# Portfolio Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full rewrite of `preview.html` — split hero, mono × red palette, cursor-magnetic interactions, fully responsive across 9 target viewports.

**Architecture:** Single self-contained HTML file with all CSS in `<style>` and all JS in `<script>`. Mobile-first CSS (base = 360px), upgraded at `768px` (tablet) and `1024px` (desktop). No build tools, no dependencies.

**Tech Stack:** Vanilla HTML5, CSS3 (custom properties, clamp, grid, IntersectionObserver), vanilla JS (ES6).

**Spec:** `docs/superpowers/specs/2026-04-03-portfolio-redesign-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `preview.html` | **Full rewrite** | Entire portfolio — markup, styles, scripts |

---

## Task 1: Foundation — HTML skeleton + CSS variables

**Files:**
- Rewrite: `preview.html`

- [ ] **Step 1: Wipe preview.html and write the base skeleton**

Replace the entire contents of `preview.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Abdallah Yaackoubi — Product Designer</title>
  <style>

    /* ── CUSTOM PROPERTIES ── */
    :root {
      --bg:        #080808;
      --bg-2:      #0e0e0e;
      --bg-3:      #060606;
      --white:     #ffffff;
      --w55:       rgba(255,255,255,0.55);
      --w28:       rgba(255,255,255,0.28);
      --w18:       rgba(255,255,255,0.18);
      --w08:       rgba(255,255,255,0.08);
      --w04:       rgba(255,255,255,0.04);
      --red:       #d42828;
      --red-faint: rgba(212,40,40,0.08);
      --red-border:rgba(212,40,40,0.25);
      --ease-out:  cubic-bezier(0.16, 1, 0.3, 1);
      --max-w:     1400px;
      --pad-x:     max(24px, 6vw);
    }

    /* ── RESET ── */
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
    html { scroll-behavior: smooth; font-size: 16px; }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--white);
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }
    a { text-decoration: none; color: inherit; }
    img { display: block; max-width: 100%; }
    button { border: none; background: none; cursor: pointer; font: inherit; }

  </style>
</head>
<body>

  <!-- content goes here -->

  <script>
    // scripts go here
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify in browser**

Open `preview.html` in browser. Expected: blank black page, no console errors, `document.title` is "Abdallah Yaackoubi — Product Designer".

- [ ] **Step 3: Commit**

```bash
git add preview.html
git commit -m "init: portfolio foundation — HTML skeleton and CSS custom properties"
```

---

## Task 2: Navigation

**Files:**
- Modify: `preview.html` — add nav HTML inside `<body>`, add nav CSS inside `<style>`, add scroll JS inside `<script>`

- [ ] **Step 1: Add nav HTML** (inside `<body>`, before `<!-- content goes here -->`)

```html
<!-- NAV -->
<nav class="nav" id="nav">
  <div class="nav-inner">
    <span class="nav-logo">AY</span>
    <div class="nav-links">
      <a href="#work"    data-en="Work"    data-fr="Travaux">Work</a>
      <a href="#about"   data-en="About"   data-fr="À propos">About</a>
      <a href="#contact" data-en="Contact" data-fr="Contact">Contact</a>
    </div>
    <div class="nav-right">
      <span class="nav-avail">
        <span class="avail-dot"></span>
        <span data-en="Available" data-fr="Disponible">Available</span>
      </span>
      <div class="lang-switcher">
        <button class="lang-btn active" id="btn-en" onclick="setLang('en')">EN</button>
        <button class="lang-btn"        id="btn-fr" onclick="setLang('fr')">FR</button>
      </div>
    </div>
  </div>
</nav>
```

- [ ] **Step 2: Add nav CSS** (inside `<style>`, after the reset block)

```css
/* ── NAV ── */
.nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  transition: background 0.4s, backdrop-filter 0.4s, border-color 0.4s;
  border-bottom: 1px solid transparent;
}
.nav.scrolled {
  background: rgba(8,8,8,0.88);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border-bottom-color: var(--w08);
}
.nav-inner {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 20px var(--pad-x);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.nav-logo {
  font-size: 0.72rem; font-weight: 800;
  letter-spacing: 0.22em; text-transform: uppercase;
  color: var(--w55);
}
.nav-links {
  display: none; /* hidden on mobile, shown on tablet+ */
  gap: 28px;
}
.nav-links a {
  font-size: 0.68rem; color: var(--w28);
  letter-spacing: 0.14em; text-transform: uppercase;
  transition: color 0.2s;
}
.nav-links a:hover { color: var(--white); }
.nav-right { display: flex; align-items: center; gap: 14px; }

.nav-avail {
  display: flex; align-items: center; gap: 6px;
  font-size: 0.65rem; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--red);
  border: 1px solid var(--red-border);
  border-radius: 999px; padding: 5px 12px;
}
.avail-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--red);
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.35; }
}

.lang-switcher {
  display: flex; border: 1px solid var(--w08); border-radius: 999px; overflow: hidden;
}
.lang-btn {
  font-size: 0.62rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--w28); padding: 6px 12px;
  transition: color 0.2s, background 0.2s;
}
.lang-btn.active  { color: var(--white); background: var(--w08); }
.lang-btn:hover:not(.active) { color: var(--w55); }

/* Tablet+ nav links */
@media (min-width: 768px) {
  .nav-links { display: flex; }
}
```

- [ ] **Step 3: Add scroll JS** (inside `<script>`)

```js
// Nav scroll state
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 40);
}, { passive: true });
```

- [ ] **Step 4: Verify in browser**

Open `preview.html`. Expected:
- Nav visible at top with AY logo, Available pill, EN/FR buttons
- At mobile width (360px): nav links hidden
- At 768px+: Work / About / Contact links visible
- Scroll down → nav gets frosted glass background

- [ ] **Step 5: Commit**

```bash
git add preview.html
git commit -m "feat: navigation — fixed nav with scroll state, available pill, lang switcher"
```

---

## Task 3: Custom Cursor

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add cursor HTML** (first elements inside `<body>`, before nav)

