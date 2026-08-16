/* ══════════════════════════════════════════════
   Motion layer — umanodesign.studio patterns
   · Lenis inertial smooth scroll (their exact config)
   · scroll-linked parallax on [data-parallax]
   · anchor links routed through Lenis
   Lazy-loads Lenis only on fine pointers; skipped for
   touch devices and prefers-reduced-motion.
   ══════════════════════════════════════════════ */
(function () {
  'use strict';

  var coarse = window.matchMedia('(pointer: coarse)').matches;
  var calm   = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var lenis  = null;

  /* ── 1 · LENIS SMOOTH SCROLL ─────────────────
     duration 1.2s with an exponential ease-out —
     gives that heavy, gliding inertia on the wheel. */
  function initLenis() {
    if (!window.Lenis) return;

    lenis = new window.Lenis({
      duration: 1.2,
      easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
      smoothWheel: true,
      touchMultiplier: 1.6
    });

    (function raf(time) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    })(0);

    // route in-page anchors through Lenis so they inherit the easing
    document.addEventListener('click', function (e) {
      var a = e.target.closest && e.target.closest('a[href^="#"]');
      if (!a) return;
      var href = a.getAttribute('href');
      if (!href || href === '#') return;
      var target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      lenis.scrollTo(target, { offset: -70 });
    });

    document.documentElement.classList.add('has-lenis');
  }

  if (!coarse && !calm) {
    var s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/lenis@1.1.20/dist/lenis.min.js';
    s.defer = true;
    s.onload = initLenis;
    s.onerror = function () { /* native scrolling stays as the fallback */ };
    document.head.appendChild(s);
  }

  /* ── 2 · PARALLAX ────────────────────────────
     <div data-parallax="0.3"> drifts at 30% of scroll.
     Only elements currently on screen get updated. */
  if (calm) return;

  var items = [].slice.call(document.querySelectorAll('[data-parallax]'));
  if (!items.length) return;

  var live = [];

  var io = ('IntersectionObserver' in window)
    ? new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          var i = live.indexOf(en.target);
          if (en.isIntersecting && i === -1) live.push(en.target);
          else if (!en.isIntersecting && i !== -1) live.splice(i, 1);
        });
      }, { rootMargin: '15% 0px 15% 0px' })
    : null;

  items.forEach(function (el) {
    el.style.willChange = 'transform';
    if (io) io.observe(el); else live.push(el);
  });

  var vh = window.innerHeight;
  window.addEventListener('resize', function () { vh = window.innerHeight; }, { passive: true });

  (function tick() {
    for (var i = 0; i < live.length; i++) {
      var el = live[i];
      var r  = el.getBoundingClientRect();
      var speed = parseFloat(el.getAttribute('data-parallax')) || 0.3;
      // distance of the element's centre from the viewport centre
      var delta = (r.top + r.height / 2) - vh / 2;
      el.style.transform = 'translate3d(0,' + (-delta * speed).toFixed(2) + 'px,0)';
    }
    requestAnimationFrame(tick);
  })();
})();

/* ══════════════════════════════════════════════
   NAV INDICATOR — one solid shape that morphs
   between items. Follows hover; settles back on the
   active section. Stays in sync with the scroll-spy.
   ══════════════════════════════════════════════ */
(function () {
  'use strict';

  var wrap = document.querySelector('.nav-links');
  if (!wrap) return;
  var links = [].slice.call(wrap.querySelectorAll('a'));
  if (!links.length) return;

  var ind = document.createElement('span');
  ind.className = 'nav-ind';
  ind.setAttribute('aria-hidden', 'true');
  wrap.insertBefore(ind, wrap.firstChild);

  function active() { return wrap.querySelector('a.is-active'); }

  function moveTo(el) {
    links.forEach(function (a) { a.classList.remove('is-lit'); });
    if (!el) { ind.style.opacity = '0'; return; }
    var w = wrap.getBoundingClientRect();
    var r = el.getBoundingClientRect();
    ind.style.width  = r.width + 'px';
    ind.style.height = r.height + 'px';
    ind.style.transform = 'translate(' + (r.left - w.left) + 'px,' + (r.top - w.top) + 'px)';
    ind.style.opacity = '1';
    el.classList.add('is-lit');
  }

  var settle, hovering = false, lastActive = null;
  function reset() { lastActive = active(); moveTo(lastActive); }

  links.forEach(function (a) {
    a.addEventListener('mouseenter', function () {
      hovering = true; clearTimeout(settle); moveTo(a);
    });
  });
  wrap.addEventListener('mouseleave', function () {
    hovering = false; clearTimeout(settle);
    settle = setTimeout(reset, 80);
  });

  /* Sync with the scroll-spy that toggles .is-active.
     NOTE: do NOT use a MutationObserver on class changes here — moveTo()
     writes the .is-lit class onto these same links, so observing them
     would retrigger this handler in an unbounded microtask loop and hang
     the page. Polling on scroll is cheap and cannot feed back. */
  var queued = false;
  window.addEventListener('scroll', function () {
    if (hovering || queued) return;
    queued = true;
    requestAnimationFrame(function () {
      queued = false;
      var a = active();
      if (a !== lastActive) { lastActive = a; moveTo(a); }
    });
  }, { passive: true });

  window.addEventListener('resize', reset, { passive: true });

  // place it without animating on first paint
  var keep = ind.style.transition;
  ind.style.transition = 'none';
  reset();
  requestAnimationFrame(function () { ind.style.transition = keep; });
})();

/* ══════════════════════════════════════════════
   SPOTLIGHT — writes the pointer position onto hovered
   rows/tiles as --mx/--my so CSS can light them from
   under the cursor. Delegated, so new rows work for free.
   ══════════════════════════════════════════════ */
(function () {
  'use strict';
  if (window.matchMedia('(pointer: coarse)').matches) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var SEL = '.pl-item, .play';
  var current = null, pending = false, px = 0, py = 0;

  document.addEventListener('mousemove', function (e) {
    var el = e.target.closest && e.target.closest(SEL);
    current = el;
    if (!el) return;
    px = e.clientX; py = e.clientY;
    if (pending) return;
    pending = true;
    requestAnimationFrame(function () {
      pending = false;
      if (!current) return;
      var r = current.getBoundingClientRect();
      current.style.setProperty('--mx', (px - r.left) + 'px');
      current.style.setProperty('--my', (py - r.top) + 'px');
    });
  }, { passive: true });
})();
