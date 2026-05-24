---
title: 'RepDefGen CLI'
type: 'feature'
created: '2026-05-24'
status: 'in-review'
baseline_commit: 'e65d114305d586720e4373f85a2c65c40390eec7'
context:
  - CONTEXT.md
  - docs/adr/0001-rdl-as-sole-file-input.md
  - docs/adr/0002-semantic-vector-index-over-symbol-graph.md
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** IFS Report Definition Packages (`.rdf`) are hand-written from scratch, which is slow and error-prone when a Report Layout (`.rdl`) already exists with the full field and block structure.

**Approach:** A two-command Python CLI: `repdefgen index` builds a semantic vector index of the customer's IFS Build Home; `repdefgen generate` parses an `.rdl`, proposes a Field List via Claude, lets the developer refine it in a chat loop, then generates the `.rdf` and `.report` files and holds the session open for SQL corrections.

## Boundaries & Constraints

**Always:**
- Use `anthropic` SDK with `claude-sonnet-4-6`; read `ANTHROPIC_API_KEY` from environment
- ChromaDB stored at `.repdefgen/index/` relative to cwd; collection name `repdefgen_index`
- Embeddings via `sentence-transformers` model `all-MiniLM-L6-v2` (local, no API cost)
- `.view` files chunked at `COMMENT ON COLUMN` statement level (one chunk per `COMMENT ON COLUMN view.col IS '...'` line); `.api`/`.apy` at function/procedure level
- Generation Session maintains full conversation history across field-list review → generation → correction phases
- Trigger detection matches the entire user input (stripped of whitespace, lowercased) exactly — `generate`, `done`, or `proceed` advances field-list review to generation; `done` or `exit` ends correction loop. A message containing these words as part of a longer sentence does not trigger phase transition.

**Ask First:**
- If `.repdefgen/index/` already exists when `index` is run, ask whether to rebuild or skip

**Never:**
- Do not use the `.xsd` file as input (see ADR 0001)
- Do not build a PL/SQL symbol graph (see ADR 0002)
- Do not implement authentication, multi-user, or server features

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Index new build home | Valid folder with `.api`/`.apy`/`.view` files | ChromaDB populated; progress printed (file count, chunk count) | Warn and skip unreadable files; abort if folder does not exist |
| Generate from valid `.rdl` | `.rdl` with `report-id`, block XPaths, `tns:FIELD` refs; index exists | `.rdf` + `.report` written after field list approval and generation | Error if index missing; warn if no fields extracted from `.rdl` |
| Field list correction | Developer types `"add CUSTOMER_NO VARCHAR2(20) to header block"` | Updated field list reprinted; loop continues | Claude rephrases if correction is ambiguous |
| Generation trigger | Developer types `generate` | Files written; correction loop begins | File write errors surfaced immediately |
| Correction loop | Developer types `"fix GROUP BY in header cursor"` | Files overwritten with fix | Claude explains if change cannot be applied |
| Exit | Developer types `done` or `exit` | Session ends; final file paths printed | — |
| `.rdl` with no block XPaths | Malformed or minimal `.rdl` | Warning printed; interactive fallback asks for block structure | — |

</frozen-after-approval>

## Code Map

- `sample/wo/source/wo/database/ExtSystemClean.rdf` -- reference `.rdf` template for generation prompt
- `sample/wo/model/wo/ExtSystemClean.report` -- reference `.report` template for generation prompt
- `sample/wo/server/reports/layouts/ExtractionSystemClean.rdl` -- sample input for manual testing
- `repdefgen/__init__.py` -- package marker
- `repdefgen/cli.py` -- click entry points: `index` and `generate` commands
- `repdefgen/indexer.py` -- Build Home file scanner, column/function chunker, sentence-transformers embedder, ChromaDB writer
- `repdefgen/rdl_parser.py` -- XML parser extracting report-id, title, block hierarchy, aggregate names, field names per block
- `repdefgen/retriever.py` -- ChromaDB query wrapper; takes field names + description, returns top-k chunks
- `repdefgen/session.py` -- Claude API conversation manager; holds message history; exposes `send(user_msg) -> str`
- `repdefgen/generator.py` -- prompt builder for field list proposal and `.rdf`/`.report` generation; file writer
- `pyproject.toml` -- package config, `repdefgen` console script entry point
- `requirements.txt` -- pinned dependencies

## Tasks & Acceptance