```html
<!-- CURSOR (desktop only) -->
<div class="cursor-dot"  id="cursorDot"></div>
<div class="cursor-ring" id="cursorRing"></div>
```

- [ ] **Step 2: Add cursor CSS**

```css
/* ── CURSOR ── */
@media (hover: hover) {
  body { cursor: none; }
  a, button, [data-cursor] { cursor: none; }
}

.cursor-dot, .cursor-ring {
  position: fixed; top: 0; left: 0; z-index: 9999;
  border-radius: 50%; pointer-events: none;
  transform: translate(-50%, -50%);
}
.cursor-dot {
  width: 7px; height: 7px;
  background: var(--white);
  transition: opacity 0.2s, width 0.2s, height 0.2s;
}
.cursor-ring {
  width: 34px; height: 34px;
  border: 1px solid rgba(255,255,255,0.28);
  transition:
    width  0.38s var(--ease-out),
    height 0.38s var(--ease-out),
    border-color 0.25s,
    background 0.25s;
  display: flex; align-items: center; justify-content: center;
}

/* States */
.cursor-dot.hidden   { opacity: 0; }
.cursor-ring.on-link {
  width: 46px; height: 46px;
  border-color: var(--red-border);
}
.cursor-ring.on-project {
  width: 80px; height: 80px;
  border-color: rgba(255,255,255,0.18);
  background: rgba(255,255,255,0.04);
}
.cursor-ring.on-project::after {
  content: 'VIEW →';
  font-size: 0.58rem; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: rgba(255,255,255,0.85);
}

/* Hide on touch devices */
@media (hover: none) {
  .cursor-dot, .cursor-ring { display: none; }
}
```

- [ ] **Step 3: Add cursor JS**

```js
// Custom cursor
const cursorDot  = document.getElementById('cursorDot');
const cursorRing = document.getElementById('cursorRing');
let ringX = 0, ringY = 0, mouseX = 0, mouseY = 0;

// Only activate on hover-capable devices
if (window.matchMedia('(hover: hover)').matches) {
  document.addEventListener('mousemove', e => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    cursorDot.style.left = mouseX + 'px';
    cursorDot.style.top  = mouseY + 'px';
  }, { passive: true });

  // Ring follows with spring lag via rAF
  function animateRing() {
    ringX += (mouseX - ringX) * 0.12;
    ringY += (mouseY - ringY) * 0.12;
    cursorRing.style.left = ringX + 'px';
    cursorRing.style.top  = ringY + 'px';
    requestAnimationFrame(animateRing);
  }
  animateRing();

  // Cursor state management
  function setCursorState(state) {
    cursorDot.classList.toggle('hidden',     state === 'project');
    cursorRing.classList.toggle('on-link',   state === 'link');
    cursorRing.classList.toggle('on-project',state === 'project');
  }

  document.addEventListener('mouseover', e => {
    const el = e.target.closest('[data-cursor="project"]');
    const lk = e.target.closest('a, button');
    if (el)      setCursorState('project');
    else if (lk) setCursorState('link');
    else         setCursorState('default');
  });
}
```

- [ ] **Step 4: Verify in browser** (desktop, not mobile)

Move mouse around page. Expected:
- Small white dot follows precisely
- Ring follows with slight spring lag
- No cursor state changes yet (no projects/links with data-cursor yet)

- [ ] **Step 5: Commit**

```bash
git add preview.html
git commit -m "feat: custom cursor — dot + ring with spring lag, touch device detection"
```

---

## Task 4: Hero Section — HTML + Static CSS

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add hero HTML** (after nav)

```html
<!-- HERO -->
<section class="hero" id="hero">
  <div class="hero-inner">

    <!-- LEFT: name + meta -->
    <div class="hero-left">
      <div class="hero-top">
        <p class="hero-eyebrow" data-en="Product Designer · Freelance" data-fr="Designer Produit · Freelance">
          Product Designer · Freelance
        </p>
        <h1 class="hero-name" id="heroName">
          <span class="name-line solid" id="nameLine1"></span>
          <span class="name-line ghost" id="nameLine2"></span>
        </h1>
      </div>
      <div class="hero-meta" id="heroMeta">
        <div class="hero-meta-row">
          <span class="meta-label" data-en="Based"  data-fr="Basé">Based</span>
          <span class="meta-val"   data-en="Tunisia" data-fr="Tunisie">Tunisia</span>
        </div>
        <div class="hero-meta-row">
          <span class="meta-label" data-en="Years"  data-fr="Expérience">Years</span>
          <span class="meta-val"   data-en="5+ years · 8 startups" data-fr="5+ ans · 8 startups">5+ years · 8 startups</span>
        </div>
        <div class="hero-meta-row">
          <span class="meta-label" data-en="Focus"  data-fr="Focus">Focus</span>
          <span class="meta-val"   data-en="UX · UI · AI Workflows" data-fr="UX · UI · IA">UX · UI · AI Workflows</span>
        </div>
      </div>
    </div>

    <!-- RIGHT: featured project + description -->
    <div class="hero-right" id="heroRight">
      <a href="#" class="hero-featured" data-cursor="project" id="heroFeatured">
        <div class="featured-top-bar"></div>
        <span class="featured-badge" data-en="Featured" data-fr="En vedette">Featured</span>
        <div class="featured-body">
          <p class="featured-label" data-en="Case Study — 01" data-fr="Étude de cas — 01">Case Study — 01</p>
          <h2 class="featured-title">Steer</h2>
          <p class="featured-sub"   data-en="Automotive · Chief Product Officer" data-fr="Automobile · Chief Product Officer">Automotive · Chief Product Officer</p>
        </div>
      </a>
      <div class="hero-desc-block">
        <p class="hero-desc"
           data-en="Designing digital products that feel intentional — from UX strategy to polished interfaces and AI-enhanced workflows."
           data-fr="Concevoir des produits numériques qui ont du sens — de la stratégie UX aux interfaces soignées et aux workflows IA.">
          Designing digital products that feel intentional — from UX strategy to polished interfaces and AI-enhanced workflows.
        </p>
      </div>
    </div>

  </div>
</section>
```

