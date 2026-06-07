"""Prompt construction, Field List proposal, .rdf/.report generation and file writing."""

import re
from pathlib import Path
from typing import NamedTuple

from repdefgen.rdl_parser import ParsedRDL
from repdefgen.session import Session

# Paths to few-shot example files (relative to this file's package root)
_HERE = Path(__file__).parent.parent

_SAMPLES = [
    {
        "label": "ExtSystemClean (WO module — 2 nested blocks, survey pivot cursors)",
        "rdf":    _HERE / "sample/wo/source/wo/database/ExtSystemClean.rdf",
        "report": _HERE / "sample/wo/model/wo/ExtSystemClean.report",
    },
    {
        "label": "JobQuote (SRVQUO module — 2 nested blocks, inter-block parameter passing)",
        "rdf":    _HERE / "sample/srvquo/source/srvquo/database/JobQuote.rdf",
        "report": _HERE / "sample/srvquo/model/srvquo/JobQuote.report",
    },
]

SYSTEM_PROMPT = (
    "You are an IFS PL/SQL developer. Generate IFS Report Definition Packages following "
    "exactly the structural patterns in the provided examples. "
    "Preserve all boilerplate patterns exactly:\n"
    "  - RPT table created via Database_SYS.Set_Table_Column calls\n"
    "  - REP view selecting from RPT with allowed_report filter\n"
    "  - Report_SYS.Define_Report_ registration (report name, module, LU, title, RPT table, package.Execute_Report)\n"
    "  - Report_SYS.Define_Report_Text_ registration (report name, text key, 'Sample')\n"
    "  - binds$ record in package spec — includes ALL cursor parameters across ALL blocks "
    "(not just top-level report parameters; child block parameters passed from parent rows belong here too)\n"
    "  - Add_Result_Row___ inserting one row into the RPT table\n"
    "  - Execute_Report driving nested cursor loops and writing XML via Xml_Record_Writer_SYS\n"
    "  - General_SYS.Init_Method calls in every procedure/function\n"
    "Naming conventions (critical — follow exactly):\n"
    "  - Package spec/body: <REPORT_NAME with _REP replaced by _RPI>  (e.g. JOB_QUOTE_REP → JOB_QUOTE_RPI)\n"
    "  - RPT table: <REPORT_NAME with _REP replaced by _RPT>  (e.g. JOB_QUOTE_REP → JOB_QUOTE_RPT)\n"
    "  - REP view: same as report name  (e.g. JOB_QUOTE_REP)\n"
    "  - .report block names: PascalCase of LU name + block role  (e.g. JobQuoteHeader, JobQuoteDetail)\n"
    "  - .report attributes: PascalCase  (e.g. QuotationNo, WqDateCreated)\n"
    "  - .rdf RPT columns: SCREAMING_SNAKE_CASE  (e.g. QUOTATION_NO, WQ_DATE_CREATED)\n"
    "Inter-block parameter passing (key pattern from JobQuote sample):\n"
    "  - Fields fetched in the parent cursor that are used as parameters in a child cursor "
    "must appear in the parent block's attribute list AND the child cursor's parameter list.\n"
    "  - These 'linking fields' (e.g. QUOTATION_REV) are often invisible in the layout but "
    "essential for correct SQL — identify them from the codebase context.\n"
    "  - They must also appear in the binds$ record.\n"
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


def _format_samples() -> str:
    """Return all reference samples formatted as a labelled few-shot block."""
    parts = []
    for s in _SAMPLES:
        rdf_text = _load_sample_text(s["rdf"])
        report_text = _load_sample_text(s["report"])
        parts.append(
            f"=== Example: {s['label']} ===\n"
            f"--- .rdf ---\n{rdf_text}\n"
            f"--- .report ---\n{report_text}"
        )
    return "\n\n".join(parts)


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
    samples = _format_samples()

    prompt = f"""I need to generate an IFS Report Definition Package for this report.

REPORT: {parsed_rdl.report_name}
TITLE: {parsed_rdl.report_title}

BLOCK STRUCTURE AND VISIBLE FIELDS (from the .rdl layout):
{block_summary}

RELEVANT CODEBASE CONTEXT (views and APIs from the IFS Build Home):
{codebase_context}

REFERENCE EXAMPLES (study both carefully before proposing):
{samples}

Based on the block structure, visible fields, and codebase context, propose the complete Field List for this report.

For EACH BLOCK include:
1. All visible fields from the .rdl (already listed above) with inferred SQL data types and lengths
2. Hidden/linking fields likely needed — primary keys, foreign keys used in JOINs, and especially
   any fields that must be fetched in a PARENT block and passed as parameters to a CHILD block cursor
   (e.g. a revision number or secondary key that is not shown in the layout but is required for the
   detail cursor WHERE clause — see JobQuote.rdf where QUOTATION_REV flows from header to detail)
3. Mark each hidden field clearly as [HIDDEN — reason]

Then list separately:
4. Report Parameters — the top-level filter inputs the developer passes when running the report
   (these appear in the binds$ record and the Execute_Report parameter_attr_ binding)
5. All binds$ fields — includes BOTH report parameters AND any inter-block linking fields

Format as a structured list per block. Be explicit about what you see in the layout vs. what you are inferring from the codebase."""

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
    samples = _format_samples()
    rdf_name = f"{meta.report_name}.rdf"
    report_name = f"{meta.report_name}.report"

    # Derive conventional names from report_name (e.g. JOB_QUOTE_REP)
    base = meta.report_name[:-4] if meta.report_name.endswith("_REP") else meta.report_name
    pkg_name = f"{base}_RPI"
    tbl_name = f"{base}_RPT"

    prompt = f"""Now generate the complete IFS Report Definition Package files.

REPORT METADATA:
- Report name (REP view): {meta.report_name}
- Package name (RPI):     {pkg_name}
- Table name (RPT):       {tbl_name}
- LU name:                {meta.lu_name}
- Module:                 {meta.module}
- Title:                  {meta.title}

CONFIRMED FIELD LIST:
{field_list}

BLOCK STRUCTURE:
{_format_block_tree(parsed_rdl.root_block)}

RELEVANT CODEBASE CONTEXT:
{codebase_context}

REFERENCE EXAMPLES (follow their structural patterns exactly):
{samples}

Generate BOTH files:

1. {rdf_name} — the complete PL/SQL Report Definition Package
   - binds$ record must include ALL cursor parameters across ALL blocks
     (report parameters + any inter-block linking fields from the field list)
   - cursor SQL must reference the views/APIs shown in the codebase context
   - RPT table columns and REP view columns must be SCREAMING_SNAKE_CASE
   - Do NOT truncate — write every BEGIN/END/PROCEDURE block completely

2. {report_name} — the IFS Report Model XML
   - Block names: PascalCase of LU + role (e.g. {meta.lu_name}Header, {meta.lu_name}Detail)
   - Attribute names: PascalCase (e.g. QuotationNo maps to column QUOTATION_NO)
   - Include aggregate edges with correct isArray=true and parameter passing between blocks
   - Report-level parameters match the top-level report parameters from the field list

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
