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
-- ═══ .rdf STRUCTURAL SKELETON — follow EVERY pattern exactly ═══
-- Naming: <BASE>_REP (view), <BASE>_RPT (table), <BASE>_RPI (package)
-- Use hard-coded object names throughout — no &DEFINE substitution variables
-- Use SHOW ERROR (no S) after each CREATE ... /

-- ── PACKAGE SPECIFICATION ───────────────────────────────────────────────────
CREATE OR REPLACE PACKAGE <BASE>_RPI AS
   module_  CONSTANT VARCHAR2(6)  := '<MODULE>';
   lu_name_ CONSTANT VARCHAR2(25) := '<LU>';
   -- binds$ is NOT in the spec — it lives in the package body only
   PROCEDURE Execute_Report(report_attr_ IN VARCHAR2, parameter_attr_ IN VARCHAR2);
   FUNCTION  Test(param1_ IN VARCHAR2, param2_ IN NUMBER) RETURN NUMBER;
   PROCEDURE Init;
END <BASE>_RPI;
/
SHOW ERROR

-- ── RPT TABLE ───────────────────────────────────────────────────────────────
-- Standard header columns (use plain NUMBER, not NUMBER(10); ROWVERSION is NUMBER)
-- 'N' = NOT NULL, 'Y' = nullable  (only 3 args: name, type, nullable)
DECLARE
   columns_    Database_SYS.ColumnTabType;
   table_name_ VARCHAR2(30) := '<BASE>_RPT';
BEGIN
   Database_SYS.Reset_Column_Table(columns_);
   Database_SYS.Set_Table_Column(columns_, 'RESULT_KEY',    'NUMBER', 'N');
   Database_SYS.Set_Table_Column(columns_, 'ROW_NO',        'NUMBER', 'N');
   Database_SYS.Set_Table_Column(columns_, 'PARENT_ROW_NO', 'NUMBER', 'N');
   Database_SYS.Set_Table_Column(columns_, 'ROWVERSION',    'NUMBER', 'Y'); -- NUMBER, not DATE
   -- one line per data field (nullable):
   Database_SYS.Set_Table_Column(columns_, 'FIELD_NAME', 'VARCHAR2(100)', 'Y');
   -- ... all other fields ...
   Database_SYS.Create_Or_Replace_Table(table_name_, columns_, '&IFSAPP_REPORT_DATA', NULL, TRUE);
END;
/

-- ── RPT INDEX (separate DECLARE block) ──────────────────────────────────────
-- Index name: replace _RPT with _RPK (e.g. JOB_QUOTE_RPT → JOB_QUOTE_RPK)
DECLARE
   columns_    Database_SYS.ColumnTabType;
   table_name_ VARCHAR2(30) := '<BASE>_RPT';
   index_name_ VARCHAR2(30) := '<BASE>_RPK';
BEGIN
   Database_SYS.Reset_Column_Table(columns_);
   Database_SYS.Set_Table_Column(columns_, 'RESULT_KEY');
   Database_SYS.Set_Table_Column(columns_, 'ROW_NO');
   Database_SYS.Set_Table_Column(columns_, 'PARENT_ROW_NO');
   Database_SYS.Create_Constraint(table_name_, index_name_, columns_, 'P', '&IFSAPP_REPORT_INDEX', NULL, TRUE, TRUE);
   Database_SYS.Reset_Column_Table(columns_);
END;
/

-- ── REP VIEW ────────────────────────────────────────────────────────────────
-- Filter: EXISTS subquery against allowed_report (NOT: WHERE allowed_report = 'TRUE')
CREATE OR REPLACE VIEW <BASE>_REP AS
SELECT RESULT_KEY, ROW_NO, PARENT_ROW_NO, ROWVERSION,
       FIELD1, FIELD2  -- list every column
FROM   <BASE>_RPT t
WHERE  EXISTS (SELECT 1 FROM allowed_report a WHERE a.result_key = t.result_key)
WITH   read only;

-- Comments ONLY on the REP view (NOT on the RPT table)
-- COMMENT ON TABLE: include LU, PROMPT, MODULE, and TITLETEXT
COMMENT ON TABLE <BASE>_REP IS
   'LU=<LU>^PROMPT=<Title>^MODULE=<MODULE>^TITLETEXT=<Title>^';
COMMENT ON COLUMN <BASE>_REP.result_key IS 'FLAGS=M----^DATATYPE=NUMBER^';
COMMENT ON COLUMN <BASE>_REP.row_no     IS 'FLAGS=M----^DATATYPE=NUMBER^';
-- Report parameter columns (user-visible, queryable) — QFLAGS=OW---:
COMMENT ON COLUMN <BASE>_REP.param_col  IS
   'FLAGS=A----^DATATYPE=STRING(50)^TITLE=Param Label^QUERY=Param Label:^QFLAGS=OW---^';
