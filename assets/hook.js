/* Hook: the claim, designed and then built.

   The first two seconds of a first visit act out the sentence the page
   opens with. The claim arrives as outlines, the way a frame looks
   before anyone has filled it. A multiplayer cursor tagged "Abdou ·
   designing" glides in and selects the last line, "Then I build them.".
   The tag flips to "building", the four lines fill left to right like a
   render pass, and the signal (signal.js) leaves the corner handle of
   that selection and heads down the page.

   Rules:
     - Once per session, never for reduced motion. The inline head script
       decides, before first paint, by setting html.hook-on. If that
       class is absent this file does nothing.
     - Skippable by anything that looks like intent: a wheel, a touch, a
       key, a click. Skipping jumps to the finished state at once; it
       does not hurry the animation along. This matters more at the
       current pace than it did: the sequence runs about 4.3 seconds,
       which is a long time to hold someone who already wants the page.
     - The finished state is the page as it would be without this file.
       Every class it adds is removed, the cursor element is removed,
       and the claim is plain text again.
     - It tells the signal when to start (the hook:built event) instead
       of the signal guessing with a timer.
*/
(function () {
  'use strict';

  var root = document.documentElement;
  var opening = document.querySelector('.opening');
  var claim = opening && opening.querySelector('.opening__claim');
  var built = claim && claim.querySelector('.claim__line--built');

  var cursor = null, tag = null;
  var anims = [], timers = [];
  var running = false, signalled = false;

  function later(fn, ms) { timers.push(setTimeout(fn, ms)); }

  function signal() {
    if (signalled) return;
    signalled = true;
    document.dispatchEvent(new Event('hook:built'));
  }

  /* Leave the page exactly as it would be without the hook. */
  function finish() {
    if (!running) return;
    running = false;
    timers.forEach(clearTimeout);
    timers = [];
    anims.forEach(function (a) { try { a.cancel(); } catch (e) {} });
    anims = [];
    if (cursor) cursor.remove();
    cursor = tag = null;
    if (built) built.classList.remove('is-selected');
    root.classList.add('hook-done');
    root.classList.remove('hook-on', 'hook-build');
    unlisten();
    signal();
  }

  var SKIP = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
  function skip() { finish(); }
  function listen() { SKIP.forEach(function (t) { window.addEventListener(t, skip, { passive: true, once: true }); }); }
  function unlisten() { SKIP.forEach(function (t) { window.removeEventListener(t, skip); }); }

  function makeCursor() {
    var el = document.createElement('div');
    el.className = 'hook-cursor';
    el.setAttribute('aria-hidden', 'true');
    el.innerHTML =
      '<svg class="hook-cursor__arrow" viewBox="0 0 20 22">' +
        '<path d="M2 1.5 L2 18.5 L6.6 14.2 L9.7 21 L12.9 19.6 L9.9 12.9 L16.2 12.9 Z"/>' +
      '</svg>' +
      '<span class="hook-cursor__tag">Abdou · designing</span>';
    opening.appendChild(el);
    tag = el.querySelector('.hook-cursor__tag');
    return el;
  }

  /* Where things are, relative to .opening. Measured once, after fonts,
     because the cursor has to land on the last word. */
  function spot(el) {
    var r = el.getBoundingClientRect(), o = opening.getBoundingClientRect();
    return { x: r.left - o.left, y: r.top - o.top, w: r.width, h: r.height };
  }

  function play() {
    if (!opening || !claim || !built || !Element.prototype.animate) { finish(); return; }

    var b = spot(built);
    var fs = parseFloat(getComputedStyle(built).fontSize) || 48;
    var W = opening.clientWidth;

    /* Lands just inside the end of "them.", a little below centre,
       where a designer would click to select the text layer. */
    var x1 = b.x + b.w - fs * 0.55, y1 = b.y + b.h * 0.58;
    var x0 = Math.min(W + 40, x1 + fs * 6), y0 = y1 - fs * 2.6;

    cursor = makeCursor();

    /* Near the right edge of the screen (phones, and any layout where
       the last line ends close to it) the tag goes to the left of the
       pointer, the way multiplayer cursors do, instead of being cut off.
       Measured with the longer of the two labels. */
    tag.textContent = 'Abdou · designing';
    var o = opening.getBoundingClientRect();
    if (o.left + x1 + 14 + tag.offsetWidth + 12 > window.innerWidth) cursor.classList.add('is-flipped');

    /* 1. Glide in. Three keyframes for a slight arc rather than a ruler
       line.

       SLOWER THAN IT WAS, and the travel is the change. The first
       version had the cursor clicking by 960ms -- the whole design
       half was over before anyone had finished registering that the
       headline was hollow. It takes 1.15s instead of 0.82 now, and the
       pointer is readable for the length of it.

       The delay went back to 120ms, though. At 250 there was a visible
       pause between first paint and anything moving, which with the
       rest of the hero still hidden read as a page that had stalled.
       The slowness belongs in the gesture, not in front of it. */
    anims.push(cursor.animate([
      { transform: 'translate(' + x0 + 'px,' + y0 + 'px)', opacity: 0 },
      { transform: 'translate(' + (x1 + fs * 1.2) + 'px,' + (y1 - fs * 0.9) + 'px)', opacity: 1, offset: 0.7 },
      { transform: 'translate(' + x1 + 'px,' + y1 + 'px)', opacity: 1 }
    ], { duration: 1150, delay: 120, easing: 'cubic-bezier(.22,1,.36,1)', fill: 'forwards' }));

    /* 2. Click: select the last line. */
    later(function () {
      var arrow = cursor.querySelector('.hook-cursor__arrow');
      anims.push(arrow.animate(
        [{ transform: 'scale(1)' }, { transform: 'scale(.82)' }, { transform: 'scale(1)' }],
        { duration: 220, easing: 'ease-out' }));
      built.classList.add('is-selected');
    }, 1450);

    /* 3. Build: the tag says so, the lines fill. */
    later(function () {
      tag.textContent = 'Abdou · building';
      anims.push(tag.animate(
        [{ transform: 'scale(.92)' }, { transform: 'scale(1)' }],
        { duration: 260, easing: 'cubic-bezier(.34,1.3,.5,1)' }));
      root.classList.add('hook-build');
      /* 700ms after the click, not 220. The selection frame and its
         "h1" tag are the point of the first half -- they are the one
         moment the page shows its own workings -- and they used to be
         on screen for a fifth of a second before the fill covered
         them. */
    }, 2150);

    /* 4. The last line is filled: hand over to the signal while the
       frame is still showing, so the trace visibly comes out of it. */
    later(function () {
      signal();
      anims.push(cursor.animate([
        { transform: 'translate(' + x1 + 'px,' + y1 + 'px)', opacity: 1 },
        { transform: 'translate(' + (x1 + fs * 0.8) + 'px,' + (y1 + fs * 1.1) + 'px)', opacity: 0 }
      ], { duration: 640, easing: 'cubic-bezier(.4,0,.6,1)', fill: 'forwards' }));
    }, 3150);

    /* 5. Deselect, then clean up. */
    later(function () { built.classList.remove('is-selected'); }, 3900);
    later(finish, 4350);
  }

  function start() {
    if (!root.classList.contains('hook-on')) return;
    /* The head script's failsafe is for a hook.js that never arrives.
       This one did, so it owns the timing from here. */
    if (window.__hookFailsafe) clearTimeout(window.__hookFailsafe);
    running = true;
    signalled = false;
    /* Restored mid-page (a reload, a back button): the hero is not on
       screen, so there is nobody to perform for. */
    if (window.scrollY > 8) { finish(); return; }
    listen();
    /* Wait for the display face, but not for long: outlines in the
       fallback face are better than a page that waits. */
    var go = function () { if (running && !cursor) play(); };
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(go);
      later(go, 700);
    } else {
      go();
    }
  }

  start();

  /* For the test suite: play the whole sequence again from the top. */
  document.addEventListener('hook:replay', function () {
    finish();
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    root.classList.remove('hook-done');
    root.classList.add('hook-on');
    /* Restart the CSS animations from the outlined state. */
    void claim.offsetWidth;
    start();
  });
})();