- [ ] **Step 2: Add hero CSS**

```css
/* ── HERO ── */
.hero {
  min-height: 100svh;
  padding-top: 72px; /* nav height */
  background: var(--bg);
}
.hero-inner {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 0 var(--pad-x);
  min-height: calc(100svh - 72px);
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding-top: 40px;
  padding-bottom: 48px;
}

/* LEFT */
.hero-left {
  display: flex; flex-direction: column; gap: 32px;
  position: relative;
}
.hero-left::before {
  content: '';
  position: absolute; left: calc(-1 * var(--pad-x)); top: 0; bottom: 0;
  width: 2px;
  background: linear-gradient(to bottom, var(--red) 0%, transparent 100%);
}
.hero-eyebrow {
  font-size: 0.62rem; font-weight: 700;
  letter-spacing: 0.3em; text-transform: uppercase;
  color: var(--w18);
  opacity: 0; /* animated in Task 5 */
}
.hero-name {
  line-height: 0.88;
  letter-spacing: -0.045em;
}
.name-line {
  display: block;
  font-size: clamp(3.5rem, 14vw, 9rem);
  font-weight: 900;
}
.name-line.solid { color: var(--white); }
.name-line.ghost {
  color: transparent;
  -webkit-text-stroke: 1px rgba(255,255,255,0.12);
}

/* META */
.hero-meta {
  display: flex; flex-direction: column; gap: 10px;
  opacity: 0; /* animated in Task 5 */
}
.hero-meta-row { display: flex; align-items: baseline; gap: 12px; }
.meta-label {
  font-size: 0.6rem; font-weight: 700;
  letter-spacing: 0.2em; text-transform: uppercase;
  color: var(--w18); min-width: 52px;
}
.meta-val { font-size: 0.8rem; color: var(--w55); }

/* RIGHT */
.hero-right {
  display: flex; flex-direction: column; gap: 0;
  border: 1px solid var(--w08); border-radius: 10px; overflow: hidden;
  opacity: 0; /* animated in Task 5 */
}

.hero-featured {
  display: block; position: relative;
  background: #0d0a0a;
  padding: 28px 24px 24px;
  min-height: 200px;
  display: flex; flex-direction: column; justify-content: flex-end;
  transition: background 0.3s;
}
.hero-featured:hover { background: #120c0c; }

.featured-top-bar {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--red) 0%, transparent 70%);
  transform: scaleX(0); transform-origin: left;
  /* animated in Task 5 */
}
.featured-badge {
  position: absolute; top: 16px; right: 16px;
  font-size: 0.6rem; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--red); border: 1px solid var(--red-border);
  background: var(--red-faint); border-radius: 999px; padding: 3px 10px;
}
.featured-body { position: relative; z-index: 1; }
.featured-label {
  font-size: 0.6rem; letter-spacing: 0.2em; text-transform: uppercase;
  color: var(--w18); margin-bottom: 8px;
}
.featured-title {
  font-size: clamp(1.8rem, 4vw, 2.6rem);
  font-weight: 900; letter-spacing: -0.03em; color: var(--white);
}
.featured-sub {
  font-size: 0.68rem; color: var(--w28);
  letter-spacing: 0.1em; text-transform: uppercase; margin-top: 6px;
}

.hero-desc-block {
  padding: 20px 24px;
  border-top: 1px solid var(--w08);
  background: var(--bg-2);
}
.hero-desc {
  font-size: 0.82rem; color: var(--w28); line-height: 1.75;
}

/* DESKTOP: side-by-side split */
@media (min-width: 1024px) {
  .hero-inner {
    flex-direction: row;
    align-items: stretch;
    gap: 0;
    padding-top: 0;
    padding-bottom: 0;
  }
  .hero-left {
    flex: 0 0 46%;
    justify-content: space-between;
    padding: 60px 48px 60px 0;
    border-right: 1px solid var(--w08);
  }
  .hero-left::before {
    left: calc(-1 * var(--pad-x));
  }
  .hero-eyebrow { font-size: 0.65rem; }
  .name-line { font-size: clamp(5rem, 8.5vw, 9rem); }

  .hero-right {
    flex: 1;
    border-radius: 0; border: none;
    border-left: none;
    display: grid;
    grid-template-rows: 1fr auto;
    opacity: 1; /* override; desktop handles this differently */
  }
  .hero-featured {
    min-height: unset;
    flex: 1;
    padding: 48px 40px 36px;
  }
  .hero-desc-block { padding: 28px 40px; }
}

/* TABLET */
@media (min-width: 768px) and (max-width: 1023px) {
  .hero-inner { flex-direction: row; gap: 0; padding-top: 0; padding-bottom: 0; }
  .hero-left {
    flex: 0 0 44%;
    justify-content: space-between;
    padding: 48px 36px 48px 0;
    border-right: 1px solid var(--w08);
  }
  .hero-right {
    flex: 1; border-radius: 0; border: none; border-left: none;
    display: grid; grid-template-rows: 1fr auto;
  }
  .hero-featured { flex: 1; }
}
```

