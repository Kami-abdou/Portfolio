# Portfolio IA restructure — design

**Date:** 2026-09-07
**Status:** approved (design), pending plan
**Repo:** `Portfolio/` (branch `Portfolio0.1`)

## Problem

Ten projects are presented at near-equal weight across two homepage bands
(6 "Case studies" + 4 "Other projects"). Three consequences:

1. **No entry point.** A visitor cannot tell which three projects are the
   argument and which seven are the evidence. Ten equal doors means the
   visitor picks one at random or leaves.
2. **Time cost.** Every project page uses the full case-study template, so
   every project reads like a 500-word commitment — including UnDrive, which
   has 3 sections, and Smarthub, which has 5.
3. **Mispositioning.** `heroStatement`, `currently` and `metaDescription` all
   lead with AI at InstaDeep. The `tagline` already says "six years across AI,
   fintech, food delivery, automotive retail and developer tools" — the hero
   contradicts the breadth the rest of the site claims.

Constraint from the owner: **nothing is cut.** All eleven projects stay
reachable. The fix is hierarchy, not deletion.

## Approach

Two visual tiers on the homepage. All pages kept. Tier-2 pages rendered
through a lighter template that skips process narrative without deleting it.

```
HOMEPAGE
┌────────────┐ ┌────────────┐ ┌────────────┐
│   STEER    │ │  KONNECT   │ │ INSTADEEP  │   ← 3-up, card--lg
│ case study │ │ case study │ │ highlights │
└────────────┘ └────────────┘ └────────────┘
Other work
┌────┐ ┌────┐ ┌────┐
│Fixe│ │Fiss│ │Grou│                            ← 3-up, plain .card
└────┘ └────┘ └────┘
┌────┐ ┌────┐ ┌────┐
│Phar│ │UnDr│ │Smar│
└────┘ └────┘ └────┘
9 pages · 11 projects
```

Rejected alternatives: cutting the weak projects (owner wants everything
included); a single flat grid with better copy (does not solve "which three
matter"); collapsing Tier 2 into a text list (throws away the visual work,
which is the point of a design portfolio).

---

## §1 Homepage structure

`site.json.sections` is rekeyed:

| from | to | slugs |
|---|---|---|
| `caseStudies` | `highlights` | `steer`, `konnect`, `instadeep` |
| `otherProjects` | `selectedWork` | `fixerloop`, `fissa3`, `groupado`, `pharmadrive`, `undrive`, `smarthub` |

Headings: "Selected case studies" and "Other work".

**Steer leads, not InstaDeep.** Convention is current-role-first, but a CPO
role at a non-AI company in the first card answers the positioning problem
before the visitor reads a word of copy. One array reorder to reverse.

**Column counts change.** `build.py:596` hardcodes `--cols: 2` for the large
band and `4` for the small one. Three large cards at 2-up leaves an orphan;
six small cards at 4-up leaves two. Both bands become `--cols: 3`. This is
the only layout arithmetic in the change.

### Correction to an earlier claim

I previously said both bands render `card card--lg` and that a new `card--sm`
variant was needed. **Both were wrong.** `build.py:482` already takes
`large` and emits `card card--lg` or bare `card`; `styles.css:147-148`
already splits `grid--lg`/`grid--sm`. The compact variant exists and is in
use today. No new CSS class is required — only the `--cols` values above.

## §2 The InstaDeep entry

New `projects/10-instadeep/` with `slug: instadeep`. One page, three highlight
blocks: **DeepPCB**, **Design System**, **InstaNovo**. `projects/00-deeppcb/`
and `projects/09-design-system/` are absorbed; `deeppcb.html` and
`design-system.html` cease to exist.

Assets move rather than being re-exported — including the protected
`_src/` originals and `09-design-system/assets/components/`, which is
populated by an `autoImages` directive rather than an explicit `images[]`
list and must keep its folder name relative to the new project root.

