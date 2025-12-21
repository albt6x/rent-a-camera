// app/static/js/main.js
document.addEventListener('DOMContentLoaded', function () {
  'use strict';

  // --- Show/Hide password (robust) ---
  (function () {
    const btns = Array.from(document.querySelectorAll('.toggle-password'));
    if (!btns.length) return;

    btns.forEach(btn => {
      // prevent duplicate handlers: remove if already marked
      if (btn.__pw_handler_installed) return;
      btn.__pw_handler_installed = true;

      btn.addEventListener('click', function (ev) {
        ev.preventDefault();
        const rawTarget = this.dataset.target || this.getAttribute('data-target');
        if (!rawTarget) return;
        // allow "password" or "#password"
        const sel = rawTarget.startsWith('#') ? rawTarget : ('#' + rawTarget.replace(/^#/, ''));
        const input = document.querySelector(sel);
        if (!input) return;

        const icon = this.querySelector('i');
        if (input.type === 'password') {
          input.type = 'text';
          if (icon) { icon.classList.remove('bi-eye-fill'); icon.classList.add('bi-eye-slash-fill'); }
        } else {
          input.type = 'password';
          if (icon) { icon.classList.remove('bi-eye-slash-fill'); icon.classList.add('bi-eye-fill'); }
        }

        // keep focus on input for nicer UX
        try { input.focus(); } catch (e) {}
      });
    });
  })();

  // --- Flip card triggers ---
  (function () {
    document.querySelectorAll('.flip-trigger').forEach(trigger=>{
      trigger.addEventListener('click', function (e) {
        const inner = this.closest('.flip-card-inner');
        if (!inner) return;
        inner.classList.toggle('is-flipped');
      });
    });
  })();

  // --- Duration preview (kejut harga preview) ---
  (function () {
    function formatRupiah(num) {
      const n = Number(num);
      if (isNaN(n)) return "Rp 0";
      return "Rp " + n.toLocaleString('id-ID', { maximumFractionDigits: 0 });
    }
    function showPriceToast(duration, amount, titleText) {
      let container = document.getElementById('price-toast-container');
      if (!container) {
        container = document.createElement('div');
        container.id = 'price-toast-container';
        container.style.position = 'fixed';
        container.style.top = '1rem';
        container.style.right = '1rem';
        container.style.zIndex = '1080';
        document.body.appendChild(container);
      }
      const toast = document.createElement('div');
      toast.className = 'toast shadow-sm border-0';
      toast.style.minWidth = '220px';
      toast.style.marginBottom = '0.5rem';
      toast.style.background = '#fff';
      toast.style.borderRadius = '0.5rem';
      toast.style.padding = '0.5rem 0.75rem';
      toast.style.boxShadow = '0 6px 18px rgba(0,0,0,0.08)';
      const titleHtml = titleText ? `<div style="font-weight:600; margin-bottom:4px;">${titleText}</div>` : '';
      toast.innerHTML = `<div style="font-size:0.95rem;">${titleHtml}<div><strong>${duration} Jam:</strong> ${formatRupiah(amount)}</div></div>`;
      container.appendChild(toast);
      setTimeout(()=>{ toast.style.transition='opacity 200ms'; toast.style.opacity='0'; setTimeout(()=>toast.remove(),220); }, 1800);
    }

    const previewButtons = document.querySelectorAll('.duration-preview');
    previewButtons.forEach(btn=>{
      btn.addEventListener('click', function (ev) {
        // don't submit when inside form
        if (this.closest('form')) ev.preventDefault();

        const priceStr = this.dataset.price;
        const duration = parseInt(this.dataset.duration, 10) || 24;
        const priceNum = Number(priceStr);
        if (isNaN(priceNum)) { showPriceToast(duration, 0, "Harga tidak tersedia"); return; }
        const factor = duration/24;
        const result = priceNum * factor;

        const card = this.closest('.card');
        if (card) {
          const priceEl = card.querySelector('.price-display');
          if (priceEl) {
            priceEl.dataset.base = Number(priceEl.dataset.base) || priceNum;
            priceEl.innerHTML = `${formatRupiah(result)} <small class="text-muted">/ ${duration} Jam</small>`;
          }
          const siblingBtns = card.querySelectorAll('.duration-preview');
          siblingBtns.forEach(b=>b.classList.remove('active-duration'));
          this.classList.add('active-duration');
          const h = card.querySelector('.card-title');
          const title = h ? h.innerText.trim() : null;
          showPriceToast(duration, result, title);
          return;
        }
        showPriceToast(duration, result);
      });
    });

    // minimal style injection if not present
    const css = document.createElement('style');
    css.innerHTML = `.duration-preview.active-duration { background-color: #0d6efd !important; color:#fff !important; border-color:#0d6efd !important; }`;
    document.head.appendChild(css);
  })();

  // --- Nav search clear/auto-submit (robust) ---
  (function () {
    const form = document.getElementById('nav-search-form');
    const input = document.getElementById('nav-search-input');
    // some templates use id 'nav-search-clear' or 'nav-clear-btn' — support both
    const clearBtn = document.getElementById('nav-search-clear') || document.getElementById('nav-clear-btn');
    if (!form || !input || !clearBtn) return;

    function updateClearVisibility() {
      if (input.value && input.value.trim().length > 0) clearBtn.style.display = '';
      else clearBtn.style.display = 'none';
    }
    clearBtn.addEventListener('click', function (e) {
      e.preventDefault();
      input.value = '';
      updateClearVisibility();
      form.submit();
    });

    let typingTimer;
    input.addEventListener('input', function () {
      updateClearVisibility();
      clearTimeout(typingTimer);
      typingTimer = setTimeout(function () {
        if (!input.value || input.value.trim().length === 0) form.submit();
      }, 400);
    });
    updateClearVisibility();
  })();

});
