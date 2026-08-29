# Abdou Yaackoubi — portfolio

Static site. Plain HTML, CSS and JavaScript — no framework, no npm, no build
step at runtime and no CDN. Open `index.html` directly, or drop the folder on
any static host as-is.

## Rebuilding after a content change

```bash
python3 build.py
```

That's the whole workflow. Edit the JSON, run the command, commit the result.

## How it fits together

```
site.json                 bio, contact links, homepage grouping and order
tokens.json               colours, type scale, spacing — the design system
projects/NN-slug/
  content.json            one case study
  assets/*.png            screens and process artefacts
build.py                  reads the JSON, writes the HTML
assets/
  tokens.css              GENERATED from tokens.json — never edit by hand
  styles.css              the stylesheet; consumes tokens only
  lightbox.js             full-size image viewer
index.html  about.html  projects/<slug>.html      <- generated output
```

The JSON is read **at build time, not in the browser.** `fetch()` is blocked
on `file://` in Chrome, so a site that loaded its own JSON at runtime would
break the moment someone double-clicked `index.html`. Baking it in keeps the
site working from the filesystem and from a server.

Generated files are committed on purpose — the site has to work for anyone who
clones the repo without running Python first.

## Adding a screen to a project

Drop the file in that project's `assets/`, add an entry to the relevant
section's `images` array, and re-run the build:

```json
{ "src": "assets/09-checkout.png",
  "alt": "Checkout screen showing the payment summary",
  "caption": "Checkout." }
```

Nothing is hardcoded to image counts or grid positions, so no layout work is
needed. `alt` is required — it's what screen readers announce, and it's already
written for every existing image.

## Editing the role list

`site.json` -> `roles` drives the hero. The first three become the scrolling
rows of the marquee wall; all of them appear in the hidden `<h1>` that
carries the page's accessible heading.

Scroll speed lives in `build.py`, in the `wall()` helper:

```python
'<div class="wall__row wall__row--%s" style="--dur: %ds">'
% ("rev" if idx % 2 else "fwd", 58 + idx * 10, ...)
#                                ^^        ^^
#                          base seconds   per-row stagger
```

Raise the base to slow every row. Keep the stagger non-zero — rows have
different track lengths, so equal durations would let them drift into
alignment and read as one moving block instead of three bands.

Adding a fourth role does not add a fourth row; change `roles[:3]` in the
hero builder if you want more.

## Conventions worth keeping

**`tokens.json` is the only place styling values live.** `styles.css` contains
no colour or spacing literals; it references custom properties. Changing the
accent everywhere is a one-line edit.

**`TODO` values are skipped automatically.** Any field whose value starts with
`TODO` is left out of the facts table, so placeholders never ship. The `todo`
arrays in the JSON are internal notes and are never rendered.

**Image dimensions are read from the PNG headers** at build time and written as
`width`/`height` attributes, so the page doesn't reflow as images load. Very
tall exports (over 2200px) are capped at `70vh` and marked `data-tall`; click
one to open it at full size in the lightbox.

## Known gaps

Some projects are missing screens — a Figma export hit a rate limit partway
through. Affected: Konnect, Groupado, Fixerloop, PharmaDrive. Adding them is
the image workflow above; no code changes required.

`tokens.json` is a sensible scaffold rather than values extracted from the
Figma file — see the `_note` field inside it. Worth replacing with the real
tokens when the Figma limit resets.

## Accessibility

Semantic landmarks, one `<h1>` per page, visible focus rings, a skip link, and
a lightbox that closes on Escape and keeps focus inside while open. Reduced
motion is respected. Dark mode follows the system setting via
`prefers-color-scheme`.
