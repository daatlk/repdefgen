"""Parse an IFS Report Studio (.rep) file to extract structural metadata.

.rep files use the DevExpress XtraReports XML format.  Key conventions:

  Tag attribute on root:  "REPORT_NAME,orientation,True"
                           → report_name = first comma-segment

  Block hierarchy comes from DataMember attributes on band elements:
      DataMember="REQUEST.REPORT.AGG1.BLOCK1.AGG2.BLOCK2"
                           → BLOCK1 is child of report root (agg=AGG1)
                           → BLOCK2 is child of BLOCK1     (agg=AGG2)

  Field references come in three forms:
    A) [FIELD_NAME]
         simple, inside a band that carries a DataMember → belongs to that block
    B) [REQUEST.REPORT.AGG.BLOCK.FIELD]
         single-bracket dot path → block and field extracted from the path
    C) [REQUEST].[REPORT].[FIELD]
         multi-bracket path → header-level field on the report root block
    D) function wrappers e.g. StringLeft([path.FIELD], n)
         → inner path extracted with a regex then handled as B

  Ignored categories: PROCESSING_INFO, STANDARD_TRANSLATIONS, *DISPLAY_TEXT
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from repdefgen.rdl_parser import BlockInfo, ParsedRDL

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_SKIP_RE = re.compile(
    r"PROCESSING_INFO|STANDARD_TRANSLATIONS|DISPLAY_TEXT|DATA_ASSEMBLY_PARAMETERS",
    re.IGNORECASE,
)

# Single-bracket full path: [A.B.C...] — must contain at least one dot
_FULL_PATH_RE = re.compile(r"^\[([A-Z][A-Z0-9_]*\.[A-Z0-9_.]+)\]$", re.IGNORECASE)

# Simple field: [FIELD_NAME]  (no dots)
_SIMPLE_FIELD_RE = re.compile(r"^\[([A-Z][A-Z0-9_]*)\]$", re.IGNORECASE)

# Multi-bracket header: [REQUEST_NAME].[REPORT_NAME].[FIELD_NAME]
_MULTI_BRACKET_RE = re.compile(
    r"^\[([A-Z][A-Z0-9_]*)\]\.\[([A-Z][A-Z0-9_]*)\]\.\[([A-Z][A-Z0-9_]*)\]$",
    re.IGNORECASE,
)

# Embedded path inside function call, e.g. StringLeft([path.FIELD], n)
_EMBEDDED_PATH_RE = re.compile(r"\[([A-Z][A-Z0-9_.]+)\]", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _title_from_name(report_name: str) -> str:
    """EXT_SYSTEM_CLEAN_REP  →  Ext System Clean"""
    stem = re.sub(r"_REP$", "", report_name, flags=re.IGNORECASE)
    return " ".join(w.capitalize() for w in stem.split("_"))


def _skip_expr(expr: str) -> bool:
    return bool(_SKIP_RE.search(expr))


def _extract_field_from_full_path(
    path: str,
    report_name: str,
    blocks: dict[str, "BlockInfo"],
) -> Optional[tuple[str, str]]:
    """Return (block_name, field_name) from a dot-separated full path, or None."""
    prefix = f"{report_name}_REQUEST.{report_name}.".upper()
    upper = path.upper()
    if not upper.startswith(prefix):
        return None
    relative = path[len(prefix):]  # e.g. AGG.BLOCK.FIELD  or  AGG.BLOCK.AGG2.BLOCK2.FIELD
    segments = relative.split(".")
    if len(segments) < 2:
        return None
    field_name = segments[-1]
    # Walk pairs from the end to find the deepest known block
    # segments pattern: [AGG, BLOCK, AGG, BLOCK, ..., FIELD]
    # field is last; pairs before it
    for i in range(len(segments) - 2, 0, -2):
        candidate_block = segments[i]
        if candidate_block in blocks:
            return candidate_block, field_name
    # No known block matched — the block is segments[-2] if we have pairs
    if len(segments) >= 2:
        return segments[-2], field_name
    return None


# ---------------------------------------------------------------------------
# XML traversal
# ---------------------------------------------------------------------------

def _collect_fields_recursive(
    el: ET.Element,
    current_block: Optional[str],
    blocks: dict[str, "BlockInfo"],
    report_name: str,
    dm_to_block: dict[str, str],
    root_block_name: str,
) -> None:
    """Depth-first walk; track nearest DataMember ancestor as current_block."""

    dm = (el.get("DataMember") or "").upper()  # normalise case to match dm_to_block keys
    if dm and dm in dm_to_block:
        current_block = dm_to_block[dm]

    expr = el.get("Expression", "")
    if expr and not _skip_expr(expr):
        _process_expression(expr, current_block, blocks, report_name, root_block_name)

    for child in el:
        _collect_fields_recursive(
            child, current_block, blocks, report_name, dm_to_block, root_block_name
        )


def _process_expression(
    expr: str,
    current_block: Optional[str],
    blocks: dict[str, "BlockInfo"],
    report_name: str,
    root_block_name: str,
) -> None:
    # Multi-bracket header:  [REQUEST].[REPORT].[FIELD]
    m = _MULTI_BRACKET_RE.match(expr)
    if m:
        field_name = m.group(3).upper()
        _add_field(blocks, root_block_name, field_name)
        return

    # Single-bracket full path:  [REQUEST.REPORT.AGG.BLOCK.FIELD]
    m = _FULL_PATH_RE.match(expr)
    if m:
        result = _extract_field_from_full_path(m.group(1), report_name, blocks)
        if result:
            block_name, field_name = result
            # Skip if the "field" is actually a block name — it's a block reference
            if field_name in blocks:
                return
            # Ensure the block exists (it may come from expressions only)
            if block_name not in blocks:
                blocks[block_name] = BlockInfo(
                    name=block_name, aggregate_name=None, parent_name=None
                )
            _add_field(blocks, block_name, field_name)
        return

    # Simple field:  [FIELD_NAME]
    m = _SIMPLE_FIELD_RE.match(expr)
    if m:
        if current_block:
            _add_field(blocks, current_block, m.group(1).upper())
        return

    # Compound expression containing embedded path(s): StringLeft([path.FIELD], n)
    for embedded in _EMBEDDED_PATH_RE.findall(expr):
        if "." in embedded and not _skip_expr(embedded):
            result = _extract_field_from_full_path(embedded, report_name, blocks)
            if result:
                block_name, field_name = result
                # Skip block references
                if field_name in blocks:
                    continue
                if block_name not in blocks:
                    blocks[block_name] = BlockInfo(
                        name=block_name, aggregate_name=None, parent_name=None
                    )
                _add_field(blocks, block_name, field_name)


def _add_field(blocks: dict, block_name: str, field_name: str) -> None:
    if block_name in blocks and field_name not in blocks[block_name].fields:
        blocks[block_name].fields.append(field_name)


# ---------------------------------------------------------------------------
# Public parse()
# ---------------------------------------------------------------------------

def parse(rep_path: Path) -> ParsedRDL:
    """Parse a .rep file and return a ParsedRDL matching the rdl_parser contract."""
    raw = rep_path.read_bytes()
    # Strip UTF-8 BOM if present
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]

    try:
        root = ET.fromstring(raw.decode("utf-8", errors="replace"))
    except ET.ParseError:
        # Fallback: strip XML declaration and retry
        text = re.sub(r"<\?xml[^?]*\?>", "", raw.decode("utf-8", errors="replace"), count=1)
        root = ET.fromstring(text)

    # ---- Report name -------------------------------------------------------
    tag_attr = root.get("Tag", "")
    report_name = tag_attr.split(",")[0].strip().upper() if tag_attr else rep_path.stem.upper()

    # ---- Report title -------------------------------------------------------
    report_title = _title_from_name(report_name)

    # ---- Build block hierarchy from DataMember attrs -----------------------
    prefix = f"{report_name}_REQUEST.{report_name}.".upper()

    # Collect unique DataMember paths that start with our prefix
    dm_paths: set[str] = set()
    for el in root.iter():
        dm = (el.get("DataMember") or "").upper()
        if dm.startswith(prefix):
            dm_paths.add(dm)

    blocks: dict[str, BlockInfo] = {}

    for dm in sorted(dm_paths, key=len):  # shorter = ancestors first
        relative = dm[len(prefix):]      # e.g. "AGG1.BLOCK1.AGG2.BLOCK2"
        segments = relative.split(".")
        # Walk pairs (agg, block)
        for i in range(0, len(segments) - 1, 2):
            agg_name = segments[i]
            block_name = segments[i + 1]
            parent_name = segments[i - 1] if i >= 2 else None
            if block_name not in blocks:
                blocks[block_name] = BlockInfo(
                    name=block_name,
                    aggregate_name=agg_name,
                    parent_name=parent_name,
                )

    # ---- Synthetic root block for report-level (header) fields -------------
    # Used for multi-bracket [REQUEST].[REPORT].[FIELD] expressions and for
    # reports that have no sub-blocks at all.
    root_block_name = re.sub(r"_REP$", "", report_name) + "_HEADER"
    if not blocks:
        # No DataMember blocks — single-block report, everything goes here
        blocks[root_block_name] = BlockInfo(
            name=root_block_name, aggregate_name="DATA", parent_name=None
        )
    else:
        # Only add root block if any multi-bracket header expressions exist
        # (we'll add it on demand inside _add_field)
        pass

    # ---- Map DataMember path → block_name for quick lookup -----------------
    dm_to_block: dict[str, str] = {}
    for dm in dm_paths:
        relative = dm[len(prefix):]
        segs = relative.split(".")
        # Block name is the last segment of even-length pairs
        if len(segs) >= 2 and len(segs) % 2 == 0:
            dm_to_block[dm] = segs[-1]

    # ---- Extract fields ----------------------------------------------------
    _collect_fields_recursive(
        root, None, blocks, report_name, dm_to_block, root_block_name
    )

    # ---- Wire parent-child children lists ----------------------------------
    for bname, binfo in blocks.items():
        if binfo.parent_name and binfo.parent_name in blocks:
            parent = blocks[binfo.parent_name]
            if binfo not in parent.children:
                parent.children.append(binfo)

    # ---- Determine root block(s) -------------------------------------------
    roots = [b for b in blocks.values() if b.parent_name is None]

    if not roots:
        # Degenerate: make a synthetic root
        synth = BlockInfo(name="REPORT_BLOCK", aggregate_name="DATA", parent_name=None)
        synth.children = list(blocks.values())
        blocks["REPORT_BLOCK"] = synth
        root_block = synth
    elif len(roots) == 1:
        root_block = roots[0]
    else:
        # Multiple roots — pick the one with the most fields, or root_block_name
        preferred = next((r for r in roots if r.name == root_block_name), roots[0])
        root_block = preferred

    return ParsedRDL(
        report_name=report_name,
        report_title=report_title,
        root_block=root_block,
        all_blocks=blocks,
    )
