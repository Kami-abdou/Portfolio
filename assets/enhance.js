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
       off-screen forever.

       There used to be a `.hero` exclusion here, because the marquee band
       animated its own heading on load. That band is gone, and with it the
       one element that had to opt out. Every mask is observed now. */
    document.querySelectorAll('.mask').forEach(function (el) {
      watcher.observe(el);
    });
  }

  /* ── contextual cursor label ──────────────────────
     Says what a click will do, where that is not obvious.

     This replaced a spring-physics trail that drew under the pointer
     everywhere it went. The trail was decorative, was always on, and on
     warm paper its 6%-ink-under-9px-blur read as smudges across the
     headline. The rule it broke is the one this follows: motion should do
     a job, and it should not sit on top of what someone is reading.

     So: nothing at rest, and a label only over the two things on this site
     that are clickable without looking it -- a screenshot, which opens
     full-screen, and a card on the homepage, which opens a case study.
     Buttons and nav links are skipped on purpose; the native pointer
     already says those are pressable and a second hint is noise.

     The native cursor is left alone. A custom cursor that REPLACES the
     system one is unusable the moment its script fails, and this is a
     hint, not a necessity.

     Fine pointers only. There is no hover on a touch screen, so there is
     nothing to label and no element is created at all. */
  if (window.matchMedia('(pointer: fine)').matches) {
    var LABELS = [
      ['.shot__btn', 'Open'],
      ['.card__link', 'Read']
    ];

    var pill = document.createElement('div');
    pill.className = 'cursor-label';
    /* Decorative duplication of an affordance the page already states in
       text; a screen reader should not meet it twice. */
    pill.setAttribute('aria-hidden', 'true');
    document.body.appendChild(pill);

    var px = 0, py = 0, pframe = 0, current = null;

    function placePill() {
      pframe = 0;
      pill.style.transform = 'translate3d(' + px + 'px,' + py + 'px,0)';
    }

    function labelFor(target) {
      if (!target || !target.closest) return null;
      /* Inside the lightbox the image is already full-screen, so "Open"
         would be a lie -- and .shot__btn is reused by the viewer zoom. */
      if (target.closest('.lb')) return null;
      for (var i = 0; i < LABELS.length; i++) {
        if (target.closest(LABELS[i][0])) return LABELS[i][1];
      }
      return null;
    }

    document.addEventListener('pointermove', function (e) {
      /* A pen or mouse only. A coarse pointer firing pointermove once on
         tap would flash the pill for a frame. */
      if (e.pointerType === 'touch') return;
      px = e.clientX;
      py = e.clientY;

      var next = labelFor(e.target);
      if (next !== current) {
        current = next;
        if (next) {
          pill.textContent = next;
          pill.classList.add('is-on');
        } else {
          pill.classList.remove('is-on');
        }
      }
      /* One transform per frame however many moves arrive. */
      if (!pframe) pframe = requestAnimationFrame(placePill);
    }, { passive: true });

    /* Leaving the window, or anything that steals the pointer, must not
       strand the pill mid-screen. */
    function hidePill() {
      current = null;
      pill.classList.remove('is-on');
    }
    document.addEventListener('pointerleave', hidePill);
    document.addEventListener('pointercancel', hidePill);
    window.addEventListener('blur', hidePill);
    /* A click that opens the lightbox leaves the pointer where it was, so
       nothing fires to clear a label that is now wrong. */
    document.addEventListener('click', function (e) {
      if (labelFor(e.target)) hidePill();
    });
  }

  /* ── theme toggle ─────────────────────────────────
     The head script has already applied any stored choice before paint;
     this only wires the control and keeps it in sync.

     "System" is the default and stays the default: nothing is written to
     storage until the visitor actually presses the button. A site that
     stamps a theme on first visit can never follow the system again. */
  var themeBtn = document.querySelector(".theme-toggle");
  if (themeBtn) {
    var root = document.documentElement;
    var sysDark = window.matchMedia("(prefers-color-scheme: dark)");

    function activeTheme() {
      return root.dataset.theme || (sysDark.matches ? "dark" : "light");
    }
    function sync() {
      var dark = activeTheme() === "dark";
      themeBtn.setAttribute("aria-pressed", dark ? "true" : "false");
      /* The label names the DESTINATION, which is what a screen reader user
         needs to decide whether to press it. */
      themeBtn.setAttribute("aria-label",
        dark ? "Switch to the light theme" : "Switch to the dark theme");
    }
    sync();

    /* The Cal booker is an iframe and does not inherit the page's theme,
       so it has to be told. Without this, switching the page to light on
       /contact left a dark calendar sitting inside a light page.

       Guarded on every hop: Cal only exists on /contact, and only once
       its script has loaded. On every other page this is a no-op. */
    /* Cal bakes the theme into the embed's iframe URL when it mounts, and
       ignores a later ("ui", {theme}) call on an inline embed -- measured:
       the call is accepted, and the iframe keeps theme=dark and the class
       cal-element-embed-dark. So the only thing that actually re-themes a
       mounted booker is reloading it with the other value.

       That costs an iframe reload, which is why it happens on an explicit
       toggle and nowhere else. The page's stored preference is already
       passed at mount, so the common case -- someone who chose light
       earlier and comes back -- never reaches this. The alternative was a
       dark calendar sitting in a light page, permanently. */
    function syncCal(theme) {
      try {
        var el = document.getElementById("cal-booker");
        var frame = el && el.querySelector("iframe");
        var src = frame && frame.getAttribute("src");
        if (!src || !/[?&]theme=/.test(src)) return;
        var next = src.replace(/([?&]theme=)[^&]*/, "$1" + theme);
        if (next !== src) frame.setAttribute("src", next);
      } catch (e) {}
    }

    /* The two theme-color metas are keyed to prefers-color-scheme, which
       is right until someone overrides it here: a visitor on a dark OS
       who picks the light theme would keep a near-black status bar above
       a paper page. Writing the chosen colour into BOTH makes whichever
       one matches the right answer. */
    function syncChrome(theme) {
      var bg = getComputedStyle(root)
        .getPropertyValue(theme === "dark" ? "--color-bg" : "--color-light-bg")
        .trim();
      if (!bg) return;
      var metas = document.querySelectorAll('meta[name="theme-color"]');
      Array.prototype.forEach.call(metas, function (m) {
        m.setAttribute("content", bg);
      });
    }

    themeBtn.addEventListener("click", function () {
      var next = activeTheme() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) {}
      sync();
      syncChrome(next);
      syncCal(next);
    });

    /* Follow the system while the visitor has not chosen. addEventListener
       rather than addListener: the old API is deprecated and gone in newer
       Safari. */
    if (sysDark.addEventListener) {
      sysDark.addEventListener("change", function () {
        if (!root.dataset.theme) { sync(); syncCal(activeTheme()); }
      });
    }
  }

  /* Reading progress moved to a scroll timeline in styles.css. It was a
     window scroll listener with a rAF guard, which is the careful version
     of a pattern that no longer needs to exist: the bar is pure animation,
     and CSS can drive it off the main thread.

     The section marker below keeps its listener on purpose. It asks which
     of several headings is nearest the top, which is a query, not an
     animation, and no timeline expresses it. */

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