- [ ] **Step 3: Verify layout** (no animations yet, that's Task 5)

Open `preview.html`. Expected:
- Mobile (360px): stacked — name then featured card below, no red bar
- Tablet (768px): side-by-side split, name left, featured card right
- Desktop (1366px): full split, eyebrow and meta visible, hero fills viewport height

- [ ] **Step 4: Commit**

```bash
git add preview.html
git commit -m "feat: hero section — split layout, name lines, featured project card"
```

---

## Task 5: Hero Load Animations

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add animation CSS** (inside `<style>`)

```css
/* ── HERO ANIMATIONS ── */
@keyframes slideUp {
  from { transform: translateY(110%); }
  to   { transform: translateY(0); }
}
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes barDraw {
  from { transform: scaleX(0); }
  to   { transform: scaleX(1); }
}

.letter-wrap {
  display: inline-block; overflow: hidden;
  vertical-align: bottom; line-height: 1;
}
.letter {
  display: inline-block;
  animation: slideUp 0.65s var(--ease-out) both;
}
```

- [ ] **Step 2: Add hero animation JS** (inside `<script>`, after cursor code)

```js
// Hero load animation sequence
function initHeroAnimation() {
  const line1El  = document.getElementById('nameLine1');
  const line2El  = document.getElementById('nameLine2');
  const eyebrow  = document.querySelector('.hero-eyebrow');
  const heroMeta = document.getElementById('heroMeta');
  const heroRight= document.getElementById('heroRight');
  const topBar   = document.querySelector('.featured-top-bar');

  const line1 = 'ABDALLAH';
  const line2 = 'YAACKOUBI';

  // Build letter spans
  function buildLetters(el, text, baseDelay) {
    el.innerHTML = '';
    [...text].forEach((ch, i) => {
      const wrap = document.createElement('span');
      wrap.className = 'letter-wrap';
      const letter = document.createElement('span');
      letter.className = 'letter';
      letter.textContent = ch === ' ' ? '\u00A0' : ch;
      letter.style.animationDelay = (baseDelay + i * 40) + 'ms';
      wrap.appendChild(letter);
      el.appendChild(wrap);
    });
  }

  // t=300ms — name letters
  setTimeout(() => {
    buildLetters(line1El, line1, 0);
    buildLetters(line2El, line2, 80);
  }, 300);

  // t=150ms — eyebrow
  setTimeout(() => {
    eyebrow.style.animation = 'fadeUp 0.6s var(--ease-out) forwards';
  }, 150);

  // t=900ms — meta rows
  setTimeout(() => {
    heroMeta.style.animation = 'fadeUp 0.7s var(--ease-out) forwards';
  }, 900);

  // t=1100ms — right panel
  setTimeout(() => {
    heroRight.style.animation = 'fadeIn 0.6s ease forwards';
  }, 1100);

  // t=1300ms — red top bar
  setTimeout(() => {
    topBar.style.animation = 'barDraw 0.5s var(--ease-out) forwards';
  }, 1300);
}

document.addEventListener('DOMContentLoaded', initHeroAnimation);
```

- [ ] **Step 3: Verify animation sequence**

Open `preview.html` and watch. Expected order:
1. Nav appears immediately
2. ~150ms: eyebrow fades up
3. ~300ms: "ABDALLAH" letters slide up one by one, then "YAACKOUBI"
4. ~900ms: meta rows fade up as a group
5. ~1100ms: right panel fades in
6. ~1300ms: red top bar draws left-to-right on the featured card

- [ ] **Step 4: Commit**

```bash
git add preview.html
git commit -m "feat: hero load animation — letter slide-up, staggered reveals"
```

---

## Task 6: Hero Magnetic Effect + Cursor Project State

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add magnetic CSS** (inside `<style>`)

```css
/* ── MAGNETIC ── */
.hero-name, #heroFeatured {
  transition: transform 0.4s var(--ease-out);
  will-change: transform;
}
```

- [ ] **Step 2: Add magnetic JS** (inside `<script>`, after hero animation code)

```js
// Hero magnetic effect (desktop only)
function initMagnetic() {
  if (!window.matchMedia('(hover: hover)').matches) return;

  const hero     = document.getElementById('hero');
  const heroName = document.querySelector('.hero-name');
  const featured = document.getElementById('heroFeatured');

  hero.addEventListener('mousemove', e => {
    const rect = hero.getBoundingClientRect();
    const cx = rect.left + rect.width  / 2;
    const cy = rect.top  + rect.height / 2;
    const dx = (e.clientX - cx) * 0.04;
    const dy = (e.clientY - cy) * 0.04;

    heroName.style.transform = `translate(${dx}px, ${dy}px)`;
    // featured card moves slightly less
    featured.style.transform = `translate(${dx * 0.5}px, ${dy * 0.5}px)`;
  }, { passive: true });

  hero.addEventListener('mouseleave', () => {
    heroName.style.transform  = '';
    featured.style.transform  = '';
  });
}

document.addEventListener('DOMContentLoaded', initMagnetic);
```

- [ ] **Step 3: Verify magnetic effect**

On desktop, move mouse around the hero. Expected:
- Hero name shifts subtly (max ~8px) following the cursor
- Featured card shifts half as much
- Snaps back smoothly on mouse leave
- No effect on touch / mobile

- [ ] **Step 4: Verify cursor project state**

Hover over the featured project card. Expected:
- Cursor ring expands to 80px
- "VIEW →" text appears inside ring
- White dot disappears

- [ ] **Step 5: Commit**

```bash
git add preview.html
git commit -m "feat: hero magnetic effect and cursor project state"
```

---

## Task 7: About Section

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add about HTML** (after the hero section)

```html
<!-- ABOUT -->
<section class="about" id="about">
  <div class="about-inner">
    <div class="about-sidebar">
      <span class="about-sidebar-label">About</span>
      <span class="about-sidebar-num" aria-hidden="true">02</span>
    </div>
    <div class="about-content reveal">
      <p class="about-text">
        <span data-en="I work at the intersection of" data-fr="Je travaille à l'intersection de">I work at the intersection of</span>
        <strong data-en="UX and UI design" data-fr="l'UX et l'UI design">UX and UI design</strong>.
        <span data-en="Things that make me excited: user-centered design, interaction design, and creating interfaces that feel" data-fr="Ce qui m'anime : le design centré utilisateur, le design d'interaction, et créer des interfaces qui donnent l'impression d'être">Things that make me excited: user-centered design, interaction design, and creating interfaces that feel</span>
        <span class="about-red" data-en="fun and human." data-fr="fun et humaines.">fun and human.</span>
      </p>
      <div class="about-stats">
        <div class="stat">
          <span class="stat-num">5+</span>
          <span class="stat-label" data-en="Years" data-fr="Ans">Years</span>
        </div>
        <div class="stat">
          <span class="stat-num">8</span>
          <span class="stat-label" data-en="Startups" data-fr="Startups">Startups</span>
        </div>
        <div class="stat">
          <span class="stat-num">3</span>
          <span class="stat-label" data-en="Industries" data-fr="Industries">Industries</span>
        </div>
      </div>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Add about CSS**

```css
/* ── ABOUT ── */
.about { border-top: 1px solid var(--w08); }
.about-inner {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 0 var(--pad-x);
  display: grid;
  grid-template-columns: 1fr;
}
.about-sidebar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 0 12px;
  border-bottom: 1px solid var(--w08);
}
.about-sidebar-label {
  font-size: 0.6rem; font-weight: 700;
  letter-spacing: 0.28em; text-transform: uppercase;
  color: var(--w18);
}
.about-sidebar-num {
  font-size: 1.8rem; font-weight: 900;
  color: rgba(255,255,255,0.04); letter-spacing: -0.05em;
}
.about-content { padding: 32px 0 48px; }
.about-text {
  font-size: clamp(1rem, 2vw, 1.35rem);
  font-weight: 400; line-height: 1.65;
  color: var(--w55); letter-spacing: -0.01em;
}
.about-text strong { color: var(--white); font-weight: 800; }
.about-red { color: var(--red); }
.about-stats {
  display: flex; gap: 32px; margin-top: 32px;
  padding-top: 24px; border-top: 1px solid var(--w08);
}
.stat-num {
  display: block;
  font-size: clamp(2rem, 4vw, 3rem);
  font-weight: 900; letter-spacing: -0.04em; color: var(--white);
  line-height: 1;
}
.stat-label {
  display: block; margin-top: 4px;
  font-size: 0.6rem; font-weight: 700;
  letter-spacing: 0.2em; text-transform: uppercase; color: var(--w18);
}

