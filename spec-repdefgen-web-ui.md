---
title: 'RepDefGen Web UI'
type: 'feature'
created: '2026-06-07'
status: 'in-review'
baseline_commit: '07875597ccc06b44163ed74a73ad3df752dcf3da'
context:
  - spec-repdefgen-cli.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The `repdefgen generate` workflow is terminal-only, requiring developers to type LU names, field list corrections, and SQL fixes inside a CLI loop — making it hard to review output, iterate quickly, or share with non-terminal users.

**Approach:** Add a FastAPI backend + React/Tailwind frontend that exposes the same three-phase generate flow (upload RDL → field list review → preview & download) as a server-deployable web app. The CLI and indexer remain unchanged; the UI is additive only.

## Boundaries & Constraints

**Always:**
- Reuse existing Python modules unchanged: `rdl_parser`, `retriever`, `session`, `generator`
- One FastAPI session object per browser session (UUID keyed, in-memory store)
- FastAPI serves the compiled React build at `/` for single-binary deployment
- Uploaded `.rdl` files and generated outputs stored in `tempfile.mkdtemp()` per session; cleaned up on session delete or server restart
- Index directory defaults to `.repdefgen/index/` relative to server cwd (same as CLI)

**Ask First:**
- If `.repdefgen/index/` is missing when the user hits Generate, surface a blocking error with instructions to run `repdefgen index` first — do not silently fail

**Never:**
- No authentication or multi-user isolation beyond session UUID
- No database — all state is in-memory
- Do not modify `repdefgen/cli.py`, `indexer.py`, or any existing module

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Upload valid .rdl | `.rdl` file via drag-drop | Parsed metadata shown (report name, blocks, field counts); form unlocks | Parse error → inline message, file rejected |
| Upload non-.rdl file | `.pdf`, `.txt`, etc. | Rejected before upload with "Only .rdl files supported" | Client-side validation |
| Index missing at generate | No `.repdefgen/index/` on server | Blocking banner: "Run `repdefgen index <build-home>` first" | Do not call Claude |
| Field list proposal | Valid session + LU/module/description filled | Chat bubble with Claude's proposal appears | API error → error bubble in chat |
| Field list correction | User types correction and submits | New chat bubble with updated field list | Disable input while waiting; re-enable on response |
| Generate RDF | User clicks "Generate RDF" in review step | Progress indicator → navigates to preview step with both files | File write error surfaced in toast |
| Download | User clicks download on preview | Browser downloads the file | — |
| SQL correction | User types correction in preview step | Both files re-rendered in code viewer | Error bubble if Claude fails |
| Session expiry / page reload | UUID cookie lost | Start over prompt; old temp files cleaned up | — |

</frozen-after-approval>

## Code Map

- `repdefgen/api.py` — new: FastAPI app, session store, all `/api/*` routes
- `repdefgen/generator.py` — existing: `propose_field_list`, `generate_files`, `apply_correction`, `Meta`, `SYSTEM_PROMPT`
- `repdefgen/session.py` — existing: `Session` class
- `repdefgen/rdl_parser.py` — existing: `parse()`
- `repdefgen/retriever.py` — existing: `query()`
- `ui/` — new: React + Vite + Tailwind project
- `ui/src/App.tsx` — top-level router: Upload → Review → Preview steps
- `ui/src/components/UploadStep.tsx` — drag-drop zone + LU/module/description form
- `ui/src/components/ReviewStep.tsx` — chat bubble layout, correction input, Generate RDF button
- `ui/src/components/PreviewStep.tsx` — tabbed code viewer (RDF | .report), download, correction input
- `ui/src/api.ts` — typed fetch wrappers for all API routes
- `ui/package.json` — React 18, Vite, Tailwind CSS, `react-syntax-highlighter`, `react-dropzone`
- `Dockerfile` — multi-stage: node build → python image; FastAPI serves `ui/dist/` as static files
- `pyproject.toml` — add `fastapi>=0.110`, `uvicorn>=0.29`, `python-multipart>=0.0.9`

## Tasks & Acceptance

