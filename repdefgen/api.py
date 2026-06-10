"""FastAPI backend for the RepDefGen web UI.

Session lifecycle:
  POST /api/sessions          — upload .rdl, parse, run RAG → SessionState created
  POST /api/sessions/{id}/field-list          — propose field list (LU/module/desc)
  POST /api/sessions/{id}/field-list/correct  — apply natural-language correction
  POST /api/sessions/{id}/generate            — generate .rdf + .report files
  POST /api/sessions/{id}/correct             — apply SQL correction to .rdf
  GET  /api/sessions/{id}/download/{filename} — stream a generated file
  DELETE /api/sessions/{id}                   — clean up temp dir

The compiled React build is served as static files at /.
"""

import os
import secrets
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

INDEX_DIR = Path(".repdefgen/index")

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_valid_tokens: set[str] = set()
_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    if not credentials or credentials.credentials not in _valid_tokens:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    session_id: str
    temp_dir: str
    rdl_path: Optional[Path] = None
    parsed_rdl: Optional[object] = None   # repdefgen.rdl_parser.ParsedRDL
    chunks: list = field(default_factory=list)
    claude_session: Optional[object] = None  # repdefgen.session.Session
    written_files: dict = field(default_factory=dict)  # filename -> Path
    meta: Optional[object] = None         # repdefgen.generator.Meta


_sessions: dict[str, SessionState] = {}


def _get_session(session_id: str) -> SessionState:
    s = _sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="RepDefGen API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class BlockSummary(BaseModel):
    name: str
    field_count: int
    aggregate_name: Optional[str]
    parent_name: Optional[str]


class SessionCreatedResponse(BaseModel):
    session_id: str
    report_name: str
    report_title: str
    blocks: list[BlockSummary]


class FieldListRequest(BaseModel):
    lu_name: str
    module: str
    description: str


class MessageResponse(BaseModel):
    message: str


class FieldListResponse(BaseModel):
    message: str
    field_list: dict  # {blocks: [...], parameters: [...]}


class CorrectionRequest(BaseModel):
    text: str


class FieldListCorrectionRequest(BaseModel):
    text: str
    field_list: dict  # client's current state, including manual edits


class GenerateRequest(BaseModel):
    field_list: Optional[dict] = None  # client's confirmed state; None = legacy flow


class FilesResponse(BaseModel):
    files: dict[str, str]  # filename -> content


class LoginRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    token: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Exchange the APP_PASSWORD for a bearer token."""
    app_password = os.environ.get("APP_PASSWORD", "")
    if not app_password:
        raise HTTPException(status_code=500, detail="APP_PASSWORD environment variable is not set")
    if req.password != app_password:
        raise HTTPException(status_code=401, detail="Invalid password")
    token = secrets.token_hex(32)
    _valid_tokens.add(token)
    return TokenResponse(token=token)


@app.post("/api/sessions", response_model=SessionCreatedResponse)
async def create_session(rdl_file: UploadFile = File(...), _: str = Depends(require_auth)):
    """Upload an .rdl file, parse it, and run RAG retrieval."""
    suffix = Path(rdl_file.filename).suffix.lower() if rdl_file.filename else ""
    if suffix not in (".rdl", ".rep"):
        raise HTTPException(status_code=400, detail="Only .rdl and .rep files are supported")

    # Check index exists
    if not INDEX_DIR.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Codebase index not found at .repdefgen/index/. "
                "Run `repdefgen index <build-home>` first."
            ),
        )

    # Save uploaded file to a temp directory
    temp_dir = tempfile.mkdtemp(prefix="repdefgen_")
    session_id = str(uuid.uuid4())

    rdl_bytes = await rdl_file.read()
    rdl_path = Path(temp_dir) / rdl_file.filename
    rdl_path.write_bytes(rdl_bytes)

    # Parse layout file (.rdl or .rep)
    from repdefgen import retriever
    if suffix == ".rep":
        from repdefgen import rep_parser as layout_parser
    else:
        from repdefgen import rdl_parser as layout_parser
    try:
        parsed = layout_parser.parse(rdl_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to parse layout file: {exc}")

    # RAG retrieval
    all_fields = [f for b in parsed.all_blocks.values() for f in b.fields]
    try:
        chunks = retriever.query(all_fields, parsed.report_title, INDEX_DIR, n=8)
    except Exception as exc:
        chunks = []  # non-fatal: generation can proceed with empty context

    # Store state
    state = SessionState(
        session_id=session_id,
        temp_dir=temp_dir,
        rdl_path=rdl_path,
        parsed_rdl=parsed,
        chunks=chunks,
    )
    _sessions[session_id] = state

    blocks = [
        BlockSummary(
            name=b.name,
            field_count=len(b.fields),
            aggregate_name=b.aggregate_name,
            parent_name=b.parent_name,
        )
        for b in parsed.all_blocks.values()
    ]

    return SessionCreatedResponse(
        session_id=session_id,
        report_name=parsed.report_name,
        report_title=parsed.report_title,
        blocks=blocks,
    )


@app.post("/api/sessions/{session_id}/field-list", response_model=FieldListResponse)
async def propose_field_list(session_id: str, req: FieldListRequest, _: str = Depends(require_auth)):
    """Create the Claude session and propose an initial structured field list."""
    state = _get_session(session_id)

    from repdefgen.generator import Meta, propose_field_list_structured, SYSTEM_PROMPT
    from repdefgen.session import Session

    meta = Meta(
        lu_name=req.lu_name,
        module=req.module,
        title=state.parsed_rdl.report_title,
        report_name=state.parsed_rdl.report_name,
    )
    state.meta = meta

    try:
        claude_session = Session(system_prompt=SYSTEM_PROMPT)
        state.claude_session = claude_session
        result = propose_field_list_structured(state.parsed_rdl, state.chunks, claude_session)
    except EnvironmentError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Claude error: {exc}")

    message = result.pop("message", "Field list proposed.")
    return FieldListResponse(message=message, field_list=result)


@app.post("/api/sessions/{session_id}/field-list/correct", response_model=FieldListResponse)
async def correct_field_list(session_id: str, req: FieldListCorrectionRequest, _: str = Depends(require_auth)):
    """Apply a natural-language correction to the client's current field list."""
    state = _get_session(session_id)
    if not state.claude_session:
        raise HTTPException(status_code=400, detail="Field list not yet proposed")

    from repdefgen.generator import correct_field_list_structured

    try:
        result = correct_field_list_structured(req.text, req.field_list, state.claude_session)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Claude error: {exc}")

    message = result.pop("message", "Field list updated.")
    return FieldListResponse(message=message, field_list=result)


