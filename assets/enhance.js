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

  /* ── smooth cursor trail ──────────────────────────
     A vanilla port of reactbits' SmoothCursor. The published component is
     React + Tailwind and installs through shadcn; this site has no
     package.json, no node_modules and no framework, and says so on its own
     project page ("0 runtime dependencies", "10.6 KB JavaScript"), so the
     component could not be installed. The behaviour is what was wanted, so
     the behaviour is what was ported.

     Upstream's two configurations, kept for reference. The values actually
     shipped live in tokens.json, and two of them are now lower than either
     column -- see the deviations below:

       pointsCount     40     trail segments
       springStrength  0.4    higher follows faster
       dampening       0.5    friction; lower is more fluid
       smoothFactor    1      curve smoothness
       lineWidth       0.3 / 1.00
       trailOpacity    1   / 0.10
       blur            0   / 9
       velocityScale   off / ON
       mixBlendMode    source-over ("Normal" in the panel)

     Two columns because the two disagree: the left is the documented prop
     default, the right is what the live demo's Customize panel actually
     runs -- and the demo is what was asked for. The defaults alone produce
     a hard hairline; the demo settings produce a soft glow, which is a
     different effect entirely. Every value here is the demo's.

     THREE deliberate deviations, all recorded because "use the component's
     own configuration" was the request.

     lineWidth ships at 0.6 and trailOpacity at 0.06, against the demo's
     1.00 and 0.10. Both were lowered at the owner's request -- less opaque,
     less thick -- and the request was well aimed, because nominal 0.10 was
     never what landed on screen: measured at the demo's values, the head of
     the trail peaked at alpha 244 of 255, all but solid. The points bunch up
     once they catch the pointer, so thirty-odd translucent strokes overlap
     and accumulate. Note that upstream's own prop default for lineWidth,
     0.3, measured invisible here -- it lit 2,906 of 3,840,000 canvas pixels,
     a sub-pixel hairline -- so 0.6 is deliberately between the two rather
     than a return to the default. Tune --cursor-line-width and
     --cursor-opacity in tokens.json; nothing here needs editing.

     Colour: upstream's default is #000000, which
     on this page (#02050C) is invisible. Black is upstream's "default ink",
     so the faithful translation is this page's default ink -- var(--color-
     text) -- resolved per frame rather than captured once, so it cannot be
     left behind if that token ever changes underneath it.

     Gating is added rather than ported; the upstream docs describe none.
     A trailing line that chases the pointer is exactly the motion a
     vestibular trigger looks like, so it is off under prefers-reduced-
     motion, and it is off entirely without a fine hover-capable pointer --
     on a phone there is no pointer to trail and the canvas would burn
     battery drawing nothing. */
  var fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  /* NOTE ON NAMES. Everything in this file shares one function scope, and
     `var` is function-scoped, so a second `var draw` anywhere in this IIFE
     silently replaces the first. That is not hypothetical: this block once
     declared `var draw`, the reading-progress block below declares its own
     `var draw`, and because that block runs later its assignment won. The
     trail then requested a frame, the frame fired, and it called the
     PROGRESS BAR's draw -- so the canvas never painted and nothing errored.

     It broke only on project pages, which is what made it look like a
     page-specific quirk: the progress block is guarded by `if (bar)`, and
     only case studies have a progress bar. The homepage kept the cursor's
     draw purely because the collision never executed there.

     Hence drawTrail/kickTrail. See the duplicate-declaration test. */
  if (!calm && fine.matches) {
    /* Read from the generated tokens rather than hardcoded here, so the
       whole configuration lives in tokens.json beside every other value
       this site is built from -- and so it can be tuned without touching
       JavaScript. The defaults in that file are upstream's verbatim. */
    var cfg = function (name, fallback) {
      var v = parseFloat(
        getComputedStyle(root).getPropertyValue('--cursor-' + name));
      return isNaN(v) ? fallback : v;
    };
    var str = function (name, fallback) {
      var v = getComputedStyle(root).getPropertyValue('--cursor-' + name).trim();
      return v || fallback;
    };
    var POINTS = cfg('points', 60), SPRING = cfg('spring', 0.4);
    var DAMPING = cfg('damping', 0.5), SMOOTH = Math.max(1, cfg('smooth', 2));
    var LINE_WIDTH = cfg('line-width', 1);
    var TRAIL_OPACITY = cfg('opacity', 0.1), BLUR = cfg('blur', 9);
    var VELOCITY_SCALE = cfg('velocity-scale', 1) > 0;
    var BLEND = str('blend', 'source-over');

    var canvas = document.createElement('canvas');
    canvas.className = 'cursor-trail';
    canvas.setAttribute('aria-hidden', 'true');
    var ctx = canvas.getContext('2d');
    document.body.appendChild(canvas);

    /* The trail is blurred by BLUR css pixels before anyone sees it, so a
       2x backing store buys nothing: every edge the extra pixels would
       preserve is destroyed by the filter on its way to the screen. Capping
       at 1 quarters the area that has to be filled and then blurred -- on a
       1280x800 retina viewport, 2560x1600 becomes 1280x800. The cap is tied
       to the blur rather than hardcoded, because an unblurred hairline is
       the one configuration that would genuinely show the difference. */
    var MAX_DPR = BLUR ? 1 : 2;

    var dpr = 1, w = 0, h = 0;
    var resize = function () {
      dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    var pts = [];
    for (var n = 0; n < POINTS; n++) pts.push({ x: -100, y: -100, vx: 0, vy: 0 });
    var mx = -100, my = -100, seen = false, frame = 0;

    /* Cached, NOT resolved per frame. getComputedStyle is a read that can
       force a style recalculation, and this one sat inside the draw loop.
       Measured on a case study: 0.745ms per call while style was dirty,
       against 0.003ms once it was clean -- and on a case study style IS
       dirty on every frame you scroll, because the reading-progress block
       below writes a transform. So this was most of a millisecond per frame
       spent re-reading a token that changes approximately never.

       The original intent was that the trail must never render stale ink if
       --color-text moves underneath it. That intent is kept, by
       invalidating on the only two things that can move it: the OS colour
       scheme, and a [data-theme] override on <html>. */
    var inkValue = '';
    var readInk = function () {
      inkValue = getComputedStyle(root).getPropertyValue('--color-text').trim()
                 || '#000';
    };
    readInk();
    var ink = function () { return inkValue; };

    var dark = window.matchMedia('(prefers-color-scheme: dark)');
    if (dark.addEventListener) dark.addEventListener('change', readInk);
    new MutationObserver(readInk).observe(root,
      { attributes: true, attributeFilter: ['data-theme'] });

    /* Blur lives on the ELEMENT, not the context. ctx.filter would re-run
       a 9px gaussian for each of the 60 strokes below; the canvas is
       composited once either way, so this is the same picture for a
       fraction of the work. */
    if (BLUR) canvas.style.filter = 'blur(' + BLUR + 'px)';

    var drawTrail = function () {
      frame = 0;
      /* Nothing worth drawing under a full-screen overlay. The lightbox
         backdrop is 92% opaque #F4F4F2 and the ink is #EDEDEB, so the trail
         reaches the eye at roughly 0.8% strength -- it is not faint behind
         the lightbox, it is invisible. Drawing it anyway still fills ~11% of
         the backing store across sixty strokes and runs a gaussian over all
         of it, every frame, to produce no picture at all -- and does it
         under a translucent overlay holding a screenshot up to 1400x7258,
         which is the combination the owner felt as the page going slow. */
      if (root.classList.contains('has-overlay')) {
        if (seen) { seen = false; ctx.clearRect(0, 0, w, h); }
        return;
      }
      var lead = pts[0];
      lead.vx = (lead.vx + (mx - lead.x) * SPRING) * DAMPING;
      lead.vy = (lead.vy + (my - lead.y) * SPRING) * DAMPING;
      lead.x += lead.vx; lead.y += lead.vy;

      var moving = Math.abs(lead.vx) + Math.abs(lead.vy) > 0.01;
      for (var i = 1; i < pts.length; i++) {
        var p = pts[i], prev = pts[i - 1];
        p.vx = (p.vx + (prev.x - p.x) * SPRING) * DAMPING;
        p.vy = (p.vy + (prev.y - p.y) * SPRING) * DAMPING;
        p.x += p.vx; p.y += p.vy;
        if (Math.abs(p.vx) + Math.abs(p.vy) > 0.01) moving = true;
      }

      ctx.clearRect(0, 0, w, h);
      if (seen) {
        /* lineWidth is a FACTOR, as the props table says -- not a pixel
           width. Each segment is stroked at factor x (remaining points), so
           the head is pointsCount wide and the tail tapers to nothing: at
           the demo's 1.00 and 60 points that is a ~60px head, which is the
           shape in the reference. Reading it as an absolute width is what
           made 0.3 look like an invisible hairline; 0.3 x 60 is an 18px
           trail, which is not invisible at all.

           Stroking segment by segment rather than as one path is what
           allows the taper, and it is also where the bright head comes
           from: the points bunch up around the cursor once they have caught
           up, so dozens of translucent strokes overlap and accumulate to
           near-solid, while the spread-out tail stays at a single 0.10
           pass. One path at one width cannot produce either. */
        var boost = 1;
        if (VELOCITY_SCALE) {
          var speed = Math.sqrt(lead.vx * lead.vx + lead.vy * lead.vy);
          boost = 1 + Math.min(speed / 40, 1.5);
        }
        ctx.globalAlpha = TRAIL_OPACITY;
        ctx.globalCompositeOperation = BLEND;
        ctx.strokeStyle = ink();
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        for (var k = 0; k < pts.length - 1; k++) {
          var a = pts[k], b = pts[k + 1];
          ctx.lineWidth = LINE_WIDTH * (pts.length - k) * boost;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          /* smoothFactor: curve each segment through the midpoint of the
             next, so the joins read as one continuous body rather than 60
             straight pieces. At 1 it is a plain line. */
          if (SMOOTH > 1 && k < pts.length - 2) {
            var c2 = pts[k + 2];
            ctx.quadraticCurveTo(b.x, b.y, (b.x + c2.x) / 2, (b.y + c2.y) / 2);
          } else {
            ctx.lineTo(b.x, b.y);
          }
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        ctx.globalCompositeOperation = 'source-over';
      }

      if (moving) { frame = requestAnimationFrame(drawTrail); }
      else { frame = 0; }
    };

    /* Cancel and re-request rather than guarding with a "has it started"
       flag. The flag version deadlocked: kickTrail raised the flag and requested
       a frame, that frame was never delivered -- requestAnimationFrame is a
       REQUEST, and a browser is free to drop it if the document is not being
       rendered at that moment -- and every later pointer move then saw the
       flag raised and declined to ask again. One dropped frame killed the
       trail for the life of the page.

       It failed on project pages and not the homepage, which is the shape
       of a race: the heavier the page, the more reliably that first request
       is dropped. A flag recording "I asked" is not the same fact as "a
       frame is coming", and only the second is worth branching on.
       Re-requesting is idempotent here -- at most one frame is ever pending
       -- so the cheap fix is also the correct one. */
    var kickTrail = function () {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(drawTrail);
    };

    window.addEventListener('pointermove', function (e) {
      if (e.pointerType && e.pointerType !== 'mouse') return;
      /* Checked here as well as in drawTrail, so an open overlay costs no
         frames at all rather than one cheap frame per pointer move. Dropping
         `seen` also re-seeds the trail at the pointer when the overlay
         closes, instead of letting it snap across the page from wherever it
         was frozen. */
      if (root.classList.contains('has-overlay')) {
        if (seen) { seen = false; ctx.clearRect(0, 0, w, h); }
        return;
      }
      mx = e.clientX; my = e.clientY;
      if (!seen) {
        seen = true;
        for (var i = 0; i < pts.length; i++) { pts[i].x = mx; pts[i].y = my; }
      }
      kickTrail();
    }, { passive: true });

    /* A trail left frozen mid-screen when the pointer leaves the window
       reads as a rendering bug rather than an effect. */
    document.addEventListener('mouseleave', function () {
      seen = false;
      ctx.clearRect(0, 0, w, h);
    });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden && frame) { cancelAnimationFrame(frame); frame = 0; }
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

    /* ── jumping in the index must not fill the Back button ──
       Every <a href="#id"> click pushes a history entry. Read a case study
       by clicking through eight index items and Back has to be pressed
       eight times to get off the page: it retraces the sections instead of
       returning to the work you came from, which is what Back means to
       anyone reading.

       replaceState swaps the current entry instead of adding one. The URL
       still names the section, so it stays copyable and a reload still
       lands in the right place, but Back now means "leave this page". The
       trade is deliberate -- Back no longer retraces jumps within the page,
       and that is the behaviour that was reported as the bug.

       preventDefault also cancels the focus move the browser does for free,
       which would strand a keyboard visitor at the top of the index with
       Tab resuming from the link they just used rather than from the
       section they asked for. Hence the tabindex/focus pair. preventScroll
       stops that focus call fighting the smooth scroll already in flight.

       scrollIntoView takes no arguments on purpose: the offset comes from
       scroll-margin-top and the easing from scroll-behavior, both already
       in the stylesheet, including the reduced-motion override that turns
       smooth off. Passing options here would fork that decision into two
       places and let them drift.

       Bail-outs, in order: a handler that already ran, anything but a plain
       left click, and a browser with no replaceState -- in each case the
       native jump is left to happen, which is correct, just with the extra
       history entry. Modified clicks matter: cmd/ctrl/shift-click opens the
       section in a new tab, and that is a navigation, not a jump. */
    targets.forEach(function (t) {
      t.link.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        if (!history.replaceState) return;

        e.preventDefault();
        history.replaceState(null, '', t.link.hash);
        t.el.scrollIntoView();
        if (!t.el.hasAttribute('tabindex')) t.el.setAttribute('tabindex', '-1');
        t.el.focus({ preventScroll: true });
        mark();
      });
    });
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