/* Desktop sidebar layout */
@media (min-width: 1024px) {
  .about-inner { grid-template-columns: 120px 1fr; }
  .about-sidebar {
    flex-direction: column; align-items: flex-start; justify-content: space-between;
    padding: 48px 0; border-bottom: none; border-right: 1px solid var(--w08);
  }
  .about-sidebar-label {
    writing-mode: vertical-rl; transform: rotate(180deg); letter-spacing: 0.22em;
  }
  .about-sidebar-num { font-size: 3rem; }
  .about-content { padding: 48px 0 48px 48px; }
}
```

- [ ] **Step 3: Verify**

Expected:
- Mobile: "About" label and number horizontal, then bio text below
- Desktop: sidebar with vertical "About" text + ghost "02", content to the right
- Stats row appears below bio

- [ ] **Step 4: Commit**

```bash
git add preview.html
git commit -m "feat: about section — sidebar layout, bio, stats"
```

---

## Task 8: Work Section

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add work HTML** (after about section)

```html
<!-- WORK -->
<section class="work" id="work">
  <div class="work-inner">
    <div class="work-header reveal">
      <span class="section-label" data-en="Selected Work" data-fr="Travaux sélectionnés">Selected Work</span>
      <span class="work-count">07</span>
    </div>
    <div class="project-list">

      <a href="#" class="project-row reveal" data-cursor="project">
        <span class="pr-num">01</span>
        <div class="pr-info">
          <span class="pr-name">Steer</span>
          <span class="pr-sub" data-en="Automotive · Chief Product Officer" data-fr="Automobile · Chief Product Officer">Automotive · Chief Product Officer</span>
        </div>
        <div class="pr-tags">
          <span class="pr-tag tag-red" data-en="Case Study" data-fr="Étude de cas">Case Study</span>
          <span class="pr-tag tag-grey">2022–2024</span>
        </div>
        <span class="pr-arrow">→</span>
      </a>

      <a href="#" class="project-row reveal" data-cursor="project">
        <span class="pr-num">02</span>
        <div class="pr-info">
          <span class="pr-name">Konnect</span>
          <span class="pr-sub" data-en="Fintech · Lead Designer" data-fr="Fintech · Lead Designer">Fintech · Lead Designer</span>
        </div>
        <div class="pr-tags">
          <span class="pr-tag tag-red" data-en="Case Study" data-fr="Étude de cas">Case Study</span>
          <span class="pr-tag tag-grey">2023</span>
        </div>
        <span class="pr-arrow">→</span>
      </a>

      <a href="#" class="project-row reveal" data-cursor="project">
        <span class="pr-num">03</span>
        <div class="pr-info">
          <span class="pr-name">Fissa3</span>
          <span class="pr-sub" data-en="Food Delivery · UX/UI Design" data-fr="Livraison · Design UX/UI">Food Delivery · UX/UI Design</span>
        </div>
        <div class="pr-tags">
          <span class="pr-tag tag-red" data-en="Case Study" data-fr="Étude de cas">Case Study</span>
          <span class="pr-tag tag-grey">2023</span>
        </div>
        <span class="pr-arrow">→</span>
      </a>

      <a href="#" class="project-row reveal" data-cursor="project">
        <span class="pr-num">04</span>
        <div class="pr-info">
          <span class="pr-name">Groupado</span>
          <span class="pr-sub" data-en="Social · UI Design" data-fr="Social · Design UI">Social · UI Design</span>
        </div>
        <div class="pr-tags">
          <span class="pr-tag tag-grey" data-en="Project" data-fr="Projet">Project</span>
          <span class="pr-tag tag-grey">2023</span>
        </div>
        <span class="pr-arrow">→</span>
      </a>

      <a href="#" class="project-row reveal" data-cursor="project">
        <span class="pr-num">05</span>
        <div class="pr-info">
          <span class="pr-name">UnDrive</span>
          <span class="pr-sub" data-en="Automotive · Web Design" data-fr="Automobile · Design Web">Automotive · Web Design</span>
        </div>
        <div class="pr-tags">
          <span class="pr-tag tag-grey" data-en="Project" data-fr="Projet">Project</span>
          <span class="pr-tag tag-grey">2023</span>
        </div>
        <span class="pr-arrow">→</span>
      </a>

      <a href="#" class="project-row reveal" data-cursor="project">
        <span class="pr-num">06</span>
        <div class="pr-info">
          <span class="pr-name">Fixerloop</span>
          <span class="pr-sub" data-en="Services · UX/UI Design" data-fr="Services · Design UX/UI">Services · UX/UI Design</span>
        </div>
        <div class="pr-tags">
          <span class="pr-tag tag-grey" data-en="Project" data-fr="Projet">Project</span>
          <span class="pr-tag tag-grey">2023</span>
        </div>
        <span class="pr-arrow">→</span>
      </a>

      <a href="#" class="project-row reveal" data-cursor="project">
        <span class="pr-num">07</span>
        <div class="pr-info">
          <span class="pr-name">PharmaDrive</span>
          <span class="pr-sub" data-en="Pharmacy · Mobile Design" data-fr="Pharmacie · Design Mobile">Pharmacy · Mobile Design</span>
        </div>
        <div class="pr-tags">
          <span class="pr-tag tag-grey" data-en="Project" data-fr="Projet">Project</span>
          <span class="pr-tag tag-grey">2023</span>
        </div>
        <span class="pr-arrow">→</span>
      </a>

    </div>
  </div>
