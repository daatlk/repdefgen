"""repdefgen CLI entry points."""

import sys
from pathlib import Path

import click

INDEX_DIR = Path(".repdefgen/index")

TRIGGER_ADVANCE = {"generate", "done", "proceed"}
TRIGGER_EXIT = {"done", "exit"}


@click.group()
def main():
    """RepDefGen — generate IFS Report Definition Packages from Report Layouts."""


# ---------------------------------------------------------------------------
# repdefgen index
# ---------------------------------------------------------------------------

@main.command()
@click.argument("build_home", type=click.Path(exists=True, file_okay=False, path_type=Path))
def index(build_home: Path):
    """Build the Codebase Index from BUILD_HOME (.api/.apy/.view files)."""
    from repdefgen.indexer import build_index

    if INDEX_DIR.exists():
        rebuild = click.confirm(
            f".repdefgen/index/ already exists. Rebuild from scratch?", default=True
        )
        if not rebuild:
            click.echo("Skipping index build.")
            return

    click.echo(f"Indexing {build_home} ...")
    file_count, chunk_count = build_index(build_home, INDEX_DIR)
    click.echo(f"Done. Indexed {file_count} files → {chunk_count} chunks stored in {INDEX_DIR}")


# ---------------------------------------------------------------------------
# repdefgen generate
# ---------------------------------------------------------------------------

@main.command()
@click.argument("layout_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output-dir", "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("."),
    show_default=True,
    help="Directory to write generated files into.",
)
def generate(layout_file: Path, output_dir: Path):
    """Generate .rdf and .report from LAYOUT_FILE (.rdl or .rep) using the Codebase Index."""
    from repdefgen import retriever
    from repdefgen.generator import Meta, apply_correction, generate_files, propose_field_list, SYSTEM_PROMPT
    from repdefgen.session import Session

    # Check index exists
    if not INDEX_DIR.exists():
        click.echo(
            "Error: no Codebase Index found at .repdefgen/index/. "
            "Run `repdefgen index <build-home>` first.",
            err=True,
        )
        sys.exit(1)

    # --- Parse layout file (.rdl or .rep) ---
    suffix = layout_file.suffix.lower()
    if suffix == ".rep":
        from repdefgen import rep_parser as layout_parser
    elif suffix == ".rdl":
        from repdefgen import rdl_parser as layout_parser
    else:
        click.echo(f"Error: unsupported file type '{suffix}'. Expected .rdl or .rep.", err=True)
        sys.exit(1)

    click.echo(f"Parsing {layout_file} ...")
    parsed = layout_parser.parse(layout_file)
    click.echo(f"  Report: {parsed.report_name}")
    click.echo(f"  Title:  {parsed.report_title}")
    for bname, binfo in parsed.all_blocks.items():
        click.echo(f"  Block:  {bname} ({len(binfo.fields)} visible fields)")

    has_real_blocks = any(b.name != "REPORT_BLOCK" for b in parsed.all_blocks.values())
    if not has_real_blocks:
        click.echo(
            "Warning: no blocks extracted from the .rdl. "
            "The block hierarchy may use a format not yet handled.\n"
        )
        click.echo(
            "Please describe the block structure manually.\n"
            "Enter one block per line as: BLOCK_NAME [parent=PARENT_BLOCK_NAME]\n"
            "Example:  EXT_SYSTEM_CLEAN_HEADER\n"
            "          EXT_SYSTEM_CLEAN_DETAILS parent=EXT_SYSTEM_CLEAN_HEADER\n"
            "Press Enter on an empty line when done.\n"
        )
        parsed.all_blocks.clear()
        from repdefgen.rdl_parser import BlockInfo
        while True:
            line = click.prompt("Block", default="", show_default=False).strip()
            if not line:
                break
            parts = line.split()
            bname = parts[0].upper()
            parent = None
            for p in parts[1:]:
                if p.lower().startswith("parent="):
                    parent = p.split("=", 1)[1].upper()
            bi = BlockInfo(name=bname, aggregate_name=bname, parent_name=parent)
            parsed.all_blocks[bname] = bi
            if parent and parent in parsed.all_blocks:
                parsed.all_blocks[parent].children.append(bi)
            elif parent is None:
                parsed.root_block = bi

    # --- Interactive metadata ---
    click.echo("")
    lu_name = click.prompt("LU name (e.g. ExtSysClean)")
    module = click.prompt("Module (e.g. WO)")
    description = click.prompt("Brief description of what this report covers")

    meta = Meta(
        lu_name=lu_name,
        module=module,
        title=parsed.report_title,
        report_name=parsed.report_name,
    )

    # --- RAG retrieval ---
    all_fields = [f for b in parsed.all_blocks.values() for f in b.fields]
    click.echo("\nQuerying Codebase Index ...")
    chunks = retriever.query(all_fields, description, INDEX_DIR, n=12)
    click.echo(f"  Retrieved {len(chunks)} relevant code chunks.")

    # --- Generation Session ---
    session = Session(system_prompt=SYSTEM_PROMPT)

    # --- Field List proposal ---
    click.echo("\nProposing Field List ...\n")
    proposal = propose_field_list(parsed, chunks, session)
    click.echo(proposal)

    # --- Field List review loop ---
    click.echo(
        "\n--- Field List Review ---\n"
        "Correct the field list in natural language. "
        "Type 'generate', 'proceed', or 'done' when ready.\n"
    )
    field_list = proposal
    while True:
        user_input = click.prompt("").strip()
        trigger = user_input.lower().strip()

        if trigger in TRIGGER_ADVANCE:
            break

        if trigger == "exit":
            click.echo("Exiting.")
            sys.exit(0)

        # Send correction to Claude
        correction_reply = session.send(
            f"Update the field list based on this correction: {user_input}\n\n"
            "Show the complete updated Field List.",
            max_tokens=4096,
        )
        click.echo("\n" + correction_reply + "\n")
        field_list = correction_reply

    # --- Generate files ---
    click.echo("\nGenerating files ...\n")
    written = generate_files(field_list, parsed, meta, chunks, session, output_dir)

    if not written:
        click.echo("Error: no files were extracted from the generation response.", err=True)
        sys.exit(1)

    for filename, path in written.items():
        click.echo(f"  Written: {path}")

    # --- Correction loop ---
    click.echo(
        "\n--- Correction Loop ---\n"
        "Request SQL corrections in natural language. "
        "Type 'done' or 'exit' to finish.\n"
    )
    while True:
        user_input = click.prompt("").strip()
        trigger = user_input.lower().strip()

        if trigger in TRIGGER_EXIT:
            break

        written = apply_correction(user_input, session, written)
        click.echo("  Correction applied.")
        for filename, path in written.items():
            if filename.endswith(".rdf"):
                click.echo(f"  Updated: {path}")

    click.echo("\nDone. Generated files:")
    for filename, path in written.items():
        click.echo(f"  {path}")