**Execution:**
- [x] `pyproject.toml` -- create with `[project.scripts] repdefgen = "repdefgen.cli:main"` and package metadata
- [x] `requirements.txt` -- pin: `anthropic>=0.25`, `chromadb>=0.4,<0.6`, `sentence-transformers>=2.2`, `click>=8.0`, `lxml>=4.9`
- [x] `repdefgen/__init__.py` -- empty package marker
- [x] `repdefgen/cli.py` -- implement `main` click group with `index` and `generate` subcommands; wire to indexer and generator
- [x] `repdefgen/indexer.py` -- scan Build Home for `.api`/`.apy`/`.view`; chunk `.view` files by splitting on `COMMENT ON COLUMN` lines (each `COMMENT ON COLUMN view_name.col_name IS '...'` becomes one chunk — include the preceding column definition line if present for context); chunk `.api`/`.apy` at `PROCEDURE`/`FUNCTION` boundaries; embed with `all-MiniLM-L6-v2`; upsert to ChromaDB with metadata `{file_path, file_type, chunk_type, object_name}`
- [x] `repdefgen/rdl_parser.py` -- parse `.rdl` XML; extract `report-id` from `<report-id>`, title from first `<data>` with a quoted string literal, block hierarchy from `<data>` XPath strings matching `/tns:*/tns:*/tns:*` patterns, field names from `tns:FIELD_NAME` tokens inside `<data>` elements (filter expressions, keep bare field refs)
- [x] `repdefgen/retriever.py` -- init ChromaDB client from `.repdefgen/index/`; `query(field_names, description, n=12)` embeds combined query text and returns top-k documents with metadata
- [x] `repdefgen/session.py` -- init `anthropic.Anthropic()` client; maintain `messages: list`; `send(user_msg, max_tokens=4096)` appends user message, calls `claude-sonnet-4-6` with full history and the given `max_tokens`, appends assistant reply, returns reply text; generation calls must pass `max_tokens=8192`
- [x] `repdefgen/generator.py` -- `meta` is a dict `{lu_name, module, title, report_name}`; system prompt content specified; `propose_field_list`, `generate_files`, `apply_correction` implemented

**Acceptance Criteria:**
- Given a Build Home path, when `repdefgen index <path>` runs, then ChromaDB is populated and the terminal shows file count and chunk count
- Given a populated index and an `.rdl` file, when `repdefgen generate <file.rdl>` runs, then the tool prompts for LU name, module, and description before proceeding
- Given the interactive prompts are filled, when the tool proposes a Field List, then it includes at least the fields visible in the `.rdl` plus Claude-inferred hidden fields and parameters
- Given the Field List review loop, when the developer types a natural-language correction, then the Field List is updated and reprinted
- Given the developer types `generate`, when generation completes, then `<ReportName>.rdf` and `<ReportName>.report` are written to the current directory
- Given the correction loop, when the developer types a SQL correction, then both files are overwritten with the fix applied
- Given the developer types `done` or `exit`, when in the correction loop, then the session ends and final file paths are printed

## Design Notes

**RDL block hierarchy extraction:** Block paths appear in `<data>` elements as full XPath strings like `/tns:EXT_SYSTEM_CLEAN_REP_REQUEST/tns:EXT_SYSTEM_CLEAN_REP/tns:HEADERS1/tns:EXT_SYSTEM_CLEAN_HEADER`. Strip the `tns:` prefix and the request root to get the block tree. Nested block references like `tns:EXT_DETAILS/tns:EXT_SYSTEM_CLEAN_DETAILS` appear in nested `<data>` elements and encode the aggregate name (`EXT_DETAILS`) and child block name (`EXT_SYSTEM_CLEAN_DETAILS`).

**File extraction from Claude response:** Ask Claude to delimit files with `--- BEGIN <filename> ---` / `--- END <filename> ---` markers. Split on these markers to extract file content reliably.

**Generation system prompt:** Include the full sample `.rdf` and `.report` as few-shot examples with explicit instruction: "Generate a Report Definition Package following exactly the same structural patterns as this example."

## Verification

**Commands:**
- `pip install -e .` -- expected: installs without error; `repdefgen --help` prints two subcommands
- `repdefgen index sample/` -- expected: prints file count and chunk count; `.repdefgen/index/` created
- `repdefgen generate sample/wo/server/reports/layouts/ExtractionSystemClean.rdl` -- expected: prompts for LU name, module, description; prints field list proposal