/* The marquee's pause control — WCAG 2.2.2 Pause, Stop, Hide (Level A).

   The three rows in the signature band animate indefinitely, start on their
   own and are not essential to anything, which is exactly the case 2.2.2
   covers. A `prefers-reduced-motion` block does not discharge it: the
   criterion asks for a MECHANISM, and an operating-system preference the
   visitor may never have heard of is not a mechanism on this page.

   The button ships `hidden` so that a visitor with JS off never sees a
   control that cannot work. Unhiding it here is the whole progressive-
   enhancement contract: with no JS the rows still move, but nothing on
   screen claims you can stop them.
*/
(function () {
  var band = document.querySelector('.hero');
  var btn = document.querySelector('.wall-pause');
  if (!band || !btn) return;
  if (!band.querySelector('.wall__track')) return;

  btn.hidden = false;

  function label(text) {
    // Only the leading text node. Setting textContent would delete the
    // visually-hidden span that gives the button its full accessible name.
    var first = btn.firstChild;
    if (first && first.nodeType === 3) first.nodeValue = text;
  }

  function setPaused(paused) {
    band.classList.toggle('is-paused', paused);
    btn.setAttribute('aria-pressed', paused ? 'true' : 'false');
    label(paused ? 'Play' : 'Pause');
  }

  // Written out rather than bound inline: a ternary that evaluates to a
  // handler attaches without error and then never fires, which cost an
  // afternoon once on this file.
  btn.addEventListener('click', function () {
    var paused = band.classList.contains('is-paused');
    setPaused(!paused);
  });

  // Someone who has asked the OS for less motion gets it stopped to begin
  // with, and can still start it. The mechanism and the preference are
  // separate obligations; this honours both.
  var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)');
  setPaused(!!(calm && calm.matches));
})();