</section>
```

- [ ] **Step 2: Add work CSS**

```css
/* ── WORK ── */
.work { border-top: 1px solid var(--w08); }
.work-inner {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 0 var(--pad-x);
}
.work-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 0 16px;
  border-bottom: 1px solid var(--w08);
}
.section-label {
  font-size: 0.6rem; font-weight: 700;
  letter-spacing: 0.28em; text-transform: uppercase; color: var(--w18);
}
.work-count {
  font-size: 0.68rem; color: var(--w18); letter-spacing: 0.1em;
}
.project-list { display: flex; flex-direction: column; }

.project-row {
  display: grid;
  grid-template-columns: 28px 1fr auto 20px;
  align-items: center;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid var(--w04);
  position: relative;
  transition: transform 0.35s var(--ease-out);
}
.project-row::before {
  content: '';
  position: absolute; left: calc(-1 * var(--pad-x)); top: 0; bottom: 0;
  width: 2px; background: var(--red);
  opacity: 0; transition: opacity 0.25s;
}
.project-row:hover { transform: translateX(8px); }
.project-row:hover::before { opacity: 1; }

.pr-num {
  font-size: 0.62rem; font-weight: 600;
  color: var(--w18); letter-spacing: 0.1em;
}
.pr-name {
  display: block;
  font-size: 1.1rem; font-weight: 800;
  color: var(--white); letter-spacing: -0.02em;
}
.pr-sub {
  display: block; margin-top: 3px;
  font-size: 0.65rem; color: var(--w28);
  letter-spacing: 0.08em; text-transform: uppercase;
}
.pr-tags { display: flex; gap: 6px; }
.pr-tag {
  font-size: 0.58rem; padding: 3px 9px; border-radius: 999px;
  letter-spacing: 0.08em; text-transform: uppercase; font-weight: 600;
}
.tag-red  { background: var(--red-faint); color: var(--red); border: 1px solid var(--red-border); }
.tag-grey { background: var(--w04); color: var(--w28); border: 1px solid var(--w08); }

.pr-arrow {
  font-size: 0.9rem; color: var(--w18);
  transition: color 0.2s, transform 0.3s;
}
.project-row:hover .pr-arrow { color: var(--white); transform: rotate(-45deg); }

/* Hide year tags on mobile to reduce clutter */
@media (max-width: 767px) {
  .project-row { grid-template-columns: 28px 1fr 20px; gap: 12px; padding: 14px 0; }
  .pr-tags { display: none; }
  .pr-sub { display: none; }
}
```

- [ ] **Step 3: Verify**

Expected:
- 7 project rows, numbered 01–07
- Case studies (01–03) have red tags, others grey
- Desktop hover: row shifts 8px right, red bar appears on left, arrow rotates
- Mobile: tags and subs hidden, clean list

- [ ] **Step 4: Commit**

```bash
git add preview.html
git commit -m "feat: work section — 7 project rows with red hover accent"
```

---

## Task 9: Contact Section

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add contact HTML** (after work section)

```html
<!-- CONTACT -->
<section class="contact" id="contact">
  <div class="contact-inner">
    <div class="contact-left reveal">
      <p class="section-label" data-en="Get in touch" data-fr="Me contacter">Get in touch</p>
      <h2 class="contact-heading">
        <span data-en="Let's" data-fr="Travaillons">Let's</span><br>
        <span data-en="work" data-fr="ensemble">work</span><br>
        <em data-en="together." data-fr="ensemble.">together.</em>
      </h2>
      <p class="contact-sub"
         data-en="Open to freelance projects, collabs, and good conversations."
         data-fr="Ouvert aux projets freelance, collaborations, et belles conversations.">
        Open to freelance projects, collabs, and good conversations.
      </p>
    </div>
    <div class="contact-right reveal d1">
      <a href="mailto:abdouyaackoubi@gmail.com" class="contact-link">
        <div>
          <span class="cl-label" data-en="Email" data-fr="Email">Email</span>
          <span class="cl-val">abdouyaackoubi@gmail.com</span>
        </div>
        <span class="cl-arrow">→</span>
      </a>
      <a href="https://www.linkedin.com/in/abdou-yaackoubi/" target="_blank" rel="noopener" class="contact-link">
        <div>
          <span class="cl-label">LinkedIn</span>
          <span class="cl-val">/in/abdou-yaackoubi</span>
        </div>
        <span class="cl-arrow">→</span>
      </a>
      <a href="https://www.behance.net/Abdou_Yaackoubi" target="_blank" rel="noopener" class="contact-link">
        <div>
          <span class="cl-label">Behance</span>
          <span class="cl-val">/Abdou_Yaackoubi</span>
        </div>
        <span class="cl-arrow">→</span>
      </a>
    </div>
  </div>
