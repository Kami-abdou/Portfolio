# Tool icons

Drop a file here named after the tool, lowercased, spaces as hyphens:

    figma.png  creative-cloud.png  claude-code.png  notion.svg

`build.py` finds it automatically — no code change. It tries `.svg`, then
`.png`, then `.webp`. A tool with no matching file falls back to a monogram
set in the site's own type.

## The plate is automatic — do not set it by hand

The page is dark, and brand marks come in both polarities. Measured
against it, every mark currently shipped, worst first — the three above the
rule get a plate, the rest must not:

| mark                 | on the page | on a white plate |
|----------------------|-------------|------------------|
| mcp.png              |   1.03:1    | 20.35:1          |
| framer.png           |   1.07:1    | 21.00:1          |
| midjourney.svg       |   1.07:1    | 21.00:1          |
| ·················    | ··········· | ················ |
| sketch.png           |   4.73:1    |  4.16:1          |
| git.png              |   4.94:1    |  3.99:1          |
| jira.png             |   5.00:1    |  3.94:1          |
| claude-code.png      |   6.38:1    |  3.09:1          |
| protopie.png         |   7.53:1    |  2.62:1          |
| google-analytics.svg |   7.63:1    |  2.58:1          |
| miro.png             |   9.05:1    |  2.18:1          |
| figma.svg            |   9.40:1    |  2.10:1          |
| notion.png           |   9.69:1    |  2.03:1          |
| creative-cloud.png   |   9.98:1    |  1.97:1          |
| vwo.svg              |  12.41:1    |  1.59:1          |

Both directions fail silently. Framer shipped on the live site at 1.03:1 —
an empty chip — and nobody noticed until it was measured.

This table has gone stale twice, which is worth knowing before you trust
it. The figures above were regenerated from `icon_needs_plate()` over the
files on disk; do that rather than editing a row by hand.

So `icon_needs_plate()` in build.py averages the luminance of each icon's
opaque pixels and adds `.tool__icon--plate` only when contrast against the
page drops below 3:1. Swap a file and the build re-decides. The mark itself
is never recoloured: vendor terms generally forbid altering it, so the only
thing we change is what sits behind it.

Store icons as **PNG or SVG**. Both are measured: PNG by averaging the
luminance of its opaque pixels, SVG by averaging the colours it declares in
`fill`/`stroke`. A WEBP is accepted by the lookup and cannot be measured, so
convert it first:

    sips --resampleWidth 96 -s format png in.webp --out assets/tools/slug.png

Two file shapes read as measurable and are not. **A palette PNG** (colour
type 3) is skipped by the decoder — ProtoPie's download arrived as one and
reported no ink at all. **An SVG whose colour is in a `prefers-color-scheme`
media query** measures as the average of both polarities, and worse, it
follows the OS rather than this site's own theme toggle: Sketch's favicon
does exactly that, which is why the tile is shipped instead. A test fails
the build if any icon in this directory cannot be measured.

## Getting clean files

Take them from the vendor's brand or press page. Do **not** screenshot a
transparent PNG out of a preview pane — three files supplied that way had
the editor's transparency checkerboard baked into opaque pixels, which
renders as a grey checked square. Jira, MCP and Git all arrived like this.

Jira was re-supplied clean. MCP and Git were recovered with a border
flood-fill: light pixels *reachable from the edge* become transparent, so
the checkerboard goes and the mark stays. It has to be a border fill, not a
colour key — Git's mark has white INSIDE it (the branch glyph on the red
diamond) and a colour key punches a hole through the logo. The script is in
the commit for `git.png`/`mcp.png` if it is ever needed again.

Check before committing:

    python3 -c "import sys;sys.path.insert(0,'.');from build import icon_needs_plate;\
    from pathlib import Path;p=Path('assets/tools/x.png');print('plate:',icon_needs_plate(p))"

## Wordmarks

The slot is 18x18, so a wordmark loses. VWO shipped as a 96x32 lockup —
`object-fit: contain` kept it undistorted and rendered it about 18x6, a
smear rather than a word. It is their standalone bird symbol now.
Prefer a vendor's symbol over its logotype every time.
