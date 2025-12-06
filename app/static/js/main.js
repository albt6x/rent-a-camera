// app/static/js/main.js

document.addEventListener("DOMContentLoaded", function() {
    // --- 1. FUNGSI UNTUK SHOW/HIDE PASSWORD ---
    const toggleButtons = document.querySelectorAll(".toggle-password");
    toggleButtons.forEach(button => {
        button.addEventListener("click", function() {
            const targetInput = document.querySelector(this.dataset.target);
            const icon = this.querySelector("i");

            if (targetInput) {
                if (targetInput.type === "password") {
                    targetInput.type = "text";
                    if (icon) {
                        icon.classList.remove("bi-eye-fill");
                        icon.classList.add("bi-eye-slash-fill");
                    }
                } else {
                    targetInput.type = "password";
                    if (icon) {
                        icon.classList.remove("bi-eye-slash-fill");
                        icon.classList.add("bi-eye-fill");
                    }
                }
            }
        });
    });

    // --- 2. FUNGSI UNTUK FLIP CARD ---
    const flipTriggers = document.querySelectorAll(".flip-trigger");
    flipTriggers.forEach(trigger => {
        trigger.addEventListener("click", function() {
            const cardInner = this.closest('.flip-card-inner');
            if (cardInner) {
                cardInner.classList.toggle('is-flipped');
            }
        });
    });

    // --- HELPERS FORMAT & TOAST ---
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

        toast.innerHTML = `
          <div style="font-size:0.95rem;">
            ${titleHtml}
            <div><strong>${duration} Jam:</strong> ${formatRupiah(amount)}</div>
          </div>
        `;
        container.appendChild(toast);

        // show + auto remove
        setTimeout(() => {
            toast.style.transition = "opacity 200ms";
            toast.style.opacity = "0";
            setTimeout(() => toast.remove(), 220);
        }, 1800);
    }

    // --- 3. PREVIEW DURATION PRICE (HOME preview-only buttons) ---
    const previewButtons = document.querySelectorAll(".duration-preview");
    previewButtons.forEach(btn => {
        btn.addEventListener("click", function(e) {
            // Jika tombol berada di dalam form, jangan submit
            if (this.closest('form')) {
                e.preventDefault();
            }

            const priceStr = this.dataset.price;
            const duration = parseInt(this.dataset.duration, 10) || 24;

            // convert to number safely
            const priceNum = Number(priceStr);
            if (isNaN(priceNum)) {
                showPriceToast(duration, 0, "Harga tidak tersedia");
                return;
            }

            const factor = duration / 24;
            const result = priceNum * factor;

            // Cari card terdekat
            const card = this.closest('.card');

            // 1) Jika ada elemen price-display di dalam card, update langsung tampilan harga
            if (card) {
                const priceEl = card.querySelector(".price-display");
                if (priceEl) {
                    priceEl.dataset.base = Number(priceEl.dataset.base) || priceNum; // keep base consistent
                    priceEl.innerHTML = `${formatRupiah(result)} <small class="text-muted">/ ${duration} Jam</small>`;
                }

                // tambahkan class aktif ke tombol yang dipilih
                const siblingBtns = card.querySelectorAll(".duration-preview");
                siblingBtns.forEach(b => b.classList.remove("active-duration"));
                this.classList.add("active-duration");

                // optional: ambil judul item untuk toast
                const h = card.querySelector('.card-title');
                const title = h ? h.innerText.trim() : null;
                showPriceToast(duration, result, title);
                return;
            }

            // 2) Kalau nggak ada card (mis. tombol di tempat lain), tetap tampilkan toast
            showPriceToast(duration, result);
        });
    });

    // small CSS injection for active-duration visual (in case not in CSS)
    const style = document.createElement('style');
    style.innerHTML = `
      .duration-preview.active-duration {
        background-color: #0d6efd !important;
        color: #fff !important;
        border-color: #0d6efd !important;
      }
    `;
    document.head.appendChild(style);

    // --- 4. SEARCH: tombol clear + auto-submit saat input dikosongkan ---
    (function() {
        const form = document.getElementById('nav-search-form');
        const input = document.getElementById('nav-search-input');
        const clearBtn = document.getElementById('nav-search-clear');

        if (!form || !input || !clearBtn) return;

        // Tampilkan/sekretkan tombol X berdasarkan isi input
        function updateClearVisibility() {
            if (input.value && input.value.trim().length > 0) {
                clearBtn.style.display = '';
            } else {
                clearBtn.style.display = 'none';
            }
        }

        // Saat tombol X diklik -> kosongkan dan submit form (atau redirect ke katalog tanpa q)
        clearBtn.addEventListener('click', function(e) {
            e.preventDefault();
            input.value = '';
            updateClearVisibility();

            // Submit form (GET tanpa q) -> katalog akan menampilkan semua item
            form.submit();
        });

        // Jika user menghapus manual sampai kosong -> submit otomatis agar kembali ke semua item
        let typingTimer;
        input.addEventListener('input', function() {
            updateClearVisibility();

            // debounced check: jika kosong setelah 400ms, submit
            clearTimeout(typingTimer);
            typingTimer = setTimeout(function() {
                if (!input.value || input.value.trim().length === 0) {
                    form.submit();
                }
            }, 400);
        });

        // inisialisasi awal
        updateClearVisibility();
    })();

});
