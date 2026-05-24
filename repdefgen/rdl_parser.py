"""Parse an IFS Report Layout (.rdl) file to extract structural metadata."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from lxml import etree


@dataclass
class BlockInfo:
    name: str
    aggregate_name: Optional[str]  # name of the aggregate edge from parent (e.g. "HEADERS1")
    parent_name: Optional[str]
    fields: list[str] = field(default_factory=list)
    children: list["BlockInfo"] = field(default_factory=list)


@dataclass
class ParsedRDL:
    report_name: str       # e.g. EXT_SYSTEM_CLEAN_REP
    report_title: str      # e.g. "Extraction System Cleaning"
    root_block: BlockInfo  # top-level block (aggregate from report root)
    all_blocks: dict[str, BlockInfo]  # name -> BlockInfo


def _strip_tns(token: str) -> str:
    return token.replace("tns:", "")


def _extract_tns_fields(text: str) -> list[str]:
    """Return bare field names from tns:FIELD_NAME tokens, excluding path-like expressions."""
    tokens = re.findall(r"tns:([A-Z][A-Z0-9_]*)", text)
    # Filter out tokens that look like block/aggregate names used in XPath navigation
    # (those appear in longer path strings; bare field refs appear alone or in concat())
    fields = []
    for t in tokens:
        # Skip if this token is part of a multi-segment XPath (preceded by another tns: segment)
        if f"tns:{t}/tns:" in text or f"/{t}/" in text:
            continue
        fields.append(t)
    return fields


def _parse_block_paths(data_elements: list[str]) -> dict[str, dict]:
    """
    Extract block hierarchy from XPath data paths.

    Full path example:
      /tns:EXT_SYSTEM_CLEAN_REP_REQUEST/tns:EXT_SYSTEM_CLEAN_REP/tns:HEADERS1/tns:EXT_SYSTEM_CLEAN_HEADER
    Relative path example (nested block reference):
      tns:EXT_DETAILS/tns:EXT_SYSTEM_CLEAN_DETAILS

    Returns dict: block_name -> {aggregate_name, parent_name}
    """
    hierarchy: dict[str, dict] = {}

    for path in data_elements:
        path = path.strip()
        if not path.startswith("/tns:") and not path.startswith("tns:"):
            continue
        # Only process paths that look like block navigation (not field refs)
        if not re.search(r"tns:[A-Z][A-Z0-9_]*/tns:[A-Z][A-Z0-9_]*", path):
            continue

        segments = [_strip_tns(s) for s in re.findall(r"tns:([A-Z][A-Z0-9_]*)", path)]
        if not segments:
            continue

        if path.startswith("/tns:"):
            # Full absolute path: [REQUEST_ROOT, REPORT_NAME, AGG_NAME, BLOCK_NAME, ...]
            # Strip the request root (index 0) and report name (index 1)
            if len(segments) >= 4:
                agg_name = segments[2]
                block_name = segments[3]
                hierarchy[block_name] = {"aggregate_name": agg_name, "parent_name": None}
            # Deeper nesting: segments[4] would be another block under segments[3]
            if len(segments) >= 5:
                for i in range(3, len(segments) - 1, 2):
                    if i + 2 < len(segments):
                        child_agg = segments[i + 1]
                        child_block = segments[i + 2]
                        if child_block not in hierarchy:
                            hierarchy[child_block] = {
                                "aggregate_name": child_agg,
                                "parent_name": segments[i],
                            }
        else:
            # Relative path: AGG_NAME/BLOCK_NAME
            if len(segments) == 2:
                agg_name, block_name = segments
                if block_name not in hierarchy:
                    hierarchy[block_name] = {
                        "aggregate_name": agg_name,
                        "parent_name": None,  # parent resolved below
                    }

    return hierarchy


def parse(rdl_path: Path) -> ParsedRDL:
    content = rdl_path.read_bytes()

    # lxml in recovery mode handles non-namespace root elements gracefully
    parser = etree.XMLParser(recover=True, encoding="utf-8")
    try:
        tree = etree.fromstring(content, parser=parser)
    except Exception:
        # Fallback: strip XML declaration and retry
        text = content.decode("utf-8", errors="replace")
        text = re.sub(r"<\?xml[^?]*\?>", "", text, count=1)
        tree = etree.fromstring(text.encode("utf-8"), parser=parser)

    # --- report-id ---
    report_id_el = tree.find(".//report-id")
    report_name = report_id_el.text.strip() if report_id_el is not None else rdl_path.stem.upper()

    # --- report title: first <data> element whose text is a single-quoted string literal
    #     in the repeat-page-head static-area ---
    report_title = report_name  # fallback
    for static_area in tree.findall(".//static-area"):
        props = static_area.find("properties")
        area_id = props.find("id") if props is not None else None
        if area_id is None or area_id.text != "repeat-page-head":
            continue
        for data_el in static_area.findall(".//data"):
            if data_el.text:
                m = re.match(r"^'([^']+)'$", data_el.text.strip())
                if m and len(m.group(1)) > 3:  # skip short tokens like 'N/A'
                    report_title = m.group(1)
                    break
        break

    # --- collect all <data> element texts ---
    all_data_texts = [
        el.text.strip()
        for el in tree.findall(".//data")
        if el.text and el.text.strip()
    ]

    # --- block hierarchy ---
    block_meta = _parse_block_paths(all_data_texts)

    # --- fields per block: walk the tree associating tns: field refs with their
    #     nearest enclosing block-level container ---
    # Strategy: each block appears as a <data> path; fields referenced AFTER that
    # path in the same container subtree belong to that block.
    # Simpler approach: for each block, collect all tns:FIELD refs from <data>
    # elements within the same ancestor container that declared the block.

    # Build block objects first
    blocks: dict[str, BlockInfo] = {}
    for bname, bmeta in block_meta.items():
        blocks[bname] = BlockInfo(
            name=bname,
            aggregate_name=bmeta["aggregate_name"],
            parent_name=bmeta["parent_name"],
        )

    # Associate fields: scan all <data> texts for tns:FIELD refs.
    # Use the block whose XPath appears most recently before each field ref.
    # Build an ordered list of (position, block_name | field_name, value)
    ordered: list[tuple[int, str, str]] = []
    for i, text in enumerate(all_data_texts):
        text = text.strip()
        # Is this a block path?
        segs = re.findall(r"tns:([A-Z][A-Z0-9_]*)", text)
        if len(segs) >= 2 and (text.startswith("/tns:") or text.startswith("tns:")):
            # Find which block this path declares
            for bname in blocks:
                if segs[-1] == bname or (len(segs) >= 2 and segs[-1] == bname):
                    ordered.append((i, "block", bname))
                    break
        else:
            fields = _extract_tns_fields(text)
            for f in fields:
                ordered.append((i, "field", f))

    # Walk ordered list: assign each field to the most recently declared block
    current_block: Optional[str] = None
    for _, kind, value in ordered:
        if kind == "block":
            current_block = value
        elif kind == "field" and current_block and current_block in blocks:
            if value not in blocks[current_block].fields:
                blocks[current_block].fields.append(value)

    # Wire parent-child relationships
    # Pass 1: explicit parents from absolute paths
    for bname, bmeta in block_meta.items():
        parent = bmeta["parent_name"]
        if parent and parent in blocks:
            blocks[bname].parent_name = parent
            if blocks[bname] not in blocks[parent].children:
                blocks[parent].children.append(blocks[bname])

    # Pass 2: relative-path blocks — find parent by context position in data stream.
    # Walk all_data_texts again tracking the last absolute-path block as context.
    context_block: Optional[str] = None
    for text in all_data_texts:
        text = text.strip()
        segs = re.findall(r"tns:([A-Z][A-Z0-9_]*)", text)
        if not segs:
            continue
        if text.startswith("/tns:") and len(segs) >= 4:
            # Absolute path — update context to the declared block
            context_block = segs[3]
        elif not text.startswith("/tns:") and len(segs) == 2:
            # Relative path: AGG/BLOCK — child of current context
            agg_name, child_name = segs
            if child_name in blocks and context_block and context_block in blocks:
                child = blocks[child_name]
                parent_block = blocks[context_block]
                if child.parent_name is None:
                    child.parent_name = context_block
                    if child not in parent_block.children:
                        parent_block.children.append(child)

    # Find root block (no parent)
    roots = [b for b in blocks.values() if b.parent_name is None]
    if not roots:
        # Fallback: create a synthetic root
        root = BlockInfo(name="REPORT_BLOCK", aggregate_name="DATA", parent_name=None)
        for b in blocks.values():
            root.children.append(b)
        blocks["REPORT_BLOCK"] = root
    else:
        if len(roots) > 1:
            import sys
            names = [r.name for r in roots]
            print(
                f"[rdl_parser] Warning: {len(roots)} unconnected root blocks found: {names}. "
                f"Using {roots[0].name}. The others may have unresolved parent references.",
                file=sys.stderr,
            )
        root = roots[0]

    return ParsedRDL(
        report_name=report_name,
        report_title=report_title,
        root_block=root,
        all_blocks=blocks,
    )