-- Data columns (visible only):
COMMENT ON COLUMN <BASE>_REP.data_col   IS
   'FLAGS=A----^DATATYPE=STRING(100)^TITLE=Data Label^';

-- ── REPORT REGISTRATION ─────────────────────────────────────────────────────
-- Text key = report name WITHOUT the _REP suffix (e.g. JOB_QUOTE_REP → JOB_QUOTE)
BEGIN
   Report_SYS.Define_Report_('<BASE>_REP', '<MODULE>', '<LU>', '<Title>',
                             '<BASE>_RPT', '<BASE>_RPI.Execute_Report', 0);
   Report_SYS.Define_Report_Text_('<BASE>_REP', '<BASE_WITHOUT_REP>', 'Sample');
   Report_SYS.Refresh_('<BASE>_REP');
   Report_Lu_Definition_API.Clear_Custom_Fields_For_Report('<BASE>_REP');
END;
/

-- ── PACKAGE BODY ────────────────────────────────────────────────────────────
CREATE OR REPLACE PACKAGE BODY <BASE>_RPI IS

   -- binds$ in the BODY only (not spec); string binds use VARCHAR2(32000)
   TYPE binds$ IS RECORD (
      param1       VARCHAR2(32000),  -- string report param, no trailing underscore
      param2       NUMBER,            -- numeric report param
      linking_col  VARCHAR2(32000)   -- inter-block field passed from parent to child cursor
   );

   -- Cursors at package-body level (outside Execute_Report):
   CURSOR get_header(param1_ VARCHAR2, param2_ NUMBER) IS
      SELECT h.col1, h.linking_col, ... FROM <VIEW1> h
      LEFT JOIN <VIEW2> v ON h.key = v.key
      WHERE h.param1 = param1_ AND h.param2 = param2_;

   CURSOR get_detail(param1_ VARCHAR2, linking_col_ VARCHAR2, param2_ NUMBER) IS
      SELECT d.col1, ...
      FROM <VIEW3> d
      WHERE d.param1 = param1_ AND d.linking_col = linking_col_;

-- ── Add_Result_Row___ ────────────────────────────────────────────────────────
-- One %ROWTYPE parameter per cursor block, each DEFAULT NULL
-- Uses named-notation call site; INSERT into explicit column list with NVL fallback
--@IgnoreWrongParamOrder
PROCEDURE Add_Result_Row___ (
   result_key$_       IN NUMBER,
   binds$_            IN binds$,
   rec_header_        IN get_header%ROWTYPE  DEFAULT NULL,
   rec_detail_        IN get_detail%ROWTYPE  DEFAULT NULL,
   row_no$_           IN OUT NUMBER)
IS
BEGIN
   INSERT INTO <BASE>_RPT (
      result_key, row_no, parent_row_no,
      param1_col, linking_col, detail_col)
   VALUES (
      result_key$_,
      row_no$_, 0,
      NVL(rec_header_.param1_col, binds$_.param1),
      rec_header_.linking_col,
      rec_detail_.detail_col);
   row_no$_ := row_no$_ + 1;
END Add_Result_Row___;

-- ── Execute_Report ───────────────────────────────────────────────────────────
PROCEDURE Execute_Report(report_attr_ IN VARCHAR2, parameter_attr_ IN VARCHAR2) IS
   result_key$_         NUMBER;
   row_no$_             NUMBER := 1;
   binds$_              binds$;
   xml$_                CLOB;
   has_header_          BOOLEAN;
   rec_header_          get_header%ROWTYPE;
   par_header_          binds$;
   has_detail_          BOOLEAN;
   rec_detail_          get_detail%ROWTYPE;
   par_detail_          binds$;
