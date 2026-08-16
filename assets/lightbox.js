/* Lightbox — opens a figure at full size.
   Closes on Escape, backdrop click or the close button, keeps focus
   inside while open, and returns focus to the thumbnail on exit. */
(function () {
  'use strict';

  var triggers = document.querySelectorAll('.shot__btn');
  if (!triggers.length) return;

  var box = document.createElement('div');
  box.className = 'lb';
  box.hidden = true;
  box.innerHTML =
    '<button class="lb__close" type="button">Close (Esc)</button>' +
    '<img class="lb__img" alt="">';
  document.body.appendChild(box);

  var img = box.querySelector('.lb__img');
  var closeBtn = box.querySelector('.lb__close');
  var opener = null;

  function open(btn) {
    var pic = btn.querySelector('img');
    opener = btn;
    img.src = btn.dataset.full;
    img.alt = pic ? pic.alt : '';
    box.hidden = false;
    document.body.style.overflow = 'hidden';
    closeBtn.focus();
  }

  function close() {
    box.hidden = true;
    img.removeAttribute('src');
    document.body.style.overflow = '';
    if (opener) { opener.focus(); opener = null; }
  }

  triggers.forEach(function (btn) {
    btn.addEventListener('click', function () { open(btn); });
  });

  closeBtn.addEventListener('click', close);
  box.addEventListener('click', function (e) {
    if (e.target === box) close();          // backdrop only
  });

  document.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'Escape') { close(); return; }
    // Only the close button is focusable inside, so trap Tab onto it.
    if (e.key === 'Tab') { e.preventDefault(); closeBtn.focus(); }
  });
})();
