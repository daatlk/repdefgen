# RepDefGen

A tool that reverse-engineers an IFS Report Definition Package from an existing Report Layout, using a semantic index of the customer's IFS codebase to generate the cursor SQL.

## Language

### IFS Report Artifacts

**Report Definition Package**:
The PL/SQL implementation of an IFS report, delivered as a `.rdf` file. Contains the package spec, RPT result table DDL, REP view, report registration call, and the package body with named cursors and `Execute_Report`.
_Avoid_: RDF, report package, report procedure

**Report Layout**:
The IFS/SSRS presentation file (`.rdl`) describing visual structure — field XPath references, styling, and page layout. Contains no SQL, no data types, and no parameters.
_Avoid_: RDL file, layout file

**Report Model**:
The IFS Developer Studio XML file (`.report`) describing blocks, cursor definitions, attributes, and aggregate hierarchy. In the normal forward workflow, the developer writes this and IFS generates the Report Definition Package from it. RepDefGen generates both outputs together.
_Avoid_: report file, `.report` file, designer file

**Report Block**:
A named cursor and result set within a Report Definition Package, corresponding to one loop in `Execute_Report`. Each block has parameters, a cursor SQL definition, and a list of attributes.
_Avoid_: section, dataset, sub-report

**Report Parameter**:
A named filter input declared at report level and passed into cursor SQL as a bind variable. Parameters are not present in the Report Layout and must be inferred by the LLM and confirmed by the developer.
_Avoid_: filter, input, query parameter

**Aggregate**:
A named parent-child relationship between two Report Blocks. Encoded as a nested loop in `Execute_Report` and as an array edge in the Report Model.
_Avoid_: relationship, nesting, sub-block

### Tool Concepts

**Build Home**:
The customer's IFS installation directory containing the combined core and custom source files (`.api`, `.apy`, `.view`). This is the corpus that is indexed. A single Build Home contains both standard IFS product code and customer-specific customisations.
_Avoid_: codebase, IFS source, installation

**Codebase Index**:
The local ChromaDB vector database built from the Build Home. `.view` files are chunked at column definition level; `.api` and `.apy` files are chunked at function/procedure level. Built once with `repdefgen index` and queried at generation time.
_Avoid_: vector store, index, embedding database

**Field List**:
The developer-confirmed set of attributes per block — including fields not visually displayed in the Report Layout — plus their inferred types and the report's parameters. Produced during the interactive review phase before SQL generation begins.
_Avoid_: attribute list, column list, schema

**Generation Session**:
The continuous Claude API conversation that begins with Field List proposal, continues through developer review and correction in natural language, extends through SQL generation, and persists until the developer explicitly ends it with `done` or `exit`.
_Avoid_: session, chat, conversation

## Example dialogue

> **Dev**: I need to generate the RDF for this cleaning report. The layout is `ExtractionSystemClean.rdl`.
>
> **Tool**: What's the LU name and module? And briefly, what is this report about?
>
> **Dev**: LU is `ExtSysClean`, module `WO`. It's a work order task report showing before/after extraction system cleaning survey results.
>
> **Tool**: Here's the proposed Field List for the two blocks — `ExtSystemCleanHeader` and `ExtSystemCleanDetails`. I've inferred `TASK_SEQ` and `CUSTOMER_NO` as hidden fields in the header block, and `WO_NO` / `TASK_NO` as Report Parameters. Does this look right?
>
> **Dev**: Add `WO_NO` to the header block too. And the parameter should be `TASK_SEQ` not `TASK_NO`.
>
> **Tool**: Updated. Generating now — writing `ExtSystemClean.rdf` and `ExtSystemClean.report`.
>
> **Dev**: The header cursor needs to join `jt_task_survey_answers` on `task_seq` only, not `wo_no`.
>
> **Tool**: Corrected the join condition in `get_ext_system_clean_header`. Files updated.
