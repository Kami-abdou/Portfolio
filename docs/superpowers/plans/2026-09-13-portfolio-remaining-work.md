# Portfolio — remaining work

Written 2026-09-13, after the gallery-led IA landed (`95cf37f`).

Ordered by effect on getting hired, not by effort. Each item says who can
do it, because roughly a third of this list is blocked on information only
Abdou has and no amount of engineering substitutes for it.

---

## 0. The site is not published — and never has been

**Blocking everything below. Owner decision required.**

This was misdiagnosed twice during the session. First reading: "the live
site predates the restructure." Second: "push to the right branch." Both
wrong. The actual state, verified 2026-09-13:

| check | result |
|---|---|
| `kami-abdou.github.io/Portfolio/` | **HTTP 404** |
| `kami-abdou.github.io/Portfolio/index.html` | **HTTP 404** |
| `kami-abdou.github.io/` (user root) | **HTTP 404** |
| body served | GitHub's own `Site not found · GitHub Pages` |
| `github.com/Kami-abdou` (account) | 200 — exists, 1 public repo |
| `github.com/Kami-abdou/Portfolio` | **404 — the repo is private** |

The earlier "the live homepage lacks 'Selected case studies'" finding was
a grep against that 404 page, not against an older deploy.

GitHub Pages does not serve private repositories on the free plan. So the
site has never been published, and 54 local commits describe a site no one
can visit.

**Three ways out, owner's call:**

1. **Make the repo public.** Free, unblocks Pages immediately, and has a
   second payoff: project 09 (`This portfolio`) currently has no link
   because the source is private. A public repo makes the strongest claim
   on the site — "I built this" — checkable by a stranger.

   **Audited before recommending this, because publishing history cannot
   be undone.** Results:

   - **No credentials.** No AWS keys, API tokens, bearer tokens or private
     keys in the working tree or in any commit across all branches. Every
     `token` hit is a design token.
   - **Two `notes/` files ARE in history** — `notes/BUILD.md` and
     `notes/generate-markdown.py`, removed from tracking in `b6b2619`
     ("Untrack notes/ scaffolding") but still reachable from HEAD. An
     earlier draft of this document claimed `notes/` had never been
     committed. That was wrong.
     - Read in full: neither is candid. `BUILD.md` is a build brief; the
       only notable line is *"Paste this whole file into Claude Code"*,
       which discloses the site was AI-assisted. Given the site now
       advertises an AI-assisted build practice in its bio and toolkit,
       that is on-brand rather than damaging.
     - The genuinely candid notes — `notes/TODOS.md` and
       `notes/REMOVED-LINKS.md` — have **zero** commits touching them and
       are not in history at all.
   - **`site/_src/portrait.jpg` and `site/_src/profile.png` are in
     history** (committed in `342b658`, untracked in `f50a177`). Full-
     resolution personal photographs, not sensitive.
   - Nothing under `projects/*/assets/_src/` has ever been committed.
   - Only one email address appears anywhere: the public contact address
     already published on the site.

   **Conclusion: safe to publish.** If the two `notes/` files are still
   unwanted, they must be purged from history (`git filter-repo`) *before*
   going public — flipping the switch first makes them permanently
   archivable by third parties.
2. **Upgrade to GitHub Pro**, keep the repo private, enable Pages.
3. **Host elsewhere** — Netlify, Vercel, Cloudflare Pages all serve a
   static folder from a private repo on free tiers.

If the final URL is not `https://kami-abdou.github.io/Portfolio`, then
`site.json -> url` must change with it: it is baked into every canonical
tag, every `og:image`, and `sitemap.xml`. One edit, one rebuild.

---

## 1. Not one outcome on the site is attributable to Abdou

**Owner must supply. Highest value on this list.**

Nine projects, and every metric is an *input* — scope, headcount, duration:

```
1 — me                     Design and product team
15 people                  Interviewed in person
82                         Screens designed
356                        Icons drawn, across 17 categories
8 months                   Time on the project
8                          Pages designed
```

The only genuine outcome numbers anywhere are project 09's, and they are
about the website itself (41 tests, 0 dependencies, 7.3 KB of JS).

Konnect is the sharpest case: it lists $1.5M raised, a Central Bank
licence and ~4% of Tunisia's online payments, then disowns all of it in
the same paragraph — *"What the company did afterwards is not my work."*
Full verification burden, zero credit claimed.

For comparison, mikes.cv opens a project with *"With over 6 million users
but plateauing engagement, I led the design of three retention-focused
features."* Same sentence length. Completely different claim.