/* The case-study rail's buttons and counter.

   The rail scrolls natively, so this adds nothing a trackpad, a touch
   screen or the keyboard could not already do. It exists for a mouse
   without a horizontal wheel, where a horizontal scroller is otherwise
   genuinely awkward, and for the position readout.

   Which is why the nav ships `hidden` and is unhidden here: with no
   script the rail still works completely, and nothing on screen offers a
   control that would do nothing.
*/
(function () {
  var rails = document.querySelectorAll('.rail');
  if (!rails.length) return;

  var calm = window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  Array.prototype.forEach.call(rails, function (rail) {
    var section = rail.closest('.band--rail');
    if (!section) return;
    var nav = section.querySelector('.rail__nav');
    var prev = section.querySelector('.rail__btn--prev');
    var next = section.querySelector('.rail__btn--next');
    var at = section.querySelector('.rail__at');
    var cards = rail.children;
    if (!nav || !prev || !next || !cards.length) return;

    nav.hidden = false;

    /* The scrollLeft at which card i is the snapped one.

       Measured in LAYOUT space -- offsetLeft, which does not move when the
       rail scrolls -- rather than from getBoundingClientRect(). Rects are
       viewport-relative, so reading them while a scroll is in flight gives
       a position that is already stale, and the arithmetic built on it
       lands near a snap point instead of on one. Measured before the
       change: clicking through the rail came to rest at 549, 1116, 623 and
       35 against snap positions of 572, 1144, 572 and 0 -- consistently
       about one scroll-padding out.

       Card 0 sits exactly on the padding line at scrollLeft 0, so every
       other card's distance from it IS the scroll offset that snaps it. */
    function snapPos(i) {
      return cards[i].offsetLeft - cards[0].offsetLeft;
    }

    function atEnd() {
      return rail.scrollLeft >= rail.scrollWidth - rail.clientWidth - 1;
    }

    function nearest() {
      // The last card can never BE the snapped one: its snap position is
      // past the end of the scroll range, because snapping its left edge
      // to the padding line would need to scroll further than there is
      // content. Measured: snap positions 0/572/1144/1716 against a
      // maximum scroll of 1280. So at the end the nearest card by edge is
      // the second-to-last and the counter read "03 / 04" with the fourth
      // card the only one fully on screen. At the end, it is the last.
      if (atEnd()) return cards.length - 1;
      var x = rail.scrollLeft;
      var best = 0;
      var bestDistance = Infinity;
      for (var i = 0; i < cards.length; i++) {
        var d = Math.abs(snapPos(i) - x);
        if (d < bestDistance) { bestDistance = d; best = i; }
      }
      return best;
    }

    function go(step) {
      var i = nearest() + step;
      if (i < 0) i = 0;
      if (i > cards.length - 1) i = cards.length - 1;
      var from = rail.scrollLeft;
      var to = snapPos(i);

      // scrollTo with an absolute target rather than scrollBy with a
      // delta: if anything lands mid-animation the absolute form still
      // converges on the right card instead of compounding an error.
      rail.scrollTo({ left: to, behavior: calm ? 'auto' : 'smooth' });

      // Not every environment honours behavior: 'smooth'. The spec says
      // it should degrade to an instant jump; some do nothing at all and
      // leave the container exactly where it was, which turns both
      // buttons into dead controls with no error anywhere. Measured in
      // this project's own test browser: a smooth scrollTo on the rail
      // AND on the page both stayed at 0 through 1.4s of sampling.
      //
      // So the move is verified rather than assumed. 120ms is long
      // enough that a real smooth scroll has visibly started and short
      // enough that the fallback still reads as a response to the click.
      if (!calm) {
        setTimeout(function () {
          if (Math.abs(rail.scrollLeft - from) < 1) rail.scrollLeft = to;
        }, 120);
      }
    }

    function update() {
      if (at) {
        var n = nearest() + 1;
        at.textContent = (n < 10 ? '0' : '') + n;
      }
      // A 1px slack: scrollLeft is fractional on a zoomed or scaled
      // display, so === 0 and === max both miss and the buttons never
      // disable.
      prev.disabled = rail.scrollLeft <= 1;
      next.disabled = atEnd();
    }

    prev.addEventListener('click', function () { go(-1); });
    next.addEventListener('click', function () { go(1); });
    rail.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update, { passive: true });
    update();
  });
})();