@app.post("/api/sessions/{session_id}/generate", response_model=FilesResponse)
async def generate_files(session_id: str, req: GenerateRequest = None, _: str = Depends(require_auth)):
    """Generate the .rdf and .report files from the confirmed field list."""
    state = _get_session(session_id)
    if not state.claude_session or not state.meta:
        raise HTTPException(status_code=400, detail="Field list not yet proposed")

    from repdefgen.generator import generate_files as _generate

    output_dir = Path(state.temp_dir)
    if req and req.field_list:
        # Client's structured state (includes manual edits) is the source of truth
        field_list = req.field_list
    else:
        # Legacy fallback: last assistant message in session history
        history = state.claude_session.history
        field_list = next(
            (m["content"] for m in reversed(history) if m["role"] == "assistant"),
            "",
        )

    try:
        written = _generate(
            field_list,
            state.parsed_rdl,
            state.meta,
            state.chunks,
            state.claude_session,
            output_dir,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation error: {exc}")

    state.written_files = written

    files = {name: path.read_text(encoding="utf-8") for name, path in written.items()}
    return FilesResponse(files=files)


@app.post("/api/sessions/{session_id}/correct", response_model=FilesResponse)
async def apply_correction(session_id: str, req: CorrectionRequest, _: str = Depends(require_auth)):
    """Apply a SQL correction to the generated .rdf file."""
    state = _get_session(session_id)
    if not state.written_files:
        raise HTTPException(status_code=400, detail="Files not yet generated")

    from repdefgen.generator import apply_correction as _correct

    try:
        updated = _correct(req.text, state.claude_session, state.written_files)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Correction error: {exc}")

    state.written_files = updated

    files = {name: path.read_text(encoding="utf-8") for name, path in updated.items()}
    return FilesResponse(files=files)


@app.get("/api/sessions/{session_id}/download/{filename}")
async def download_file(session_id: str, filename: str, _: str = Depends(require_auth)):
    """Stream a generated file as a download."""
    state = _get_session(session_id)
    # Sanitise: only allow filenames present in written_files
    if filename not in state.written_files:
        raise HTTPException(status_code=404, detail="File not found in this session")
    path = state.written_files[filename]
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/octet-stream",
    )


@app.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, _: str = Depends(require_auth)):
    """Remove session state and clean up temp files."""
    import shutil
    state = _sessions.pop(session_id, None)
    if state:
        shutil.rmtree(state.temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Serve React build (must come last so API routes take priority)
# ---------------------------------------------------------------------------

_UI_DIST = Path(__file__).parent.parent / "ui" / "dist"
if _UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")
