# Portfolio Redesign — Design Spec

**Date:** 2026-04-03
**File target:** `preview.html` (full rewrite)
**Tech:** Vanilla HTML / CSS / JS — zero dependencies
**Inspiration:** andrewreff.com — layout, animations, typography, mood

---

## Design Decisions

| Dimension | Decision |
|---|---|
| Direction | Cinematic Dark + Typographic Brutalist + Motion Fluid |
| Layout | Split Hero (name/bio left · featured project right) |
| Color | Mono × Red — near-monochrome dark, single `#d42828` red accent |
| Motion | Cursor-magnetic — custom cursor, elements react to mouse |
| Language | EN/FR switcher preserved |

---

## Color System

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#080808` | Page background |
| `--bg-2` | `#0e0e0e` | Card/panel backgrounds |
| `--bg-3` | `#060606` | Footer |
| `--white` | `#ffffff` | Primary text |
| `--white-55` | `rgba(255,255,255,0.55)` | Secondary text |
| `--white-28` | `rgba(255,255,255,0.28)` | Muted text |
| `--white-18` | `rgba(255,255,255,0.18)` | Labels, numbers |
| `--white-08` | `rgba(255,255,255,0.08)` | Borders |
| `--red` | `#d42828` | Single accent — borders, bars, tags, hover |
| `--red-faint` | `rgba(212,40,40,0.08)` | Tag backgrounds |

No gradients. No gold. No multi-color accents. Red is the only color.

---

## Typography

- **Font:** System stack — `system-ui, -apple-system, sans-serif` (no external fonts, fast load)
- **Hero name:** `clamp(5rem, 10vw, 9rem)`, weight 900, tracking `-0.045em`
- **Ghost name line:** `color: transparent`, `-webkit-text-stroke: 1px rgba(255,255,255,0.12)`
- **Section headings:** `clamp(2rem, 4vw, 3.5rem)`, weight 900, tracking `-0.04em`
- **Labels:** `0.62rem`, weight 700, `letter-spacing: 0.25em`, `text-transform: uppercase`
- **Body:** `0.88rem`, weight 400, `line-height: 1.75`
- **Project names:** `1.1rem`, weight 800, tracking `-0.02em`

---

## Cursor System

Custom cursor replaces default. Two layers:
- **Dot** (`8px`, white circle) — follows mouse precisely
- **Ring** (`36px`, 1px white border) — follows with spring lag (`transition: width/height 0.38s cubic-bezier(0.16,1,0.3,1)`)

**State changes:**
- Default: dot visible, ring 36px
- On project hover: ring expands to `80px`, shows `"VIEW →"` label inside, dot hides
- On link hover: ring expands to `48px`, slight border-color shift to red

**Magnetic effect (hero section only):**
- Hero name and featured project card shift subtly based on `mousemove` (max ±8px)
- Formula: `offset = (mousePos - elementCenter) * 0.04`
- Smooth with CSS `transition: transform 0.4s cubic-bezier(0.16,1,0.3,1)`

---

## Sections

### ① Navigation (fixed)

```
[AY]    [Work]  [About]  [Contact]    [● Available]  [EN | FR]
```

- Fixed top, transparent until scroll → `backdrop-filter: blur(18px)` + subtle border
- "Available" pill: red border, red dot with CSS pulse animation
- EN/FR switcher: pill shape, active state highlighted

### ② Hero — Split (100vh)

```
┌─────────────────────┬──────────────────────┐
│ ▌                   │  ┌──────────────────┐ │
│   Product Designer  │  │ ▬▬▬▬▬▬▬▬         │ │
│                     │  │  [Featured]       │ │
│   ABDA              │  │                   │ │
│   LLAH              │  │  Steer            │ │
│                     │  │  Automotive · CPO │ │
│   Based  Morocco    │  └──────────────────┘ │
│   Years  5+ · 8     │                       │
│   Focus  UX·UI·AI   │  Designing products   │
│                     │  that feel intentional│
└─────────────────────┴──────────────────────┘
```

- Red 2px vertical bar on far left of left panel
- Name: top line solid white, second line ghost (stroke only)
- Featured project card: red top-line, dark warm background, "Featured" red pill
- Entire hero is the cursor-magnetic zone
- Load animation: letters slide up through mask staggered, then meta fades in