/* Collapsible case-study sections: the two things <details> does not do
   for itself.

   Everything else about them is the browser's. A <summary> opens on
   click and on Enter or Space, exposes its own expanded state, and works
   with this file absent entirely. What is missing is that a link to a
   section inside a CLOSED <details> scrolls to a collapsed heading and
   appears to do nothing -- which breaks the table of contents, the
   pager's deep links and any URL anyone has shared.
*/
(function () {
  var sections = document.querySelectorAll('details.project__section');
  if (!sections.length) return;

  /* 1. Opening a section that something just linked to. */
  function reveal(hash) {
    if (!hash || hash.length < 2) return;
    var target;
    try {
      target = document.querySelector(hash);
    } catch (err) {
      return;                      // a hash that is not a valid selector
    }
    if (!target) return;
    var box = target.closest('details');
    if (box && !box.open) box.open = true;
  }

  reveal(window.location.hash);
  window.addEventListener('hashchange', function () {
    reveal(window.location.hash);
  });
  // Before the jump, not after: opening the section first means the
  // browser scrolls to a heading that is already in its final position.
  document.addEventListener('click', function (ev) {
    var link = ev.target.closest && ev.target.closest('a[href^="#"]');
    if (!link) return;
    reveal(link.getAttribute('href'));
  }, true);

  /* 2. Expand all / collapse all. */
  var control = document.querySelector('.sections__control');
  var toggle = control && control.querySelector('.sections__toggle');
  if (!control || !toggle) return;

  control.hidden = false;

  function allOpen() {
    for (var i = 0; i < sections.length; i++) {
      if (!sections[i].open) return false;
    }
    return true;
  }

  function sync() {
    var open = allOpen();
    toggle.textContent = open ? 'Collapse all' : 'Expand all';
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  toggle.addEventListener('click', function () {
    var open = !allOpen();
    Array.prototype.forEach.call(sections, function (s) { s.open = open; });
    sync();
  });

  // `toggle` fires on a <details> whenever its state changes, including
  // from a click on one summary, so the button's label keeps up with the
  // sections rather than only with itself.
  Array.prototype.forEach.call(sections, function (s) {
    s.addEventListener('toggle', sync);
  });

  sync();
})();
