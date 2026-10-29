/* Signal: a forward pass through the homepage.

   The homepage is already shaped like a small network: one claim at the
   top, four projects, three ways to work, one button at the end. This
   draws that network as a single routed trace and lets scrolling run the
   forward pass. The signal leaves the corner handle of the "Then I build
   them." frame (the design), reaches each project when the reader does,
   fans out across the three offers, and lands in Book a call (the thing
   that ships).

   It keeps the rules enhance.js keeps:

     - Additive. The SVG is built here and nowhere else, and the
       html.signal-on class that unlocks every rule in signal.css is set
       only after the build succeeds. No JS, no circuit, nothing hidden.
     - It does not sit on what someone is reading. The trunk runs in the
       left gutter and touches content only at a node, and only where a
       line already exists: a row's top rule, a card's edge, a button.
     - Nothing runs at rest. One passive scroll listener queues one rAF,
       and the loop stops as soon as the trace has caught up.
     - Reduced motion gets the finished diagram, static, with the content
       untouched.

   Why a listener and not a scroll timeline: the tip has to sit on the
   reader's line, and where that line falls along the path depends on
   layout (row heights, wrapped headings). A scroll() timeline maps the
   document linearly and would drift off the rows. This is a query
   against layout, the same reason the section marker keeps its listener.
*/
(function () {
  'use strict';

  var root = document.documentElement;
  var scope = document.querySelector('main');
  if (!scope || !window.ResizeObserver || !window.requestAnimationFrame ||
      !document.createElementNS) return;

  var NS = 'http://www.w3.org/2000/svg';

  var READ_LINE   = 0.62; // the tip rides 62% down the viewport...
  var READ_START  = 0.88; // ...after starting here at the top of the page
  var CHASE       = 0.16; // weight, same idea as the peek preview's 0.14
  var STEP_INTRO  = 10;   // px per frame while the intro draws
  var STEP_LIVE   = 64;   // px per frame after, so an anchor jump still draws
  var INTRO_DELAY = 900;  // ms: let the claim frame show before the trace
                          // (repeat visits; a first visit waits for hook:built)
  var BUS_MS      = 900;  // the ways bus, start to last tap

  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var fine = window.matchMedia('(hover: hover) and (pointer: fine)');

  var svg = null, geo = null, sig = '';
  var trunk, head, handle;
  var drawn = 0, raf = 0, queued = 0, timer = 0;
  var started = false, intro = false, still = false;

  /* data-signal-calm on <html> forces the reduced-motion path. It exists
     for the test suite, not for visitors: asserting what a reduced-motion
     reader gets means being able to ask for it without restarting the
     browser under a different OS setting. */
  function calm() { return reduce.matches || root.hasAttribute('data-signal-calm'); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }

  function make(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  /* Layout position relative to <main>, transforms ignored.
     getBoundingClientRect would include the 18px .rise offset of a band
     that has not revealed yet, the circuit would be built 18px low, and
     it would stay there: a ResizeObserver does not fire for transforms. */
  function box(n) {
    if (!n) return null;
    var x = 0, y = 0, w = n.offsetWidth, h = n.offsetHeight;
    while (n && n !== scope) { x += n.offsetLeft; y += n.offsetTop; n = n.offsetParent; }
    if (n !== scope) return null; // the walk escaped <main>; refuse to guess
    return { left: x, top: y, right: x + w, bottom: y + h, width: w, height: h };
  }

  function contentLeft() {
    var shell = scope.querySelector('.shell');
    var b = box(shell);
    if (!b) return 24;
    return b.left + (parseFloat(getComputedStyle(shell).paddingLeft) || 0);
  }

  function lengthAt(g, y) {
    var s = g.segs;
    if (y <= s[0].a[1]) return 0;
    for (var i = 0; i < s.length; i++) {
      var a = s[i].a[1], b = s[i].b[1];
      if (y <= b) {
        var t = b > a ? (y - a) / (b - a) : 1;
        return s[i].from + s[i].len * clamp(t, 0, 1);
      }
    }
    return g.total;
  }

  function pointAt(g, len) {
    var s = g.segs;
    for (var i = 0; i < s.length; i++) {
      if (len <= s[i].from + s[i].len || i === s.length - 1) {
        var t = s[i].len ? clamp((len - s[i].from) / s[i].len, 0, 1) : 0;
        return [s[i].a[0] + (s[i].b[0] - s[i].a[0]) * t,
                s[i].a[1] + (s[i].b[1] - s[i].a[1]) * t];
      }
    }
    return s[0].a;
  }

  function d(points) {
    return 'M' + points.map(function (p) {
      return p[0].toFixed(1) + ' ' + p[1].toFixed(1);
    }).join(' L');
  }

  /* ── 1. measure: where the circuit goes ──────────────── */
  function measure() {
    var claim = scope.querySelector('.claim__line--built');
    var out = scope.querySelector('.band--close .btn--solid');
    var c = box(claim), o = box(out);
    if (!c || !o) return null;

    var L = contentLeft();
    /* The rail sits halfway into the gutter, never closer than 10px to
       the edge of the screen and never further than 32px from the text. */
    var R = Math.round(L - clamp(L * 0.5, 10, 32));
    var fs = parseFloat(getComputedStyle(claim).fontSize) || 16;

    /* Trunk. Only 90 and 45 degree turns, routed like a board trace:
       frame corner, back along the line's bottom edge to the margin, 45
       into the rail, down the rail, 45 into the button's left edge. The
       frame's inset is -0.08em, hence hx.

       When the last line is right-aligned (wide screens) the run back is
       long and passes under nothing: the space left of that line is
       empty by construction. When it is left-aligned the run is a few
       pixels and the route is just the diagonal. Either way it never
       drops straight down from the corner, because the frame's "h1" tag
       sits 10px under that corner while the frame is showing. */
    var hx = c.left - 0.08 * fs, hy = c.bottom;
    var oy = o.top + o.height / 2, dx = o.left - R;
    var run = Math.max(0, hx - R), k = Math.min(run, 18);
    var pts = [[hx, hy]];
    if (run - k > 1) pts.push([R + k, hy]);
    pts.push([R, hy + k], [R, oy - dx], [o.left, oy]);

    var segs = [], total = 0;
    for (var i = 1; i < pts.length; i++) {
      var a = pts[i - 1], b = pts[i];
      var len = Math.hypot(b[0] - a[0], b[1] - a[1]);
      segs.push({ a: a, b: b, from: total, len: len });
      total += len;
    }

    var g = {
      pts: pts, segs: segs, total: total, R: R, L: L, nodes: [],
      top: scope.getBoundingClientRect().top + window.scrollY,
      max: (document.scrollingElement || root).scrollHeight - window.innerHeight
    };

    /* Projects: a node level with each row's number, a stub into it. */
    [].forEach.call(scope.querySelectorAll('.index__row'), function (row) {
      var b = box(row.querySelector('.index__num') || row);
      if (!b) return;
      var y = b.top + b.height / 2;
      g.nodes.push({ y: y, el: row, stub: [[R, y], [L - 6, y]] });
    });

    /* Ways: three cards in a row get a bus with a tap into each, drawn
       left to right so the signal visits them in reading order. Stacked
       cards (narrow screens) get stubs like the rows instead. */
    var cards = [].slice.call(scope.querySelectorAll('.way'));
    var title = scope.querySelector('.band--ways .band__title');
    var cb = cards.map(box);
    var row = cards.length > 1 && cb.every(function (b) {
      return b && Math.abs(b.top - cb[0].top) < 2;
    });
    var tb = box(title);
    if (row && tb) {
      var yb = Math.round((tb.bottom + cb[0].top) / 2);
      g.nodes.push({ y: yb, bus: cards.map(function (k, i) {
        return { el: k, x: cb[i].left + 24, top: cb[i].top };
      }) });
    } else {
      cards.forEach(function (k, i) {
        if (!cb[i]) return;
        var y = cb[i].top + 30;
        g.nodes.push({ y: y, el: k, stub: [[R, y], [cb[i].left, y]] });
      });
    }

    g.nodes.forEach(function (n) { n.at = lengthAt(g, n.y); });
    g.nodes.sort(function (a, b) { return a.at - b.at; });
    g.output = { el: out, at: total, x: o.left, y: oy };
    g.handle = [hx, hy];
    return g;
  }

  /* Geometry only. Scroll position and viewport height are left out on
     purpose, so a mobile URL bar collapsing does not rebuild the SVG. */
  function signature(g) {
    return g.pts.concat(g.nodes.map(function (n) { return [n.y, n.at]; }))
      .map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(';');
  }

  /* ── 2. render: build the SVG from the measurements ──── */
  function pin(parent, x, y, delay) {
    var p = make('g', { class: 'signal__pin', transform: 'translate(' + x.toFixed(1) + ' ' + y.toFixed(1) + ')' }, parent);
    if (delay) p.style.setProperty('--delay', delay + 'ms');
    make('circle', { class: 'signal__halo', r: 7 }, p);
    make('circle', { class: 'signal__ping', r: 3.5 }, p);
    make('circle', { class: 'signal__dot', r: 3.5 }, p);
    p.addEventListener('animationend', function () { p.classList.remove('is-ping'); });
    return p;
  }

  function wire(parent, pts, extra) {
    var w = make('path', { class: 'signal__wire', d: d(pts) }, parent);
    var len = 0;
    for (var i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    w.style.setProperty('--len', len.toFixed(1) + 'px');
    if (extra) for (var k in extra) w.style.setProperty(k, extra[k]);
    return len;
  }

  function render(g, instant) {
    if (svg) svg.remove();
    svg = make('svg', { class: 'signal', 'aria-hidden': 'true', focusable: 'false' });
    if (instant) svg.classList.add('is-instant');
    if (still) svg.classList.add('is-still');

    var ghost = make('path', { class: 'signal__ghost' }, svg);
    var ghosts = [d(g.pts)];
    var branches = make('g', { class: 'signal__branches' }, svg);
    trunk = make('path', { class: 'signal__trunk', d: d(g.pts) }, svg);
    trunk.style.strokeDasharray = g.total.toFixed(1) + ' ' + g.total.toFixed(1);
    var pins = make('g', { class: 'signal__pins' }, svg);

    g.nodes.forEach(function (n) {
      if (n.stub) {
        n.branch = make('g', { class: 'signal__branch' }, branches);
        if (n.stub[1][0] - n.stub[0][0] > 2) {
          wire(n.branch, n.stub);
          ghosts.push(d(n.stub));
        }
        n.pin = pin(pins, g.R, n.y);
      } else if (n.bus) {
        /* Separate paths per segment rather than one path of subpaths:
           whether a dash pattern restarts at each subpath is not something
           to rely on. Each piece gets its own delay and duration, linear,
           so the taps light exactly when their segment arrives. */
        n.branch = make('g', { class: 'signal__branch' }, branches);
        var x = g.R, total = 0, pieces = [];
        n.bus.forEach(function (t) {
          pieces.push([[x, n.y], [t.x, n.y]]);
          pieces.push([[t.x, n.y], [t.x, t.top]]);
          total += (t.x - x) + (t.top - n.y);
          t.arrive = total;
          x = t.x;
        });
        var at = 0;
        pieces.forEach(function (p) {
          var len = Math.hypot(p[1][0] - p[0][0], p[1][1] - p[0][1]);
          wire(n.branch, p, {
            '--delay': Math.round(at / total * BUS_MS) + 'ms',
            '--dur': Math.round(len / total * BUS_MS) + 'ms',
            '--ease': 'linear'
          });
          ghosts.push(d(p));
          at += len;
        });
        n.pin = pin(pins, g.R, n.y);
        n.taps = n.bus.map(function (t) {
          var ms = Math.round(t.arrive / total * BUS_MS);
          if (!still) t.el.style.setProperty('--signal-delay', ms + 'ms');
          return { el: t.el, pin: pin(pins, t.x, t.top, ms) };
        });
      }
    });

    g.output.pin = pin(pins, g.output.x, g.output.y);
    ghost.setAttribute('d', ghosts.join(' '));

    handle = make('rect', {
      class: 'signal__handle', x: (g.handle[0] - 4).toFixed(1), y: (g.handle[1] - 4).toFixed(1),
      width: 8, height: 8
    }, svg);

    head = make('g', { class: 'signal__head is-off' }, svg);
    make('circle', { class: 'signal__head-ring', r: 7 }, head);
    make('circle', { class: 'signal__head-dot', r: 3.5 }, head);

    scope.insertBefore(svg, scope.firstChild);
    geo = g;
    sig = signature(g);

    if (instant) {
      /* Two frames: one for the new nodes to take their lit styles with
         transitions off, one for that to have been painted. */
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { if (svg) svg.classList.remove('is-instant'); });
      });
    }
  }

  /* ── 3. paint: one frame of the forward pass ─────────── */
  function mark(el, on) {
    if (!el || still) return; // reduced motion: the diagram only, the page untouched
    if (on) el.setAttribute('data-signal', 'on');
    else el.removeAttribute('data-signal');
  }

  function light(n, on) {
    if (n.on === on) return;
    n.on = on;
    if (n.pin) n.pin.classList.toggle('is-lit', on);
    if (n.branch) n.branch.classList.toggle('is-on', on);
    if (n.taps) n.taps.forEach(function (t) { t.pin.classList.toggle('is-lit', on); mark(t.el, on); });
    mark(n.el, on);
  }

  function paint() {
    var g = geo;
    trunk.style.strokeDashoffset = (g.total - drawn).toFixed(1);
    var p = pointAt(g, drawn);
    head.setAttribute('transform', 'translate(' + p[0].toFixed(1) + ' ' + p[1].toFixed(1) + ')');
    head.classList.toggle('is-off', drawn < 2 || drawn > g.total - 1);
    handle.classList.toggle('is-lit', started || still);
    for (var i = 0; i < g.nodes.length; i++) light(g.nodes[i], drawn >= g.nodes[i].at - 0.5);
    light(g.output, drawn >= g.total - 0.75);
  }

  function target() {
    var sy = window.scrollY, vh = window.innerHeight;
    /* At the top of the page the reading line starts near the bottom of
       the screen, so the intro has somewhere to draw to: on a tall
       desktop the claim ends below 62%, and the trace would otherwise
       wait, invisible, for the first scroll. It rises to READ_LINE over
       the first half-screen. Slope stays positive (1 - 2 x 0.26), so the tip
       never backs up while someone scrolls down. */
    var line = READ_LINE + (READ_START - READ_LINE) * (1 - clamp(sy / (vh * 0.5), 0, 1));
    var len = lengthAt(geo, sy - geo.top + vh * line);
    /* The last stretch: the button may never reach the reading line on a
       short page, so the final half-screen of scroll finishes the trace. */
    var k = geo.max <= 0 ? 1 : clamp((sy - (geo.max - vh * 0.5)) / (vh * 0.5), 0, 1);
    return len + (geo.total - len) * k;
  }

  function tick() {
    raf = 0;
    if (!geo || !started) return;
    var t = target();
    var diff = t - drawn;
    var cap = intro ? STEP_INTRO : STEP_LIVE;
    if (Math.abs(diff) < 0.5) {
      drawn = t;
      intro = false;
    } else {
      drawn += clamp(diff * CHASE, -cap, cap);
    }
    paint();
    if (drawn !== t) raf = requestAnimationFrame(tick);
  }

  function wake() {
    if (!raf && started && !still) raf = requestAnimationFrame(tick);
  }

  function begin() {
    if (started || !geo) return;
    clearTimeout(timer);
    document.removeEventListener('hook:built', begin);
    started = true;
    paint();
    wake();
  }

  /* ── 4. lifecycle ─────────────────────────────────────── */
  function teardown() {
    clearTimeout(timer);
    document.removeEventListener('hook:built', begin);
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    if (svg) svg.remove();
    svg = null; geo = null; sig = '';
    started = false; intro = false;
    root.classList.remove('signal-on');
    [].forEach.call(scope.querySelectorAll('[data-signal], .way'), function (n) {
      n.removeAttribute('data-signal');
      n.style.removeProperty('--signal-delay');
    });
  }

  function init() {
    teardown();
    still = calm();
    scope.classList.add('signal-scope');
    var g = measure();
    if (!g) { scope.classList.remove('signal-scope'); return; }
    render(g, false);
    root.classList.add('signal-on');

    if (still) {
      drawn = g.total;
      paint();
    } else if (window.scrollY < 8) {
      /* Landed at the top: the trace grows out of the frame once the
         frame has had a moment on its own. */
      drawn = 0;
      intro = true;
      paint();
      if (root.classList.contains('hook-on')) {
        /* The hook is playing: it says when the last line is built.
           The timer is only for a hook that never reports. */
        document.addEventListener('hook:built', begin);
        timer = setTimeout(begin, 5000);
      } else {
        timer = setTimeout(begin, INTRO_DELAY);
      }
    } else {
      /* Landed mid-page (a reload, a #contact link): no intro to watch,
         so the trace is simply where it would be. */
      drawn = target();
      started = true;
      paint();
    }
    requestAnimationFrame(function () { if (svg) svg.classList.add('is-ready'); });
  }

  function rebuild() {
    queued = 0;
    if (!geo) return;
    var g = measure();
    if (!g) return;
    if (signature(g) === sig) {
      geo.top = g.top;
      geo.max = g.max;
      wake();
      return;
    }
    /* Layout changed (fonts landed, a resize, a cover image loaded on a
       phone). Rebuild with transitions off and jump to the right state:
       a resize is not a reason to replay anything. */
    render(g, true);
    svg.classList.add('is-ready');
    if (still) drawn = g.total;
    else if (started) drawn = target();
    paint();
  }

  function queueRebuild() {
    if (!queued) queued = requestAnimationFrame(rebuild);
  }

  function ping(el) {
    if (!geo || still) return;
    var nodes = geo.nodes.concat([geo.output]);
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i], p = null;
      if (n.el === el) p = n.pin;
      else if (n.taps) n.taps.forEach(function (t) { if (t.el === el) p = t.pin; });
      if (p) {
        p.classList.remove('is-ping');
        void p.getBoundingClientRect(); // restart the animation
        p.classList.add('is-ping');
        return;
      }
    }
  }

  init();

  /* The intro draws slowly on purpose. Once someone scrolls, they are
     driving, and the slow cap would read as lag. */
  window.addEventListener('scroll', function () { intro = false; wake(); }, { passive: true });
  window.addEventListener('resize', queueRebuild, { passive: true });
  new ResizeObserver(queueRebuild).observe(scope);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(queueRebuild);
  window.addEventListener('load', queueRebuild);

  if (reduce.addEventListener) reduce.addEventListener('change', init);
  /* For the test suite: start over from the top. */
  document.addEventListener('signal:reset', init);

  /* A ping on hover (fine pointers) and on keyboard focus, so the two
     ways of arriving at a row get the same answer. */
  [].forEach.call(scope.querySelectorAll('.index__row, .way, .band--close .btn--solid'), function (el) {
    el.addEventListener('pointerenter', function (e) {
      if (e.pointerType !== 'touch' && fine.matches) ping(el);
    });
    el.addEventListener('focusin', function () { ping(el); });
  });
})();