</section>
```

- [ ] **Step 2: Add contact CSS**

```css
/* ── CONTACT ── */
.contact { border-top: 1px solid var(--w08); }
.contact-inner {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 56px var(--pad-x);
  display: flex; flex-direction: column; gap: 40px;
}
.contact-heading {
  font-size: clamp(2.4rem, 8vw, 4.2rem);
  font-weight: 900; letter-spacing: -0.04em; line-height: 0.92;
  color: var(--white); margin-top: 12px;
}
.contact-heading em {
  color: transparent;
  -webkit-text-stroke: 1px rgba(255,255,255,0.15);
  font-style: normal;
}
.contact-sub {
  font-size: 0.88rem; color: var(--w28); line-height: 1.75; margin-top: 16px;
}
.contact-right { display: flex; flex-direction: column; gap: 10px; }
.contact-link {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px;
  border: 1px solid var(--w08); border-radius: 10px;
  background: var(--w04);
  min-height: 56px; /* touch target */
  transition: background 0.3s, border-color 0.3s, transform 0.35s var(--ease-out);
}
.contact-link:hover {
  background: rgba(255,255,255,0.06);
  border-color: var(--red-border);
  transform: translateX(5px);
}
.contact-link:hover .cl-arrow { color: var(--red); transform: rotate(-45deg); }
.cl-label {
  display: block; font-size: 0.58rem; font-weight: 700;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--w28); margin-bottom: 3px;
}
.cl-val { font-size: 0.88rem; color: var(--white); font-weight: 600; }
.cl-arrow { font-size: 1rem; color: var(--w18); transition: color 0.25s, transform 0.3s; }

@media (min-width: 1024px) {
  .contact-inner {
    flex-direction: row; align-items: center;
    gap: 80px; padding: 100px var(--pad-x);
  }
  .contact-left { flex: 1; }
  .contact-right { flex: 1; }
}
```

- [ ] **Step 3: Verify**

Expected:
- Mobile: heading stacked, then 3 link cards below
- Desktop: heading left, link cards right
- Hover: card shifts 5px right, border turns red, arrow rotates
- All 3 links work (email opens mail client, LinkedIn/Behance open new tab)

- [ ] **Step 4: Commit**

```bash
git add preview.html
git commit -m "feat: contact section — split layout, 3 link cards with hover states"
```

---

## Task 10: Footer

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add footer HTML** (after contact section)

```html
<!-- FOOTER -->
<footer class="footer">
  <div class="footer-inner">
    <span class="footer-copy">© 2025 Abdallah Yaackoubi · All rights reserved</span>
    <div class="footer-links">
      <a href="https://www.behance.net/Abdou_Yaackoubi" target="_blank" rel="noopener">Behance</a>
      <a href="https://www.linkedin.com/in/abdou-yaackoubi/" target="_blank" rel="noopener">LinkedIn</a>
      <a href="UX UI Design Portfolio/CV-Abdallah_Yaackoubi.pdf" target="_blank">CV</a>
    </div>
  </div>
</footer>
```

- [ ] **Step 2: Add footer CSS**

```css
/* ── FOOTER ── */
.footer {
  border-top: 1px solid var(--w08);
  background: var(--bg-3);
}
.footer-inner {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 20px var(--pad-x);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}
.footer-copy {
  font-size: 0.6rem; color: rgba(255,255,255,0.12); letter-spacing: 0.12em;
}
.footer-links { display: flex; gap: 20px; }
.footer-links a {
  font-size: 0.6rem; color: var(--w18); letter-spacing: 0.1em;
  text-transform: uppercase; transition: color 0.2s;
}
.footer-links a:hover { color: var(--w55); }

@media (min-width: 768px) {
  .footer-inner {
    flex-direction: row; justify-content: space-between;
    text-align: left;
  }
}
```

- [ ] **Step 3: Verify**

Expected:
- Mobile: copy centered, links below centered
- Tablet+: copy left, links right
- Very dark background (#060606)

- [ ] **Step 4: Commit**

```bash
git add preview.html
git commit -m "feat: footer — minimal, dark, responsive stacking"
```

---

## Task 11: EN/FR Language Switcher

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Verify all data-en/data-fr attributes are present**

Every user-facing string added in Tasks 2–10 should already have `data-en` and `data-fr` attributes. Scan the HTML and confirm these elements have both attributes:
- Nav links (Work, About, Contact)
- Available pill
- Hero eyebrow
- Hero meta labels + values
- Featured label, sub
- About text spans
- Stats labels
- Work section label
- Project subtitles + tags
- Contact heading spans, sub
- Contact link labels

- [ ] **Step 2: Add language switcher JS** (inside `<script>`, replace the stub `setLang` if present)

```js
// EN/FR language switcher
function setLang(lang) {
  document.querySelectorAll('[data-en]').forEach(el => {
    const val = el.getAttribute('data-' + lang);
    if (val !== null) el.textContent = val;
  });
  document.getElementById('btn-en').classList.toggle('active', lang === 'en');
  document.getElementById('btn-fr').classList.toggle('active', lang === 'fr');
  document.documentElement.lang = lang;
  localStorage.setItem('lang', lang);
}

