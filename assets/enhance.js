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


/* Screen-in-screen viewer: tabs swap which panel is shown.
   Panels render visible by default; the .js class hides the inactive ones,
   so a failed script leaves every view reachable rather than blank. */
(function () {
  var boxes = document.querySelectorAll('[data-viewer]');
  if (!boxes.length) return;

  Array.prototype.forEach.call(boxes, function (box) {
    var tabs = box.querySelectorAll('.viewer__tab');
    var panels = box.querySelectorAll('.viewer__panel');
    if (!tabs.length) return;

    function show(i) {
      Array.prototype.forEach.call(panels, function (p, n) {
        p.classList.toggle('is-on', n === i);
      });
      Array.prototype.forEach.call(tabs, function (t, n) {
        t.classList.toggle('is-on', n === i);
        t.setAttribute('aria-selected', n === i ? 'true' : 'false');
        t.tabIndex = n === i ? 0 : -1;
      });
    }

    Array.prototype.forEach.call(tabs, function (tab, i) {
      tab.addEventListener('click', function () { show(i); });
      tab.addEventListener('keydown', function (e) {
        var d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
        if (!d) return;
        e.preventDefault();
        var next = (i + d + tabs.length) % tabs.length;
        tabs[next].focus();
        show(next);
      });
    });
    show(0);
  });
})();

/* Component lab behaviours. Each demo is real: the timings here match the
   spec printed next to it, so what a visitor sees is the documentation. */
(function () {
  if (!document.querySelector('.lab')) return;

  /* loading button */
  document.querySelectorAll('[data-lab-load]').forEach(function (b) {
    b.addEventListener('click', function () {
      b.classList.add('is-load');
      setTimeout(function () { b.classList.remove('is-load'); }, 1600);
    });
  });

  /* toggle */
  document.querySelectorAll('[data-lab-toggle]').forEach(function (t) {
    t.addEventListener('click', function () {
      var on = t.classList.toggle('is-on');
      t.setAttribute('aria-checked', on ? 'true' : 'false');
    });
  });

  /* toast — in fast, hold, out slower */
  document.querySelectorAll('[data-lab-toast]').forEach(function (btn) {
    var el = btn.parentNode.querySelector('[data-lab-toast-el]');
    var timer;
    btn.addEventListener('click', function () {
      clearTimeout(timer);
      el.hidden = false;
      void el.offsetWidth;   // force reflow: gives the transition a start state
      el.classList.add('is-in');
      timer = setTimeout(function () {
        el.classList.remove('is-in');
        setTimeout(function () { el.hidden = true; }, 320);
      }, 2600);
    });
  });

  /* dialog */
  document.querySelectorAll('[data-lab-modal]').forEach(function (btn) {
    var el = btn.parentNode.querySelector('[data-lab-modal-el]');
    function close() {
      el.classList.remove('is-in');
      setTimeout(function () { el.hidden = true; }, 260);
    }
    btn.addEventListener('click', function () {
      el.hidden = false;
      void el.offsetWidth;   // force reflow: gives the transition a start state
      el.classList.add('is-in');
    });
    el.querySelectorAll('[data-lab-modal-close]').forEach(function (c) {
      c.addEventListener('click', close);
    });
    el.addEventListener('click', function (e) { if (e.target === el) close(); });
  });

  /* accordion */
  document.querySelectorAll('[data-lab-acc]').forEach(function (acc) {
    var head = acc.querySelector('.c-acc__h');
    head.addEventListener('click', function () {
      var open = acc.classList.toggle('is-open');
      head.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });

  /* tabs — the indicator travels rather than cuts */
  document.querySelectorAll('[data-lab-tabs]').forEach(function (box) {
    var tabs = box.querySelectorAll('.c-tabs__t');
    var panels = box.querySelectorAll('.c-tabs__p');
    var ind = box.querySelector('.c-tabs__ind');
    function move(i) {
      var t = tabs[i];
      ind.style.width = t.offsetWidth + 'px';
      ind.style.transform = 'translateX(' + t.offsetLeft + 'px)';
      tabs.forEach(function (x, n) { x.classList.toggle('is-on', n === i); });
      panels.forEach(function (p, n) { p.classList.toggle('is-on', n === i); });
    }
    tabs.forEach(function (t, i) { t.addEventListener('click', function () { move(i); }); });
    /* the lab panel may be display:none at load, so offsetLeft would read 0 */
    var ro = new ResizeObserver(function () { if (box.offsetParent) move(indexOfOn()); });
    function indexOfOn() {
      for (var i = 0; i < tabs.length; i++) if (tabs[i].classList.contains('is-on')) return i;
      return 0;
    }
    ro.observe(box);
    move(0);
  });
})();
