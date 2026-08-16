/* ══════════════════════════════════════════════
   Designer cursor — dot + trailing ring
   · dot tracks the pointer 1:1
   · ring trails with eased interpolation
   · expands to a filled "VIEW" disc over project cards
   · mix-blend-mode in CSS handles light/dark inversion
   Desktop pointers only; respects prefers-reduced-motion.
   ══════════════════════════════════════════════ */
(function () {
  'use strict';

  var fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  var calm = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (!fine.matches || calm.matches) return;

  // ── build markup (avoids duplicating it in every page) ──
  var root = document.createElement('div');
  root.id = 'cursor';
  root.setAttribute('aria-hidden', 'true');
  root.innerHTML =
    '<div class="c-ring"><span class="c-label">View</span></div>' +
    '<div class="c-dot"></div>';
  document.body.appendChild(root);

  var ring  = root.querySelector('.c-ring');
  var dot   = root.querySelector('.c-dot');
  var label = root.querySelector('.c-label');

  // start off-screen so it doesn't flash at 0,0
  var mx = -100, my = -100;   // pointer
  var rx = -100, ry = -100;   // ring (trails)
  var seen = false;

  // ── selectors that change the cursor state ──
  var VIEW_SEL = '.work, .sketch, .wip';
  var LINK_SEL = 'a, button, .chip, .social, .about-bullet, .nav-links a, .contact-mail';

  function onMove(e) {
    mx = e.clientX;
    my = e.clientY;
    if (!seen) {                       // snap into place on first move
      rx = mx; ry = my; seen = true;
      document.body.classList.remove('cur-out');
    }
    dot.style.transform = 'translate(' + mx + 'px,' + my + 'px) translate(-50%,-50%)';
  }

  // ── ring easing loop ──
  function frame() {
    rx += (mx - rx) * 0.16;
    ry += (my - ry) * 0.16;
    ring.style.transform = 'translate(' + rx + 'px,' + ry + 'px) translate(-50%,-50%)';
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  // ── hover state, delegated so it survives DOM changes ──
  function onOver(e) {
    var t = e.target;
    if (!t || t.nodeType !== 1) return;

    var view = t.closest(VIEW_SEL);
    if (view) {
      // let a card declare its own label: data-cursor="Read case study"
      label.textContent = view.getAttribute('data-cursor') || 'View';
      document.body.classList.add('cur-view');
      document.body.classList.remove('cur-link');
      return;
    }
    document.body.classList.remove('cur-view');
    document.body.classList.toggle('cur-link', !!t.closest(LINK_SEL));
  }

  document.addEventListener('mousemove', onMove, { passive: true });
  document.addEventListener('mouseover', onOver, { passive: true });

  document.addEventListener('mousedown', function () {
    document.body.classList.add('cur-down');
  }, { passive: true });

  document.addEventListener('mouseup', function () {
    document.body.classList.remove('cur-down');
  }, { passive: true });

  // hide when the pointer leaves the window
  document.addEventListener('mouseleave', function () {
    document.body.classList.add('cur-out');
  });
  document.addEventListener('mouseenter', function () {
    document.body.classList.remove('cur-out');
  });

  // clear states if the tab loses focus mid-hover
  window.addEventListener('blur', function () {
    document.body.classList.remove('cur-down', 'cur-view', 'cur-link');
  });
})();