**InstaNovo has no content or assets in the repo.** Owner is supplying
screens. The section ships as a stub with `"body": "TODO — InstaNovo"` and
no `images`. `build.py:838` drops exactly that shape — a section is live only
if `usable(body) or images` — so the page renders complete with two blocks
until the screens land, then the block appears with no template change.
(The drop rule keys on `body`/`images`, not on the heading; a TODO heading
alone would still render a bare `<h2>`.)

**Honest scoping note:** all 8 DeepPCB assets are marketing-site pages, not
the routing product UI. This entry can truthfully claim "the product
surfaces and the system behind them" — it cannot claim "I designed an AI
routing engine." If routing-tool UI exists elsewhere, the story improves
substantially.

## §3 Tier-2 page treatment — non-destructive

Add `"format": "highlights"` to the six Tier-2 `content.json` files.
`build.py` branches on it and renders: cover → summary → images → metrics →
links, skipping `sections[].body` prose.

**No copy is deleted.** The narrative stays in the JSON and is simply not
rendered. Removing one field restores the full page. This matters because
Fixerloop carries 11 sections and 22 images and is a candidate for future
promotion to Tier 1.

**`category` must be reconciled.** `build.py:863` renders the per-page
eyebrow as `'Case study' if project['category'] == 'case-study' else
'Project'`. Konnect, Fissa3 and Groupado are all currently `case-study`;
Fissa3 and Groupado move to Tier 2. Left alone, their pages would announce
"Case study" while the homepage files them under "Other work". The eyebrow
should derive from tier (`format`), not from the now-redundant `category`
field. Fixerloop's `category: "project"` mislabel dissolves in the same
change.

## §4 At-a-glance card metadata

Each card gains one line — `2021–23 · Automotive retail · CPO` — so domain
and seniority land without a click.

**This needs a new field.** `year` cannot be reused: values are long prose
("January 2024 — present", "October 2021 — November 2023") and both UnDrive
and Smarthub are literal `"TODO"`. A short `"meta"` string per project,
subject to the existing `usable()` rule so it vanishes when unset, keeps
this additive and safe.

## §5 Hero repositioning

| field | from | to |
|---|---|---|
| `heroStatement` | "I design AI products at InstaDeep — interfaces that make a machine's decisions legible to the people who act on them." | "Six years designing products across fintech, automotive retail and AI — from first research to shipped interface." |
| `currently` | "Senior product designer at InstaDeep, designing AI products." | "Senior product designer at InstaDeep." |
| `metaDescription` | "Senior product designer at InstaDeep, specialising in AI products. Six years across fintech, delivery, automotive retail and developer tools." | "Senior product designer. Fintech, automotive retail, food delivery and AI." |

AI becomes one item in a list instead of the headline. `contactLede` and
`about[2]` carry the same "specialising in AI products" phrasing and should
be reviewed for consistency.

Copy is the owner's voice; treat all three as drafts to overwrite.

## Cost and blast radius

- **9 project pages** (was 10), **11 sitemap URLs** (was 12).
- **Two URLs die:** `projects/deeppcb.html`, `projects/design-system.html`.
  Exactly two places reference them, both in `site.json`: line 29
  (`experience[0].projects`, which generates the two links at
  `about.html:80-81`) and lines 93-94 (`sections.caseStudies.slugs`). Both
  become `["instadeep"]` / `"instadeep"`. No HTML is hand-edited — `about.html`
  is generated. Being static, the repo has no redirect mechanism; neither URL
  is externally linked, so none is needed.
- `build.py:998` prints the homepage counts from the two old section keys and
  breaks on rename.
- No new dependencies. No build step at runtime. `file://` still works.

## Out of scope

Noted, not included:

- 6 `projects/*/assets/share.jpg` are `og:image` targets but untracked and
  not gitignored — they will 404 on GitHub Pages and break every link
  preview. Fix is `git add`. **Unrelated to this change and worth doing
  first.**
- `site/profile.avif` untracked (degrades gracefully).
- 8 remaining `TODO` placeholders, including UnDrive and Smarthub `year`.
- `projects/09-design-system/assets/cover.full.jpg`, a pre-existing orphan.