/* The nav marker: one filled pill that follows the pointer.

   The reference this layout was briefed against positions an absolute
   div per item and animates left/width. This does the same, and adds the
   two things that version leaves out: it returns to the CURRENT PAGE when
   the pointer leaves, so the nav never stops saying where you are, and it
   follows keyboard focus as well as hover.

   Until this runs, the current page is marked with a tinted background in
   CSS. `is-live` hands that job to the marker, so the two never paint at
   once and a visitor with no JS still sees where they are.
*/
(function () {
  var pill = document.querySelector('.site-nav__pill');
  if (!pill) return;
  var marker = pill.querySelector('.site-nav__marker');
  var links = [].slice.call(pill.querySelectorAll('a'));
  if (!marker || !links.length) return;

  var home = pill.querySelector('a[aria-current="page"]');

  function moveTo(link) {
    if (!link) {
      marker.style.width = '0px';
      pill.classList.remove('is-live');
      links.forEach(function (a) { a.classList.remove('is-marked'); });
      return;
    }
    // offsetLeft is relative to the pill, which is the marker's
    // containing block -- so no rect arithmetic and nothing to go stale
    // when the header moves.
    marker.style.left = link.offsetLeft + 'px';
    marker.style.width = link.offsetWidth + 'px';
    pill.classList.add('is-live');
    links.forEach(function (a) { a.classList.toggle('is-marked', a === link); });
  }

  function rest() { moveTo(home); }

  links.forEach(function (link) {
    link.addEventListener('mouseenter', function () { moveTo(link); });
    link.addEventListener('focus', function () { moveTo(link); });
  });
  pill.addEventListener('mouseleave', rest);
  pill.addEventListener('focusout', function (ev) {
    if (!pill.contains(ev.relatedTarget)) rest();
  });

  // The pill is laid out before the fonts land, and Gabarito changes the
  // links' widths when it arrives. Measure after.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(rest);
  }
  window.addEventListener('resize', rest, { passive: true });
  rest();

  /* ── the work index's cover, following the cursor ────
     The covers used to be 1152x720 cards stacked down the page. They are
     one floating preview now: the image appears only once someone has
     shown interest in a particular row, which is the only point at which
     a screenshot is worth its bytes on a homepage.

     Chases the pointer rather than tracking it exactly. A preview locked
     to the cursor reads as a tooltip; one that lags slightly reads as a
     physical thing being dragged along, and the lag is what makes the
     difference. One rAF loop for every row, started on enter and stopped
     on leave -- nothing runs while nobody is hovering.

     Gated three ways: a fine pointer (no tap-flash on phones), no
     reduced-motion preference, and rows actually existing. The CSS hides
     .peek for the first two as well, so a failure here is invisible
     rather than a stuck image.
  */
  var rows = document.querySelectorAll(".index__link[data-peek]");
  /* Both queries are read here rather than borrowed from the module that
     set up the reveals: that one lives in a different IIFE, and reaching
     for its `calm` threw a ReferenceError that killed every statement
     after it in THIS one -- which included the copy-email button. */
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  var still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (rows.length && fine && !still) {
    var peek = document.createElement("div");
    peek.className = "peek";
    var peekImg = document.createElement("img");
    peekImg.alt = "";
    peekImg.decoding = "async";
    peek.appendChild(peekImg);
    document.body.appendChild(peek);

    var tx = 0, ty = 0, cx = 0, cy = 0, raf = null, live = false;

    function frame() {
      /* 0.14 is the chase: low enough to read as weight, high enough
         that the image is never far behind on a fast cross-screen
         sweep. */
      cx += (tx - cx) * 0.14;
      cy += (ty - cy) * 0.14;
      peek.style.transform = "translate3d(" + Math.round(cx) + "px," +
                             Math.round(cy) + "px,0)";
      raf = live ? window.requestAnimationFrame(frame) : null;
    }

    function point(ev) {
      /* Offset up and right of the pointer, and clamped so the preview
         never hangs off the viewport on a row near the edge. */
      var w = peek.offsetWidth, h = peek.offsetHeight;
      tx = Math.min(Math.max(ev.clientX + 24, 8), window.innerWidth - w - 8);
      ty = Math.min(Math.max(ev.clientY - h / 2, 8), window.innerHeight - h - 8);
    }

    Array.prototype.forEach.call(rows, function (row) {
      row.addEventListener("mouseenter", function (ev) {
        var src = row.getAttribute("data-peek");
        if (peekImg.getAttribute("src") !== src) peekImg.setAttribute("src", src);
        point(ev);
        /* Jump to the pointer on the first frame instead of flying in
           from wherever the last row left it. */
        cx = tx; cy = ty;
        peek.classList.add("is-on");
        if (!live) { live = true; frame(); }
      });
      row.addEventListener("mousemove", point);
      row.addEventListener("mouseleave", function () {
        peek.classList.remove("is-on");
        live = false;
        if (raf) { window.cancelAnimationFrame(raf); raf = null; }
      });
    });
  }

  /* ── copy the address instead of launching a mail client ────
     The page ships BOTH controls: a <button> that copies, and a mailto
     <a> hidden next to it. This module owns which one is shown.

     Three cases, and only the first is the happy one:

       clipboard available  -> the button stays, the mailto stays hidden
       no Clipboard API     -> swap them, so the visitor gets a mail link
       JS never runs        -> the <noscript> rule in head() swaps them

     navigator.clipboard is undefined on a page served over plain http
     from anything but localhost, which is not an edge case here: it is
     how this site is previewed. Checking for it rather than assuming it
     is the difference between a fallback and a dead button.

     The label swap and the announcement are deliberately separate. A
     screen reader does not reliably announce the accessible name of a
     button changing under the user's own focus, so the word "Copied" is
     written into a role=status sibling, which is announced because it is
     a live region. The visible label changes for everyone else.
  */
  var copyables = document.querySelectorAll('.js-copy');
  if (copyables.length) {
    var canCopy = !!(navigator.clipboard && navigator.clipboard.writeText);
    Array.prototype.forEach.call(copyables, function (btn) {
      var row = btn.parentNode;
      var fallback = row.querySelector('.js-copy-fallback');
      if (!canCopy) {
        btn.style.display = 'none';
        if (fallback) fallback.style.display = 'inline-flex';
        return;
      }
      var status = row.querySelector('[data-copy-status]');
      var original = btn.textContent;
      var timer = null;
      btn.addEventListener('click', function () {
        navigator.clipboard.writeText(btn.getAttribute('data-copy')).then(
          function () {
            btn.textContent = 'Copied';
            if (status) status.textContent = 'Email address copied';
            window.clearTimeout(timer);
            /* Two seconds, per the brief. Cleared first, so a second
               click does not let the earlier timer cut the new one
               short. */
            timer = window.setTimeout(function () {
              btn.textContent = original;
              if (status) status.textContent = '';
            }, 2000);
          },
          function () {
            /* Permission denied or a document that is not focused. The
               address is still reachable, so say so rather than
               failing silently. */
            btn.style.display = 'none';
            if (fallback) fallback.style.display = 'inline-flex';
            if (status) status.textContent = 'Copying is blocked; use the email link';
          }
        );
      });
    });
  }
})();