### ③ About — Brief + Stats

```
┌──────────┬────────────────────────────────────┐
│  ABOUT ↕ │  I work at the intersection of     │
│          │  UX and UI design...               │
│       02 │  [5+] Years  [8] Startups  [3] Ind │
└──────────┴────────────────────────────────────┘
```

- Brutalist left sidebar: vertical "About" label + oversized ghost section number
- Right: 2-line bio (English/French versions) + 3 stats
- Stats: large bold numbers, small uppercase labels

### ④ Work — Numbered List

```
Selected Work ──────────────────────── 07 Projects
▌ 01  Steer              [Case Study]  2022–2024  →
  02  Konnect            [Case Study]  2023       →
  03  Fissa3             [Case Study]  2023       →
  04  Groupado           [Project]     2023       →
  05  UnDrive            [Project]     2023       →
  06  Fixerloop          [Project]     2023       →
  07  PharmaDrive        [Project]     2023       →
```

- Hover: red 2px left bar appears, row shifts `8px` right, cursor expands to "VIEW →"
- Case studies tagged in red; other projects in grey
- All rows link out (Behance or case study URL)

### ⑤ Contact — Split

```
┌────────────────────┬───────────────────────────┐
│  Get in touch      │  [Email →]                │
│                    │  [LinkedIn →]             │
│  Let's work        │  [Behance →]              │
│  together.         │                           │
│                    │                           │
│  Open to freelance │                           │
│  projects...       │                           │
└────────────────────┴───────────────────────────┘
```

- Left: heading with ghost "together." in stroke type
- Right: 3 link cards (email, LinkedIn, Behance) with hover shift + red arrow

### ⑥ Footer

```
© 2025 Abdallah Yaackoubi · All rights reserved    [Behance] [LinkedIn] [CV]
```

- Minimal, `#060606` background, very muted text

---

## Animations

### Load sequence (on DOMContentLoaded)
1. `t=0` — nav fades in
2. `t=150ms` — eyebrow label fades up
3. `t=300ms` — hero name letters slide up through mask, staggered 40ms per letter
4. `t=900ms` — meta rows fade in (staggered)
5. `t=1100ms` — right panel reveals (fade + slight translateX)
6. `t=1300ms` — red accent bar draws down (scaleY 0→1)

### Scroll reveals
- `IntersectionObserver` triggers on each section
- Elements: `opacity: 0; transform: translateY(24px)` → `opacity: 1; transform: none`
- Transition: `0.8s cubic-bezier(0.16, 1, 0.3, 1)`
- Stagger children with `transition-delay`

### Hover interactions
- Project rows: `transform: translateX(8px)` on hover, red left-bar opacity 0→1
- Contact links: `transform: translateX(5px)` on hover
- Nav links: `color` transition 0.2s

---

## EN/FR Language Switcher

- All copy has `data-en` and `data-fr` attributes
- `setLang(lang)` function swaps all `data-{lang}` values into `textContent`
- Active button highlighted, persisted to `localStorage`

---

## Project Data

| # | Name | Type | Industry | Link target |
|---|---|---|---|---|
| 01 | Steer | Case Study | Automotive | Behance/Notion |
| 02 | Konnect | Case Study | Fintech | Behance/Notion |
| 03 | Fissa3 | Case Study | Food Delivery | Behance/Notion |
| 04 | Groupado | Project | Social | Behance/Notion |
| 05 | UnDrive | Project | Automotive | Behance/Notion |
| 06 | Fixerloop | Project | Services | Behance/Notion |
| 07 | PharmaDrive | Project | Pharmacy | Behance/Notion |

Featured project in hero: **Steer** (most prominent case study, CPO role).

---

## What Changes vs Current `preview.html`

| Current | New |
|---|---|
| Dark navy `#06080f` | Near-black `#080808` |
| Gold + Red accents | Red only (`#d42828`) |
| Full-width hero, name at bottom | Split hero, 50/50 grid |
| Project list rows (existing) | Same structure, red hover discipline |
| Services section | Removed — replaced by About with stats |
| Marquee | Removed — adds noise, reduces focus |
| Services grid | Removed |
| Breathing glow orbs | Removed |

---

## Out of Scope

- Individual case study pages (Approach 2) — future work
- Framework migration — stays vanilla HTML
- CMS or dynamic data