// Restore saved language on load
document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('lang');
  if (saved === 'fr') setLang('fr');
});
```

- [ ] **Step 3: Verify language switching**

Click FR button. Expected — every text element switches:
- Nav: "Work → Travaux", "About → À propos"
- Hero eyebrow: "Product Designer · Freelance → Designer Produit · Freelance"
- Available: "Available → Disponible"
- About bio text switches
- Stats labels switch
- Work section label: "Selected Work → Travaux sélectionnés"
- Contact heading, sub switch
- Click EN: all reverts

Reload page after setting FR: language is remembered from localStorage.

- [ ] **Step 4: Commit**

```bash
git add preview.html
git commit -m "feat: EN/FR language switcher with localStorage persistence"
```

---

## Task 12: Scroll Reveal Animations

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Add reveal CSS** (inside `<style>`)

```css
/* ── SCROLL REVEAL ── */
.reveal {
  opacity: 0;
  transform: translateY(24px);
  transition:
    opacity  0.8s var(--ease-out),
    transform 0.8s var(--ease-out);
}
.reveal.visible {
  opacity: 1;
  transform: none;
}
.d1 { transition-delay: 0.08s; }
.d2 { transition-delay: 0.16s; }
.d3 { transition-delay: 0.26s; }
.d4 { transition-delay: 0.36s; }
.d5 { transition-delay: 0.48s; }
```

- [ ] **Step 2: Confirm .reveal classes on elements**

These elements should already have `class="reveal"` from previous tasks:
- `.about-content`
- `.work-header`
- All 7 `.project-row` elements
- `.contact-left`
- `.contact-right` (with class `d1`)

Add any that are missing.

- [ ] **Step 3: Add IntersectionObserver JS** (inside `<script>`)

```js
// Scroll reveal
document.addEventListener('DOMContentLoaded', () => {
  const revealEls = document.querySelectorAll('.reveal');
  if (!revealEls.length) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target); // fire once
      }
    });
  }, { threshold: 0.12 });

  revealEls.forEach(el => observer.observe(el));
});
```

- [ ] **Step 4: Verify**

Reload page, scroll slowly. Expected:
- About content fades up as it enters viewport
- Work header fades up
- Each project row fades up as it scrolls into view
- Contact left and right fade in with slight stagger (d1 delay)
- Each animation fires once and stays visible

- [ ] **Step 5: Commit**

```bash
git add preview.html
git commit -m "feat: scroll reveal — IntersectionObserver on all sections"
```

---

## Task 13: Responsive QA — All 9 Viewports

**Files:**
- Modify: `preview.html` (fix any issues found)

- [ ] **Step 1: Test mobile — 360×800**

Open browser devtools, set to 360×800. Check each section:
- [ ] Nav: logo left, lang switcher right, no nav links visible ✓
- [ ] Hero: stacked, name fills full width, featured card full width below
- [ ] Hero: no horizontal overflow (scroll-x)
- [ ] About: horizontal label row, no sidebar
- [ ] Work: tags and subs hidden, clean list rows
- [ ] Contact: heading full width, link cards full width, min-height 56px
- [ ] Footer: stacked, centered

Fix any issues before moving on.

- [ ] **Step 2: Test mobile — 390×844 and 393×873**

Repeat checks. These are ~30px wider so fewer issues expected. Fix any edge cases.

- [ ] **Step 3: Test tablet — 768×1024**

Set devtools to 768×1024. Check:
- [ ] Nav: nav links visible
- [ ] Hero: side-by-side split, left 44%, right fills remainder
- [ ] About: sidebar not shown, inline horizontal label
- [ ] Contact: 2-column layout
- [ ] Footer: horizontal

- [ ] **Step 4: Test tablet — 810×1080 and 820×1180**

Repeat checks at wider tablet sizes. Expected: same layout, proportions slightly more comfortable.

- [ ] **Step 5: Test desktop — 1366×768**

Set devtools to 1366×768. Check:
- [ ] Hero fills full viewport height (100svh)
- [ ] Split hero 46%/54%, content not cramped
- [ ] About: left sidebar with vertical label, ghost number
- [ ] Max-width 1400px: content area fills available width

- [ ] **Step 6: Test desktop — 1536×864**

Same checks. Content should remain the same, slightly more breathing room.

- [ ] **Step 7: Test desktop — 1920×1080**

Set to 1920×1080. Check:
- [ ] max-width 1400px: content centred with space on sides
- [ ] No section stretches uncomfortably wide
- [ ] Background fills full viewport

- [ ] **Step 8: Commit fixes**

```bash
git add preview.html
git commit -m "fix: responsive QA across all 9 target viewports"
```

---

## Task 14: Final Polish

**Files:**
- Modify: `preview.html`

- [ ] **Step 1: Update project links**

Replace `href="#"` placeholders on each `.project-row` and `.hero-featured` with the actual Behance/Notion URLs for each project. Ask the user for URLs if not known.

- [ ] **Step 2: Verify load animation on first visit**

Hard-reload (`Cmd+Shift+R` / `Ctrl+Shift+R`) and watch full animation sequence. Confirm timing feels right. If any step feels too fast or too slow, adjust `setTimeout` delays in `initHeroAnimation()`.

- [ ] **Step 3: Verify cursor across all interactive elements**

Hover over: nav links, lang buttons, project rows, featured card, contact links. Confirm cursor ring expands to correct size for each state (`link` → 46px, `project` → 80px with VIEW text).

- [ ] **Step 4: Verify EN/FR on desktop and mobile**

Switch to FR, resize to 360px, scroll through full page. No text should overflow its container in French.

- [ ] **Step 5: Check page title and meta**

Confirm `<title>` reads "Abdallah Yaackoubi — Product Designer". Add basic meta description:

```html
<meta name="description" content="Abdallah Yaackoubi — Product Designer. UX, UI, and AI Workflows. 5+ years, 8 startups, based in Tunisia.">
```

- [ ] **Step 6: Final commit**

```bash
git add preview.html
git commit -m "polish: project links, meta description, final animation timing"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Mono × red color system — CSS custom properties in Task 1
- [x] Custom cursor (dot + ring + states) — Task 3
- [x] Fixed nav with scroll state + Available pill + EN/FR — Task 2
- [x] Hero split layout — Task 4
- [x] Hero load animation sequence (6 timed steps) — Task 5
- [x] Magnetic effect + hero cursor expand — Task 6
- [x] About with brutalist sidebar + stats — Task 7
- [x] Work list 7 rows, hover red bar, cursor expand — Task 8
- [x] Contact split, ghost heading, 3 link cards — Task 9
- [x] Footer — Task 10
- [x] EN/FR switcher with localStorage — Task 11
- [x] Scroll reveal IntersectionObserver — Task 12
- [x] All 9 target viewports — Task 13
- [x] max-width 1400px on desktop — Task 4 hero CSS
- [x] clamp() on all headings — Tasks 4, 7, 9

**No placeholders confirmed:** All code blocks are complete. No TBD/TODO present.

**Type consistency:** `setLang()` defined in Task 11, called by `onclick` in Task 2 nav HTML. `initHeroAnimation()` / `initMagnetic()` defined and called with `DOMContentLoaded`. `setCursorState()` defined in Task 3 cursor JS, called from the `mouseover` handler in the same block. No cross-task naming mismatches.