**Needed: one true sentence per project** — what measurably changed
because he was there. Small and internal beats nothing ("cut sign-up from
7 steps to 4"; "the component library replaced three team-local button
sets"). These cannot be invented, inferred, or written by an agent.

---

## 2. Reasoning is absent; only process is shown

**Can be drafted once §1 exists.**

Searched all case-study content for trade-offs, rejected alternatives,
constraints, "instead of", "didn't work", "what I'd do differently".
No hit constitutes a design decision. Captions name artefacts rather than
findings — `"Survey results."`, `"User journey."`, `"Competitor analysis."`

mikes.cv does this in one sentence, three times per page:

> "Tracking this many created confusion, and users couldn't distinguish
> species. One colour per animal would overwhelm and become unscalable,
> so they were grouped by biome: savanna, jungle, tundra, ocean."

Problem → rejected alternative → *why* → decision. His project pages are
~280 words. Not long-form; dense.

Apply to Steer and Konnect, the two remaining case studies. The voice
already exists on the site — InstaDeep's captions prove it: *"Enterprise —
the same router, argued to a buyer instead of an engineer."*

---

## 3. Nothing is corroborated by another human

**Owner must obtain; template work is mine.**

Zero testimonials, references or quotes site-wide, and the template has no
support for them (0 hits for `testimonial` / `blockquote` in `build.py`
and `styles.css`). For someone whose central claim is repeatedly "I was
the only designer", one line from the Steer founder or the Konnect CTO
moves more than any other single addition.

Client names (Tunisie Telecom, Renault, Hyphen, Hive, Inspire, Cha9a9a)
were deliberately excluded and the owner reaffirmed that on 2026-09-13.
Worth revisiting once, since it is the cheapest credibility available and
both comparison sites lead with client names.

---

## 4. Claims that outrun the evidence

**Mine, but each needs a decision: add the screens, or soften the copy.**

| claim | state |
|---|---|
| Steer: "designed the identity, the corporate site and **the dashboard**" | no dashboard image exists in its 18 assets |
| Steer: "It still runs on the brand I built" | no logo, palette or type anywhere |
| Steer: the one external link | *"The site has been redesigned since I left"* — it shows someone else's work |
| Konnect: Platforms `iOS, Android, Web`, "rebuilt the application end to end" | not one mobile screen on the page |
| Konnect: "established a design system, and designed the final brand" | neither shown |
| Konnect | its single product screenshot does quadruple duty: cover, outcome image, og:image, lightbox |
| PharmaDrive | shipped screens contain **Lorem ipsum**, and a French typo: "Télécharger votre ordonnoce" |

---

## 5. Conversion

**Mixed ownership.**

- **Reachability.** Location reads "Tunis, Tunisia" with no remote,
  relocation or authorisation signal. For EU/US roles this is the largest
  silent filter on the site. The owner chose a neutral contact line on
  2026-09-13 (employed, no job-search signal) — that decision stands, but
  a *reachability* line is not a job-search signal and would cost one
  sentence.
- **The CV.** Internal PDF `/Title` is `CV-Abdallah Yaackoubi` while the
  site brands him Abdou. It is a Figma export, so text extracts as glyph
  garbage and will parse badly in any ATS. Dated 24 Aug — predates this
  entire restructure. **Owner must re-export.**
- **CV placement.** Footer-only. Absent from the homepage contact band,
  i.e. missing at the moment of intent. *Mine.*
- **`mailto` prefill.** mikes.cv uses
  `?subject=So, about your portfolio...`. Ours is a bare mailto. *Mine.*
- **No `404.html`.** *Mine.*

---

## 6. Positioning is now stated but thinly evidenced

The 2026-09-13 rewrite added a "Build and AI workflow" toolkit group and a
bio paragraph. Before it, the site contained **zero** occurrences of code,
build, AI workflow, Cursor or Claude.

Two gaps remain:

- **The toolkit list was inferred, not confirmed.** Claude Code is
  evidenced; Git and HTML/CSS/JS are evidenced by this repo; MCP was
  inferred from connected servers. Needs the owner's sign-off, and
  extending with anything actually used (Cursor, v0, n8n, Make).
- **No interaction artefact exists.** Zero `.gif/.mp4/.webm`, zero
  `<video>`/`<iframe>` across the whole site. The hero stakes out
  interaction design — *"how a thing responds, what it does while it
  waits, and how it recovers"* — and then shows static screens. One
  states-and-edge-cases study of any real flow would close it.

---

## 7. Content debt

*Mine, low value, do last.*

- Seven `TODO` fields render as absent rows (correct behaviour, but they
  are blanks a reader may notice): smarthub duration/team/year,
  pharmadrive duration/team, fixerloop duration.
- InstaNovo is a `TODO` stub. The page promises three product surfaces and
  shows two. **Owner must supply screens.**
- Four projects still have no outbound link: fissa3, pharmadrive,
  smarthub, portfolio. Smarthub's own status is "not launched yet" while
  its card reads "Founder" — that reads as padding; decide whether to
  launch it or reframe it as a self-initiated brand exercise.
- The `viewer` component is now dead code site-wide (~50 lines of Python
  plus CSS and tablist JS). Kept deliberately in case a future case study
  wants it.
- Gallery pages still carry case-study furniture: the facts table and the
  reading-progress bar.

---

## Suggested order

1. §0 — publish. Everything else is theatre until this is done.
2. §1 — nine sentences from the owner.
3. §4 — the InstaDeep links are already in (`95cf37f`); soften or
   substantiate the Steer and Konnect claims.
4. §2 — Fahlo-format reasoning blocks for Steer and Konnect.
5. §3 and §5 — one testimonial, the CV, the small conversion wins.
6. §7 — cleanup.

Steps 1 and 2 are blocked on the owner. Step 3 onward is executable.
