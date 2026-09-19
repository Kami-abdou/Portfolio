# Tool icons

Drop a file here named after the tool, lowercased, spaces as hyphens:

    figma.png  creative-cloud.png  claude-code.png  notion.svg

`build.py` finds it automatically — no code change. It tries `.svg`, then
`.png`, then `.webp`. A tool with no matching file falls back to a monogram
set in the site's own type.

## The plate is automatic — do not set it by hand

This page is `#0A0A0B`, and brand marks come in both polarities. Measured
against the page background:

| mark           | on the page | on a white plate |
|----------------|-------------|------------------|
| MCP            | 14.91:1     | 1.20:1           |
| Git            | 12.35:1     | 1.46:1           |
| Creative Cloud | 10.15:1     | 1.77:1           |
| Notion         |  8.86:1     | 2.03:1           |
| Figma          |  2.06:1     | 8.74:1           |
| VWO            |  2.38:1     | 7.56:1           |

Both directions fail silently. Framer shipped on the live site at 1.06:1 —
an empty chip — and nobody noticed until it was measured.

So `icon_needs_plate()` in build.py averages the luminance of each icon's
opaque pixels and adds `.tool__icon--plate` only when contrast against the
page drops below 3:1. Swap a file and the build re-decides. The mark itself
is never recoloured: vendor terms generally forbid altering it, so the only
thing we change is what sits behind it.

Store icons as **PNG or SVG**. The detector decodes PNG; a WEBP is accepted
by the lookup but cannot be measured, so convert it first:

    sips --resampleWidth 96 -s format png in.webp --out assets/tools/slug.png

## Getting clean files

Take them from the vendor's brand or press page. Do **not** screenshot a
transparent PNG out of a preview pane — three files supplied that way had
the editor's transparency checkerboard baked into opaque pixels, which
renders as a grey checked square. Jira, MCP and Git all arrived like this;
the Jira one was replaced, MCP and Git are still on monograms.

Check before committing:

    python3 -c "import sys;sys.path.insert(0,'.');from build import icon_needs_plate;\
    from pathlib import Path;p=Path('assets/tools/x.png');print('plate:',icon_needs_plate(p))"

## Wordmarks

The slot is 18x18. VWO's logo is 3:1 — `object-fit: contain` keeps it
undistorted but it renders about 18x6 and reads as a shape, not a word.
Prefer a vendor's standalone symbol where one exists.
