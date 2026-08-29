# Build brief — Abdallah Yaackoubi portfolio

Paste this whole file into Claude Code, with this folder as the working directory.

---

## What you're building

A static portfolio site for a UX/UI designer. **Plain HTML, CSS and JavaScript. No framework, no build step, no npm.** It has to open by double-clicking `index.html` and it has to be hostable on any static host as-is.

All content already exists as JSON in this folder. Do not write copy. Do not invent projects. Read the JSON and render it.

## What's in this folder

```
site.json                     bio, contact, section ordering
tokens.json                   colours, type scale, spacing — the design system
generate-markdown.py          regenerates the .md files from JSON; don't touch
site/profile.png              portrait
site/CV-Abdallah-Yaackoubi.pdf
projects/
  01-steer/
    content.json              structured case study
    case-study.md             same thing as prose (generated — read only)
    assets/*.png              screens and process artefacts
  02-konnect/  03-fissa3/  04-groupado/
  05-pharmadrive/  06-fixerloop/  07-undrive/  08-smarthub/
```

## content.json schema

Every project file has this shape:

| field | type | notes |
|---|---|---|
| `slug` | string | URL segment, e.g. `steer` |
| `order` | number | display order, 1–8 |
| `category` | `"case-study"` \| `"project"` | drives which homepage section it lands in |
| `title` | string | |
| `tagline` | string | one line, shown under the title |
| `summary` | string | 2–3 sentences, used on cards and as the meta description |
| `role`, `client`, `year`, `duration`, `team`, `status` | string | render as a facts table; **skip any whose value starts with `TODO`** |
| `tags`, `platforms`, `tools` | string[] | |
| `links` | `{label, url}[]` | may be empty |
| `metrics` | `{label, value}[]` | may be empty; render `value` large, `label` small |
| `cover` | string | path relative to the project folder |
| `sections` | `{id, heading, body, images[]}[]` | the body of the page |
| `images` | `{src, alt, caption}[]` | `src` is relative to the project folder |
| `todo` | string[] | **internal. never render this on the site.** |

`site.json` carries the bio, the contact links, and `sections.caseStudies.slugs` / `sections.otherProjects.slugs`, which define homepage grouping and order. Trust those arrays over the folder numbering.

## Pages

**`index.html`** — hero with name, title, tagline and the "currently" line. Then "Case studies" (4 projects, large cards, cover image + title + tagline). Then "Other projects I'm proud of" (4 projects, smaller cards). Then contact.

**`about.html`** — portrait, the `about` paragraphs, a link to the CV, contact links.

**`projects/<slug>.html`** — one per project, 8 total. Title, tagline, summary, facts table, metrics row, links, then each section as a heading + prose + its images with captions underneath. Previous/next navigation at the foot, following `order`.

## How to handle the data

There is no server, and `fetch()` on `file://` is blocked by CORS in Chrome — so **do not fetch the JSON at runtime.** Write a small Python or Node script that reads the JSON and writes the static HTML files, and commit both the script and its output. The site then works from the filesystem and from any host, and regenerating after a content edit is one command.

Put the generator at `build.py` and document it in a short `README.md`.

## Design direction

Use `tokens.json` as CSS custom properties in `:root`. Do not hardcode colours or spacing anywhere else.

This is a designer's portfolio, so restraint reads as competence. Generous whitespace. One accent colour, used sparingly. Type does the work — a real scale, tight leading on headings, `1.6` on body. Prose column capped at `--prose-width` (68ch) even when images run wider.

Images are the content. Full-bleed or near-full-bleed within the container, `loading="lazy"` on everything below the fold, `width` and `height` attributes set so nothing reflows. Several screens are very tall (4000px) — cap their display height with `max-height` and `object-fit: cover; object-position: top`, and make clicking one open the full image in a lightbox. Write the lightbox yourself in ~30 lines; do not add a library.

Dark mode via `prefers-color-scheme` if it's cheap. Skip it rather than doing it badly.

## Non-negotiables

- No frameworks, no npm, no CDN dependencies. Everything local.
- `tokens.json` is the single source of truth for styling.
- Never render `todo` arrays, and skip any field whose value starts with `TODO`.
- Every `<img>` gets the `alt` text from the JSON. It's already written; use it.
- Semantic HTML — `<main>`, `<article>`, `<figure>`/`<figcaption>`, one `<h1>` per page.
- Keyboard accessible: visible focus rings, lightbox closes on Escape and traps focus.
- Per-page `<title>`, meta description from `summary`, and Open Graph tags using `cover`.
- Mobile first. Test at 375px before anything else.

## Known gaps

Some projects are missing screens — the Figma export hit a rate limit partway through. Affected: Konnect (4 more desktop screens), Groupado (6), Fixerloop (10), PharmaDrive (~24). Build so that adding an image to a section's `images` array and re-running the generator is the only step needed. Don't hardcode image counts or grid positions.
