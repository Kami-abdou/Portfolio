# Tool icons

Drop a file here named after the tool, lowercased, spaces as hyphens:

    figma.svg  framer.png  claude-code.png  illustrator.svg

`build.py` picks them up automatically — no code change needed. It tries
`.svg`, then `.png`, then `.webp`. Any tool without a matching file falls
back to a monogram in the site's own type.

## Two things that will bite you

**This page is #0A0A0B, and most brand marks are drawn for white.**
Measured contrast of the marks as vendors ship them:

| mark            | contrast vs the page |
|-----------------|----------------------|
| Jira            | 13.33:1              |
| Claude          | 6.46:1               |
| VWO             | 2.44:1               |
| Figma app tile  | 2.05:1               |
| Framer          | 1.06:1 — invisible   |

So `.tool__icon` puts every mark on a light plate. The mark itself is never
recoloured or redrawn: vendor terms generally forbid altering it, and a
hand-tweaked logo looks worse than no logo. Change what sits behind it,
not the mark.

**The slot is 18x18, so wordmarks do not work.** VWO's logo is 1.67:1 —
at 18px square it is an unreadable smear. Use a vendor's standalone symbol
where one exists, or leave it on the monogram.

## Getting clean files

Take them from the vendor's brand or press page and follow the usage terms.
Do not screenshot a transparent PNG from a preview pane — the supplied Jira
file had the editor's transparency checkerboard baked into opaque pixels,
which renders as a grey checked square.
