const menuToggle = document.querySelector('[data-menu-toggle]');
const mobileMenu = document.querySelector('[data-mobile-menu]');
const staggeredNodes = Array.from(document.querySelectorAll('[data-staggered]'));

function buildStaggeredText(node) {
  const text = node.getAttribute('data-staggered') || '';
  node.innerHTML = Array.from(text).map((char, index) => {
    const display = char === ' ' ? '&nbsp;' : char;
    return `<span class="staggered-char" style="--i:${index}">${display}</span>`;
  }).join('');
}

function setupStaggeredFade() {
  if (!staggeredNodes.length) return;
  staggeredNodes.forEach(buildStaggeredText);

  if (!('IntersectionObserver' in window)) {
    staggeredNodes.forEach(node => node.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.35 });

  staggeredNodes.forEach(node => observer.observe(node));
}

function openMenu() {
  if (!mobileMenu || !menuToggle) return;
  mobileMenu.hidden = false;
  requestAnimationFrame(() => mobileMenu.dataset.state = 'open');
  menuToggle.setAttribute('aria-expanded', 'true');
  menuToggle.setAttribute('aria-label', 'Close menu');
}

function closeMenu() {
  if (!mobileMenu || !menuToggle) return;
  mobileMenu.dataset.state = 'closing';
  menuToggle.setAttribute('aria-expanded', 'false');
  menuToggle.setAttribute('aria-label', 'Open menu');
  window.setTimeout(() => {
    if (mobileMenu.dataset.state === 'closing') {
      mobileMenu.hidden = true;
      delete mobileMenu.dataset.state;
    }
  }, 280);
}

if (menuToggle && mobileMenu) {
  menuToggle.addEventListener('click', () => {
    if (mobileMenu.hidden) openMenu();
    else closeMenu();
  });

  mobileMenu.addEventListener('click', event => {
    if (event.target instanceof HTMLElement && event.target.closest('a')) {
      closeMenu();
    }
  });

  document.addEventListener('click', event => {
    const target = event.target;
    if (!(target instanceof Node)) return;
    if (mobileMenu.hidden) return;
    if (mobileMenu.contains(target) || menuToggle.contains(target)) return;
    closeMenu();
  });
}

setupStaggeredFade();
