"""Prompt construction, Field List proposal, .rdf/.report generation and file writing."""

import re
from pathlib import Path
from typing import NamedTuple

from repdefgen.rdl_parser import ParsedRDL
from repdefgen.session import Session

# Paths to few-shot example files (relative to this file's package root)
_HERE = Path(__file__).parent.parent
SAMPLE_RDF = _HERE / "sample/wo/source/wo/database/ExtSystemClean.rdf"
SAMPLE_REPORT = _HERE / "sample/wo/model/wo/ExtSystemClean.report"

SYSTEM_PROMPT = (
    "You are an IFS PL/SQL developer. Generate IFS Report Definition Packages following "
    "exactly the structural patterns in the provided examples. "
    "Preserve all boilerplate patterns (RPT table DDL, REP view, report registration, "
    "Execute_Report loop structure, Add_Result_Row___ procedure, binds$ record, "
    "Xml_Record_Writer_SYS calls, General_SYS.Init_Method calls). "
    "Output files delimited by exactly these markers (one per line):\n"
    "  --- BEGIN <filename> ---\n"
    "  <file content>\n"
    "  --- END <filename> ---\n"
    "Never truncate output. If a file is large, continue until fully written."
)


class Meta(NamedTuple):
    lu_name: str
    module: str
    title: str
    report_name: str


def _load_sample_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"[sample file not found: {path}]"


def _format_block_tree(block, indent: int = 0) -> str:
    prefix = "  " * indent
    lines = [f"{prefix}Block: {block.name} (aggregate: {block.aggregate_name})"]
    for f in block.fields:
        lines.append(f"{prefix}  field: {f}")
    for child in block.children:
        lines.extend(_format_block_tree(child, indent + 1).splitlines())
    return "\n".join(lines)


def _format_chunks(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        parts.append(
            f"[{c['file_type'].upper()} | {c['object_name']}]\n{c['text']}"
        )
    return "\n\n---\n\n".join(parts)


def _extract_files(response: str) -> dict[str, str]:
    """Extract delimited files from Claude response."""
    pattern = re.compile(
        r"---\s*BEGIN\s+(.+?)\s*---\r?\n(.*?)---\s*END\s+\1\s*---",
        re.DOTALL,
    )
    return {m.group(1).strip(): m.group(2) for m in pattern.finditer(response)}


def propose_field_list(
    parsed_rdl: ParsedRDL,
    chunks: list[dict],
    session: Session,
) -> str:
    """Ask Claude to propose the complete Field List for all blocks."""
    block_summary = _format_block_tree(parsed_rdl.root_block)
    codebase_context = _format_chunks(chunks)
    sample_rdf = _load_sample_text(SAMPLE_RDF)
    sample_report = _load_sample_text(SAMPLE_REPORT)

    prompt = f"""I need to generate an IFS Report Definition Package for this report.

REPORT: {parsed_rdl.report_name}
TITLE: {parsed_rdl.report_title}

BLOCK STRUCTURE AND VISIBLE FIELDS (from the .rdl layout):
{block_summary}

RELEVANT CODEBASE CONTEXT (views and APIs from the IFS Build Home):
{codebase_context}

REFERENCE EXAMPLES:
=== Sample .rdf ===
{sample_rdf}

=== Sample .report ===
{sample_report}

Based on the block structure, visible fields, and codebase context, propose the complete Field List for this report. Include:
1. All visible fields from the .rdl (already listed above)
2. Any hidden/linking fields likely needed (e.g. primary keys, foreign keys used in JOINs)
3. Report Parameters (the filter inputs the user passes when running the report)
4. Inferred SQL data types and lengths for each field

Format your response as a structured list per block, then list the Report Parameters separately. Be explicit about what you are inferring vs. what you see directly in the layout."""

    return session.send(prompt, max_tokens=4096)


def generate_files(
    field_list: str,
    parsed_rdl: ParsedRDL,
    meta: Meta,
    chunks: list[dict],
    session: Session,
    output_dir: Path,
) -> dict[str, Path]:
    """
    Generate the .rdf and .report files from the confirmed Field List.
    Returns dict of filename -> written Path.
    """
    codebase_context = _format_chunks(chunks)
    rdf_name = f"{meta.report_name}.rdf"
    report_name = f"{meta.report_name}.report"

    prompt = f"""Now generate the complete IFS Report Definition Package files.

REPORT METADATA:
- Report name: {meta.report_name}
- LU name: {meta.lu_name}
- Module: {meta.module}
- Title: {meta.title}

CONFIRMED FIELD LIST:
{field_list}

BLOCK STRUCTURE:
{_format_block_tree(parsed_rdl.root_block)}

RELEVANT CODEBASE CONTEXT:
{codebase_context}

Generate BOTH files following the exact structural patterns of the provided examples:

1. {rdf_name} — the complete PL/SQL Report Definition Package (.rdf)
2. {report_name} — the IFS Report Model XML (.report)

Use the CONFIRMED FIELD LIST above for all attributes, parameters, and cursor SQL.
Generate realistic cursor SQL by referencing the views and APIs shown in the codebase context.
Do NOT truncate. Write every file completely.

Delimit each file with:
--- BEGIN <filename> ---
<complete file content>
--- END <filename> ---"""

    response = session.send(prompt, max_tokens=8192)
    files = _extract_files(response)

    written: dict[str, Path] = {}
    output_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in files.items():
        safe_name = Path(filename).name  # strip any path components from Claude's response
        out_path = output_dir / safe_name
        out_path.write_text(content, encoding="utf-8")
        written[safe_name] = out_path

    if not written:
        # Claude didn't use markers — write raw response as .rdf fallback
        fallback = output_dir / rdf_name
        fallback.write_text(response, encoding="utf-8")
        written[rdf_name] = fallback

    return written


def apply_correction(
    correction: str,
    session: Session,
    written_files: dict[str, Path],
) -> dict[str, Path]:
    """
    Apply a developer correction to the .rdf only (structural .report is not regenerated).
    Returns updated dict of written files.
    """
    rdf_files = {k: v for k, v in written_files.items() if k.endswith(".rdf")}
    if not rdf_files:
        return written_files

    rdf_name = next(iter(rdf_files))
    current_rdf = rdf_files[rdf_name].read_text(encoding="utf-8")

    prompt = f"""Apply this correction to the .rdf file:

CORRECTION: {correction}

CURRENT .rdf CONTENT:
{current_rdf}

Return the complete corrected .rdf file using the same delimiter format:
--- BEGIN {rdf_name} ---
<complete corrected content>
--- END {rdf_name} ---"""

    response = session.send(prompt, max_tokens=8192)
    files = _extract_files(response)

    updated = dict(written_files)
    for filename, content in files.items():
        if filename in updated:
            updated[filename].write_text(content, encoding="utf-8")
        else:
            # Claude used a slightly different filename — match by extension
            for k, v in updated.items():
                if k.endswith(".rdf") and filename.endswith(".rdf"):
                    v.write_text(content, encoding="utf-8")
                    break

    return updated
