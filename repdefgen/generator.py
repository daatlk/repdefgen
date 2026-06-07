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


# ---------------------------------------------------------------------------
# Structural skeletons — token-efficient boilerplate guides (~500 tokens each)
# Full samples are available in sample/ but are NOT sent in prompts to stay
# within API rate limits. These skeletons capture every required pattern.
# ---------------------------------------------------------------------------

_RDF_SKELETON = """\
-- ═══ .rdf STRUCTURAL SKELETON ═══
-- Naming: <BASE>_REP (view), <BASE>_RPT (table), <BASE>_RPI (package)

PACKAGE <BASE>_RPI IS
  TYPE binds$ IS RECORD (
    -- ALL cursor params across ALL blocks (report params + inter-block linking fields)
    param1_  VARCHAR2(50),
    param2_  NUMBER,
    linking_ VARCHAR2(12)   -- e.g. QUOTATION_REV passed from header to detail cursor
  );
  PROCEDURE Execute_Report(report_attr_ IN VARCHAR2, parameter_attr_ IN VARCHAR2);
  FUNCTION  Test(p1_ IN VARCHAR2, p2_ IN NUMBER) RETURN VARCHAR2;
  PROCEDURE Init;
END <BASE>_RPI;

-- RPT table (one Database_SYS.Set_Table_Column call per column):
Database_SYS.Set_Table_Column(columns_, 'RESULT_KEY',    'NUMBER(10)',     'N', 'Y');
Database_SYS.Set_Table_Column(columns_, 'ROW_NO',        'NUMBER(10)',     'N', 'Y');
Database_SYS.Set_Table_Column(columns_, 'PARENT_ROW_NO', 'NUMBER(10)',     'N', 'Y');
Database_SYS.Set_Table_Column(columns_, 'ROWVERSION',    'DATE',           'N', 'Y');
Database_SYS.Set_Table_Column(columns_, 'FIELD_NAME',    'VARCHAR2(100)',  'Y', 'N');
-- ... one line per field ...
Database_SYS.Create_Or_Replace_Table('<BASE>_RPT', columns_, '&IFSAPP_DATA', NULL, TRUE);

-- Column comments (FLAGS: A=Always shown, Q=Query prompt, M=Mandatory):
COMMENT ON COLUMN <BASE>_RPT.FIELD_NAME IS
   'FLAGS=A----^DATATYPE=STRING(100)^TITLE=Field Label^QUERY=:^';

-- REP view:
CREATE OR REPLACE VIEW <BASE>_REP AS
   SELECT * FROM <BASE>_RPT WHERE allowed_report = 'TRUE'
   WITH READ ONLY;

-- Registration:
Report_SYS.Define_Report_('<BASE>_REP', '<MODULE>', '<LU>', '<Title>',
                          '<BASE>_RPT', '<BASE>_RPI.Execute_Report', 0);
Report_SYS.Define_Report_Text_('<BASE>_REP', '<TEXT_KEY>', 'Sample');

-- Package body:
PACKAGE BODY <BASE>_RPI IS
  PROCEDURE Add_Result_Row___(result_key_ NUMBER, row_no_ IN OUT NUMBER,
                              parent_row_no_ NUMBER, rec_ <BASE>_RPT%ROWTYPE) IS
  BEGIN
    General_SYS.Init_Method('<BASE>_RPI', NULL, 'Add_Result_Row___', TRUE);
    INSERT INTO <BASE>_RPT VALUES rec_;
    row_no_ := row_no_ + 1;
  END Add_Result_Row___;

  PROCEDURE Execute_Report(report_attr_ IN VARCHAR2, parameter_attr_ IN VARCHAR2) IS
    binds_   binds$;
    xml_     CLOB;
    header_  <BASE>_RPT%ROWTYPE;
    detail_  <BASE>_RPT%ROWTYPE;
    row_no_  NUMBER := 1;
    CURSOR get_header(p1_ VARCHAR2, p2_ NUMBER) IS
       SELECT ... FROM <view1>, <view2> WHERE ...;
    CURSOR get_detail(p1_ VARCHAR2, link_ VARCHAR2, p2_ NUMBER) IS
       SELECT ... FROM <view3> WHERE ...;
  BEGIN
    General_SYS.Init_Method('<BASE>_RPI', NULL, 'Execute_Report');
    -- bind parameters from parameter_attr_
    Client_SYS.Add_To_Attr('PARAM1', binds_.param1_, parameter_attr_);
    Report_SYS.Start_Xml_Report(xml_, '<BASE>_REP');
    FOR h IN get_header(binds_.param1_, binds_.param2_) LOOP
      header_.result_key    := Report_SYS.Get_Result_Key;
      header_.row_no        := row_no_;
      header_.parent_row_no := 0;
      header_.FIELD_NAME    := h.field_name;
      -- populate all header fields ...
      Xml_Record_Writer_SYS.Start_Element(xml_, 'HEADERS1');
      Xml_Record_Writer_SYS.Add_Element(xml_, 'FIELD_NAME', h.field_name);
      -- link field for detail cursor:
      binds_.linking_ := h.linking_field;
      FOR d IN get_detail(binds_.param1_, binds_.linking_, binds_.param2_) LOOP
        detail_.result_key    := Report_SYS.Get_Result_Key;
        detail_.row_no        := row_no_;
        detail_.parent_row_no := header_.row_no;
        detail_.DETAIL_FIELD  := d.detail_field;
        Add_Result_Row___(detail_.result_key, row_no_, header_.row_no, detail_);
        Xml_Record_Writer_SYS.Start_Element(xml_, 'DETAILS1');
        Xml_Record_Writer_SYS.Add_Element(xml_, 'DETAIL_FIELD', d.detail_field);
        Xml_Record_Writer_SYS.End_Element(xml_, 'DETAILS1');
      END LOOP;
      Add_Result_Row___(header_.result_key, row_no_, 0, header_);
      Xml_Record_Writer_SYS.End_Element(xml_, 'HEADERS1');
    END LOOP;
    Report_SYS.Finish_Xml_Report(xml_, result_key_);
  END Execute_Report;
END <BASE>_RPI;"""