**Execution:**
- [x] `repdefgen/api.py` — create FastAPI app with in-memory `sessions: dict[str, SessionState]`; `SessionState` holds `parsed_rdl`, `chunks`, `session` (Claude Session), `written_files`, `temp_dir`; implement routes:
  - `POST /api/sessions` — accept `multipart/form-data` with `rdl_file`; run `rdl_parser.parse()` + `retriever.query()`; store state; return `{session_id, report_name, report_title, blocks}`
  - `POST /api/sessions/{id}/field-list` — accept `{lu_name, module, description}`; call `propose_field_list()`; return `{message}`
  - `POST /api/sessions/{id}/field-list/correct` — accept `{text}`; call `session.send()` with correction prompt; return `{message}`
  - `POST /api/sessions/{id}/generate` — call `generate_files()`; return `{files: {filename: content}}`
  - `POST /api/sessions/{id}/correct` — accept `{text}`; call `apply_correction()`; return `{files: {filename: content}}`
  - `GET /api/sessions/{id}/download/{filename}` — stream file from temp dir
  - Mount `ui/dist/` as `StaticFiles(html=True)` at `/`
- [x] `ui/` — scaffold with `npm create vite@latest ui -- --template react-ts`; install `tailwindcss`, `react-dropzone`, `react-syntax-highlighter`, `@types/react-syntax-highlighter`; configure Tailwind
- [x] `ui/src/App.tsx` — three-step wizard state machine: `upload | review | preview`; pass `sessionId` between steps
- [x] `ui/src/components/UploadStep.tsx` — drag-drop zone (`.rdl` only); LU name, Module, Description fields below; "Propose Field List" button calls `POST /api/sessions` then `POST .../field-list`; disabled until all fields filled and file dropped
- [x] `ui/src/components/ReviewStep.tsx` — chat bubbles (assistant = indigo left, user = slate right); markdown rendered in assistant bubbles; sticky bottom input + Send (Enter key); "Generate RDF ▶" button fixed at bottom right; disabled while waiting
- [x] `ui/src/components/PreviewStep.tsx` — two tabs: RDF | .report; `react-syntax-highlighter` with `vscDarkPlus` theme; Download button per tab; sticky correction input at bottom with "Apply" button
- [x] `ui/src/api.ts` — typed fetch wrappers returning typed responses for all routes; includes `sessionId` in all requests
- [x] `Dockerfile` — stage 1: `node:20-alpine`, `COPY ui/ .`, `npm ci`, `npm run build`; stage 2: `python:3.11-slim`, copy `repdefgen/` + `ui/dist/` + requirements, `CMD ["uvicorn", "repdefgen.api:app", "--host", "0.0.0.0", "--port", "8000"]`
- [x] `pyproject.toml` — add `fastapi>=0.110`, `uvicorn>=0.29`, `python-multipart>=0.0.9` to dependencies

**Acceptance Criteria:**
- Given the server is running and the index exists, when a user drops a `.rdl` file and fills in LU/module/description and clicks "Propose Field List", then a chat bubble with Claude's field list proposal appears within the UI
- Given a field list has been proposed, when the user types a correction and presses Enter, then a new assistant bubble with the updated field list appears and the input re-enables
- Given the field list is ready, when the user clicks "Generate RDF", then the UI transitions to the Preview step showing both files in syntax-highlighted tabs
- Given the Preview step, when the user clicks Download on the RDF tab, then the browser downloads the `.rdf` file
- Given the Preview step, when the user submits a SQL correction, then both file tabs update with the corrected content
- Given `docker build . && docker run -p 8000:8000 -v ./build-home:/app/build-home .`, when `http://localhost:8000` is opened, then the UI loads and the full workflow is usable

## Design Notes

**Session lifecycle:** Each page load generates a new UUID stored in `sessionStorage`. The FastAPI session dict maps UUID → `SessionState`. No persistence across server restarts — users start fresh.

**API ↔ UI coupling:** `generate` and `correct` return full file content as strings in JSON (not file streams) so the UI can render them in the code viewer without a second request. Only the Download endpoint streams the file.

**Vite dev proxy:** `vite.config.ts` proxies `/api/*` to `http://localhost:8000` during development so `npm run dev` and `uvicorn` run independently.

**Color palette (Tailwind):** Background `slate-950`, cards `slate-900`, accent `indigo-500`, text `slate-100`. Matches VS Code Dark+ aesthetic.

## Verification

**Commands:**
- `cd ui && npm run build` — expected: exits 0, `ui/dist/` populated
- `uvicorn repdefgen.api:app --reload` — expected: server starts, `http://localhost:8000` serves the React app
- `docker build -t repdefgen-ui . && docker run -p 8000:8000 repdefgen-ui` — expected: container starts, UI accessible at `http://localhost:8000`