BEGIN
   General_SYS.Init_Method(lu_name_, '<BASE>_RPI', 'Execute_Report');
   -- 1. Extract result key from report_attr_ (not Report_SYS.Get_Result_Key):
   result_key$_ := Client_SYS.Attr_Value_To_Number(
                      Client_SYS.Get_Item_Value('RESULT_KEY', report_attr_));
   -- 2. Bind report-level parameters from parameter_attr_:
   binds$_.param1 := Client_SYS.Get_Item_Value('PARAM1', parameter_attr_);
   binds$_.param2 := Client_SYS.Attr_Value_To_Number(
                        Client_SYS.Get_Item_Value('PARAM2', parameter_attr_));
   -- 3. Initialise XML report:
   Xml_Record_Writer_SYS.Create_Report_Header(xml$_, '<BASE>_REP', '<Title>');
   -- 4. Header loop — OPEN/FETCH/CLOSE (not FOR...IN LOOP):
   has_header_ := FALSE;
   par_header_ := binds$_;
   Xml_Record_Writer_SYS.Start_Element(xml$_, '<HEADER_AGGREGATE>'); -- e.g. 'HEADERS1'
   OPEN get_header(binds$_.param1, binds$_.param2);
   LOOP
      FETCH get_header INTO rec_header_;
      has_header_ := get_header%FOUND OR get_header%ROWCOUNT > 0;
      EXIT WHEN get_header%NOTFOUND;
      -- Capture inter-block linking field from this header row:
      binds$_.linking_col := rec_header_.linking_col;
      Xml_Record_Writer_SYS.Start_Element(xml$_, '<HEADER_BLOCK>'); -- e.g. 'JOB_QUOTE_HEADER'
      Xml_Record_Writer_SYS.Add_Element(xml$_, 'FIELD1', rec_header_.col1);
      -- ... all header fields ...
      -- 5. Detail loop (nested):
      has_detail_ := FALSE;
      par_detail_ := binds$_;
      binds$_.param1       := rec_header_.param1_col;
      binds$_.linking_col  := rec_header_.linking_col;
      Xml_Record_Writer_SYS.Start_Element(xml$_, '<DETAIL_AGGREGATE>'); -- e.g. 'DETAILS1'
      OPEN get_detail(binds$_.param1, binds$_.linking_col, binds$_.param2);
      LOOP
         FETCH get_detail INTO rec_detail_;
         has_detail_ := get_detail%FOUND OR get_detail%ROWCOUNT > 0;
         EXIT WHEN get_detail%NOTFOUND;
         Xml_Record_Writer_SYS.Start_Element(xml$_, '<DETAIL_BLOCK>');
         Xml_Record_Writer_SYS.Add_Element(xml$_, 'DETAIL_FIELD', rec_detail_.col1);
         Xml_Record_Writer_SYS.End_Element(xml$_, '<DETAIL_BLOCK>');
         Add_Result_Row___(result_key$_,
                           binds$_        => binds$_,
                           rec_header_    => rec_header_,
                           rec_detail_    => rec_detail_,
                           row_no$_       => row_no$_);
      END LOOP;
      CLOSE get_detail;
      Xml_Record_Writer_SYS.End_Element(xml$_, '<DETAIL_AGGREGATE>');
      binds$_ := par_detail_;
      -- Fallback: write an empty detail row so the header is never orphaned:
      IF NOT has_detail_ THEN
         Add_Result_Row___(result_key$_, binds$_ => binds$_,
                           rec_header_ => rec_header_, row_no$_ => row_no$_);
      END IF;
      Xml_Record_Writer_SYS.End_Element(xml$_, '<HEADER_BLOCK>');
   END LOOP;
   CLOSE get_header;
   Xml_Record_Writer_SYS.End_Element(xml$_, '<HEADER_AGGREGATE>');
   binds$_ := par_header_;
   -- Fallback: write a row even when query returns nothing:
   IF NOT has_header_ THEN
      Add_Result_Row___(result_key$_, binds$_ => binds$_, row_no$_ => row_no$_);
   END IF;
   -- 6. Close report XML and finish (report name is first arg):
   Xml_Record_Writer_SYS.End_Element(xml$_, '<BASE>_REP');
   Report_SYS.Finish_Xml_Report('<BASE>_REP', result_key$_, xml$_);
EXCEPTION
   WHEN OTHERS THEN
      IF get_header%ISOPEN THEN CLOSE get_header; END IF;
      IF get_detail%ISOPEN THEN CLOSE get_detail; END IF;
      RAISE;
END Execute_Report;

-- ── Test function ────────────────────────────────────────────────────────────
FUNCTION Test(param1_ IN VARCHAR2, param2_ IN NUMBER) RETURN NUMBER IS
   result_key_     NUMBER;
   report_attr_    VARCHAR2(200);
   parameter_attr_ VARCHAR2(32000);
BEGIN
   General_SYS.Init_Method(lu_name_, '<BASE>_RPI', 'Test');
   Report_SYS.Get_Result_Key__(result_key_);         -- double underscore
   Client_SYS.Add_To_Attr('RESULT_KEY', result_key_, report_attr_);
   IF param1_ IS NOT NULL THEN
      Client_SYS.Add_To_Attr('PARAM1', param1_, parameter_attr_);
   END IF;
   IF param2_ IS NOT NULL THEN
      Client_SYS.Add_To_Attr('PARAM2', param2_, parameter_attr_);
   END IF;
   Execute_Report(report_attr_, parameter_attr_);
   RETURN result_key_;
END Test;

PROCEDURE Init IS BEGIN NULL; END Init;

END <BASE>_RPI;
/
SHOW ERROR"""

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
    codebase_context = _format_chunks(chunks[:8])  # cap chunks to stay under rate limit
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
    codebase_context = _format_chunks(chunks[:8])  # cap chunks to stay under rate limit
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
