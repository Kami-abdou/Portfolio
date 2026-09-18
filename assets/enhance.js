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

  /* Two separate facts, previously conflated into one class:

       .js    this script is running, so JS-dependent UI can be offered
       .anim  reveal animations are wanted — needs an observer to drive
              them and a visitor who has not asked for less motion

     Setting only .js meant a reduced-motion visitor was treated as a
     no-JS visitor. Because `html:not(.js) .viewer__tabs { display: none }`,
     they lost the component browser's tablist completely and got every
     panel stacked instead, on the page that tells them to step through
     the views. The tabs need JS, not animation, so they are gated on .js;
     the reveals are gated on .anim. */
  root.classList.add('js');
  if (!calm && io) root.classList.add('anim');

  /* ── motion clips: play in view, pause out of view ────
     The markup ships <video controls muted loop> with NO autoplay, so the
     base state is a poster frame and nothing moves until the visitor asks.
     That is also the whole reduced-motion story: this block is gated on
     !calm, so a visitor who asked for less motion never gets autoplay and
     keeps the controls they can drive themselves. No media query needed.

     Pausing on exit matters more than starting on entry. A looping clip
     playing on a screen nobody is looking at decodes frames for nothing,
     and on the page arguing that interaction detail is the job, leaving it
     running would be the wrong answer.

     play() returns a promise that rejects if the browser declines (low-power
     mode, a policy we did not anticipate). It is caught and ignored: the
     poster plus controls is already a working state, so a refused autoplay
     degrades to exactly the base experience.

     userPaused stops us fighting the visitor. Without it, scrolling away
     from a clip they deliberately paused and back again restarts it. */
  if (!calm && io) {
    var clips = document.querySelectorAll('.shot__video');
    if (clips.length) {
      var clipWatcher = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          var v = en.target;
          v.dataset.inView = en.isIntersecting ? '1' : '0';
          if (en.isIntersecting) {
            if (v.paused && v.dataset.userPaused !== '1') {
              var r = v.play();
              if (r && r.catch) { r.catch(function () {}); }
            }
          } else if (!v.paused) {
            v.pause();
          }
        });
      }, { threshold: 0.4 });

      clips.forEach(function (v) {
        v.addEventListener('pause', function () {
          if (!v.ended && v.dataset.inView === '1') { v.dataset.userPaused = '1'; }
        });
        v.addEventListener('play', function () { v.dataset.userPaused = '0'; });
        clipWatcher.observe(v);
      });
    }
  }

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
      '.band, .project__section, .shots, .about__grid, .cv, .pager'
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