_REPORT_SKELETON = """\
-- ═══ .report STRUCTURAL SKELETON ═══
-- Block names: PascalCase  (e.g. <LU>Header, <LU>Detail)
-- Attribute names: PascalCase matching SCREAMING_SNAKE RPT columns
-- Aggregate names match XPath tokens in the .rdl

<?xml version="1.0" encoding="UTF-8"?>
<REPORT xmlns="urn:ifsworld-com:schemas:report_report">
  <CODE_GENERATION_PROPERTIES>
    <CODE_GENERATION_PROPERTIES><TITLE_TEXT>Report Title</TITLE_TEXT></CODE_GENERATION_PROPERTIES>
  </CODE_GENERATION_PROPERTIES>
  <DIAGRAMS>
    <DIAGRAM><NAME>Main</NAME><DIAGRAM_TYPE>REPORT_STRUCTURE</DIAGRAM_TYPE>
      <NODES>
        <DIAGRAM_NODE><NODE_TYPE>REPORT</NODE_TYPE>...</DIAGRAM_NODE>
        <DIAGRAM_NODE><NODE_TYPE>REPORT_BLOCK</NODE_TYPE>...</DIAGRAM_NODE>
      </NODES>
      <EDGES>
        <!-- AGGREGATE edge from parent block to child block: -->
        <DIAGRAM_EDGE><EDGE_TYPE>AGGREGATE</EDGE_TYPE>
          <PROPERTIES>
            <PROPERTY><NAME>Name</NAME><VALUE>AggName</VALUE></PROPERTY>
            <PROPERTY><NAME>IsArray</NAME><VALUE>true</VALUE></PROPERTY>
            <PROPERTY><NAME>PassedParameters</NAME>
              <VALUE>ParamName1,ParamName2</VALUE></PROPERTY>
          </PROPERTIES>
        </DIAGRAM_EDGE>
      </EDGES>
    </DIAGRAM>
  </DIAGRAMS>
  <BLOCKS>
    <BLOCK>
      <NAME><LU>Header</NAME>
      <CURSOR>SELECT h.col1, h.col2, h.linking_col FROM view1 h JOIN view2 v ON ... WHERE h.param1 = :param1 AND h.param2 = :param2</CURSOR>
      <PARAMETERS>
        <PARAMETER><NAME>Param1</NAME><DATA_TYPE_DB>VARCHAR2</DATA_TYPE_DB></PARAMETER>
        <PARAMETER><NAME>Param2</NAME><DATA_TYPE_DB>NUMBER</DATA_TYPE_DB></PARAMETER>
      </PARAMETERS>
      <ATTRIBUTES>
        <ATTRIBUTE><NAME>FieldName</NAME><DATA_TYPE>TEXT</DATA_TYPE><LENGTH>50</LENGTH></ATTRIBUTE>
        <!-- linking field (hidden, passed to child): -->
        <ATTRIBUTE><NAME>LinkingField</NAME><DATA_TYPE>TEXT</DATA_TYPE><LENGTH>12</LENGTH></ATTRIBUTE>
      </ATTRIBUTES>
      <AGGREGATES>
        <AGGREGATE>
          <NAME>Details1</NAME><BLOCK><LU>Detail</BLOCK>
          <IS_ARRAY>true</IS_ARRAY>
          <PARAMETERS>
            <PARAMETER><NAME>Param1</NAME></PARAMETER>
            <PARAMETER><NAME>LinkingField</NAME></PARAMETER><!-- passed from parent row -->
            <PARAMETER><NAME>Param2</NAME></PARAMETER>
          </PARAMETERS>
        </AGGREGATE>
      </AGGREGATES>
    </BLOCK>
    <BLOCK>
      <NAME><LU>Detail</NAME>
      <CURSOR>SELECT d.col1, d.col2 FROM view3 d WHERE d.param1 = :param1 AND d.linking = :linkingField AND d.param2 = :param2</CURSOR>
      <PARAMETERS>
        <PARAMETER><NAME>Param1</NAME><DATA_TYPE_DB>VARCHAR2</DATA_TYPE_DB></PARAMETER>
        <PARAMETER><NAME>LinkingField</NAME><DATA_TYPE_DB>VARCHAR2</DATA_TYPE_DB></PARAMETER>
        <PARAMETER><NAME>Param2</NAME><DATA_TYPE_DB>NUMBER</DATA_TYPE_DB></PARAMETER>
      </PARAMETERS>
      <ATTRIBUTES>
        <ATTRIBUTE><NAME>DetailField</NAME><DATA_TYPE>TEXT</DATA_TYPE><LENGTH>200</LENGTH></ATTRIBUTE>
      </ATTRIBUTES>
    </BLOCK>
  </BLOCKS>
  <PARAMETERS><!-- report-level parameters (top-level only, not inter-block) -->
    <PARAMETER><NAME>Param1</NAME><DATA_TYPE>TEXT</DATA_TYPE><OPTIONAL>true</OPTIONAL></PARAMETER>
    <PARAMETER><NAME>Param2</NAME><DATA_TYPE>NUMBER</DATA_TYPE><OPTIONAL>true</OPTIONAL></PARAMETER>
  </PARAMETERS>
  <AGGREGATES><!-- top-level aggregate from report root to header block -->
    <AGGREGATE><NAME>Headers1</NAME><BLOCK><LU>Header</BLOCK><IS_ARRAY>true</IS_ARRAY>
      <PARAMETERS>
        <PARAMETER><NAME>Param1</NAME></PARAMETER>
        <PARAMETER><NAME>Param2</NAME></PARAMETER>
      </PARAMETERS>
    </AGGREGATE>
  </AGGREGATES>
  <REPORT_TEXTS>
    <REPORT_TEXT><NAME>TEXT_KEY</NAME><VALUE>Sample</VALUE></REPORT_TEXT>
  </REPORT_TEXTS>
  <COMPONENT><MODULE></COMPONENT>
  <LU_NAME><LU></LU_NAME>
  <TITLE>Report Title</TITLE>
</REPORT>"""


def _format_structural_guide() -> str:
    """Return compact structural skeletons (~500 tokens) instead of full samples."""
    return (
        "=== IFS .rdf STRUCTURAL SKELETON (follow every boilerplate pattern) ===\n"
        + _RDF_SKELETON
        + "\n\n=== IFS .report STRUCTURAL SKELETON ===\n"
        + _REPORT_SKELETON
    )


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
    codebase_context = _format_chunks(chunks[:5])  # cap at 5 chunks to stay under rate limit
    guide = _format_structural_guide()

    prompt = f"""I need to generate an IFS Report Definition Package for this report.

REPORT: {parsed_rdl.report_name}
TITLE: {parsed_rdl.report_title}

BLOCK STRUCTURE AND VISIBLE FIELDS (from the .rdl layout):
{block_summary}

RELEVANT CODEBASE CONTEXT (views and APIs from the IFS Build Home):
{codebase_context}

STRUCTURAL PATTERNS TO FOLLOW:
{guide}

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
    codebase_context = _format_chunks(chunks[:5])  # cap at 5 chunks to stay under rate limit
    guide = _format_structural_guide()
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

STRUCTURAL PATTERNS TO FOLLOW:
{guide}

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
