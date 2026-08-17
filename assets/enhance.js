/* Progressive enhancement — reveals, section tracking, reading progress.

   Everything here is additive. The <html class="js"> flag is set as the
   first act, and every hiding rule in the stylesheet is scoped to that
   class, so if this file fails to load the page still shows all content.
*/
(function () {
  'use strict';

  var root = document.documentElement;
  var calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var io = 'IntersectionObserver' in window;

  if (!calm && io) root.classList.add('js');

  /* ── reveal on enter ─────────────────────────────
     Sections rise and sharpen out of a slight blur once. */
  if (!calm && io) {
    var watcher = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('is-in');
          watcher.unobserve(en.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -6% 0px' });

    document.querySelectorAll(
      '.band, .project__section, .shots, .about__grid, .pager'
    ).forEach(function (el) {
      el.classList.add('rise');
      watcher.observe(el);
    });

    /* Masked headings observe themselves. Relying on an enclosing wrapper
       is fragile — a heading that sits outside one would stay translated
       off-screen forever. The hero is excluded; it animates on load. */
    document.querySelectorAll('.mask').forEach(function (el) {
      if (el.closest('.hero')) return;
      watcher.observe(el);
    });
  }

  /* ── reading progress ────────────────────────────
     Case studies are long; show how much is left. */
  var bar = document.querySelector('.progress__bar');
  if (bar) {
    var article = document.querySelector('.project');
    var ticking = false;
    var draw = function () {
      ticking = false;
      var box = article.getBoundingClientRect();
      var travel = box.height - window.innerHeight;
      var done = travel > 0 ? (-box.top / travel) : 0;
      bar.style.transform = 'scaleX(' + Math.min(1, Math.max(0, done)) + ')';
    };
    var onScroll = function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(draw);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    draw();
  }

  /* ── mark the section you're reading in the index ──
     Tracks the heading nearest the top of the viewport rather than
     using an observer per section, so it stays correct when several
     sections are on screen at once. */
  var links = [].slice.call(document.querySelectorAll('.toc__list a'));
  if (links.length) {
    var targets = links.map(function (a) {
      return { link: a, el: a.hash ? document.querySelector(a.hash) : null };
    }).filter(function (t) { return t.el; });

    var queued = false;
    var mark = function () {
      queued = false;
      var best = null, bestTop = -Infinity;
      for (var i = 0; i < targets.length; i++) {
        var top = targets[i].el.getBoundingClientRect().top - 120;
        if (top <= 0 && top > bestTop) { bestTop = top; best = targets[i]; }
      }
      links.forEach(function (a) { a.classList.remove('is-current'); });
      if (best) best.link.classList.add('is-current');
    };
    window.addEventListener('scroll', function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(mark);
    }, { passive: true });
    mark();
  }
})();

/* ══════════════════════════════════════════════
   CYCLING ROLE LINE
   Advances one role at a time: the current one slides up and out
   while the next rises into the slot. Pauses when the tab is
   hidden so it isn't animating into an empty room.
   ══════════════════════════════════════════════ */
(function () {
  'use strict';

  var slot = document.querySelector('[data-roles]');
  if (!slot) return;

  var items = [].slice.call(slot.querySelectorAll('.roles__item'));
  if (items.length < 2) return;                       // nothing to cycle

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var HOLD = 2600;
  var i = 0, timer = null;

  function step() {
    var out = items[i];
    i = (i + 1) % items.length;
    var next = items[i];

    out.classList.remove('is-on');
    out.classList.add('is-out');
    next.classList.add('is-on');

    // Once the outgoing item has left, move it back below the slot so it is
    // ready to rise again on its next turn. The transition is suppressed for
    // that reset — otherwise it would animate back down *through* the slot
    // and you would see it pass the role that just arrived.
    var parked = false;
    var park = function (ev) {
      if (parked || (ev && ev.target !== out)) return;
      parked = true;
      out.removeEventListener('transitionend', park);
      out.style.transition = 'none';
      out.classList.remove('is-out');
      void out.offsetHeight;                          // flush the change
      out.style.transition = '';
    };
    out.addEventListener('transitionend', park);
    setTimeout(park, 900);                            // fallback if the event never fires
  }

  function start() { if (!timer) timer = setInterval(step, HOLD); }
  function stop() { clearInterval(timer); timer = null; }

  document.addEventListener('visibilitychange', function () {
    document.hidden ? stop() : start();
  });
  start();
})();
