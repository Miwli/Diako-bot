/* ─── Theme ─── */
const THEME_KEY = 'diako-theme';
const LANG_KEY = 'diako-lang';

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-icon');
  if (icon) icon.className = theme === 'warm' ? 'ti ti-moon' : 'ti ti-sun';
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'cool';
  const next = current === 'cool' ? 'warm' : 'cool';
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
  updateChartTheme(next);
}

function updateChartTheme(theme) {
  if (!window.revenueChart) return;
  const rgb = theme === 'warm' ? '249,115,22' : '0,196,190';
  const color = `rgb(${rgb})`;
  const canvas = document.getElementById('revenue-chart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const grad = ctx.createLinearGradient(0, 0, 0, 200);
  grad.addColorStop(0, `rgba(${rgb},0.28)`);
  grad.addColorStop(1, `rgba(${rgb},0)`);
  const ds = window.revenueChart.data.datasets[0];
  ds.borderColor = color;
  ds.backgroundColor = grad;
  ds.pointBackgroundColor = color;
  window.revenueChart.update();
}

/* ─── Language ─── */
function applyLang(lang) {
  const html = document.documentElement;
  html.setAttribute('lang', lang);
  html.setAttribute('dir', lang === 'fa' ? 'rtl' : 'ltr');

  document.querySelectorAll('[data-fa]').forEach(el => {
    const text = lang === 'fa' ? el.getAttribute('data-fa') : el.getAttribute('data-en');
    if (el.children.length > 0) {
      // عنصر دارای فرزند (مثل nav-item با آیکون) — فقط tooltip آپدیت بشه
      el.setAttribute('data-tooltip', text);
    } else {
      el.textContent = text;
    }
  });

  const btn = document.getElementById('lang-btn');
  if (btn) btn.textContent = lang === 'fa' ? 'EN' : 'FA';
}

function toggleLang() {
  const current = document.documentElement.getAttribute('lang') || 'fa';
  const next = current === 'fa' ? 'en' : 'fa';
  localStorage.setItem(LANG_KEY, next);
  applyLang(next);
}

/* ─── Sidebar (mobile) ─── */
function openSidebar() {
  document.querySelector('.sidebar').classList.add('open');
  document.querySelector('.sidebar-overlay').classList.add('open');
}
function closeSidebar() {
  document.querySelector('.sidebar').classList.remove('open');
  document.querySelector('.sidebar-overlay').classList.remove('open');
}

/* ─── Avatar Dropdown ─── */
function toggleAvatarMenu(e) {
  e.stopPropagation();
  document.getElementById('avatar-menu').classList.toggle('open');
}

document.addEventListener('click', () => {
  const menu = document.getElementById('avatar-menu');
  if (menu) menu.classList.remove('open');
});

/* ─── Notification System ─── */
let seenOrderIds = new Set();
let stack = document.getElementById('notif-stack');

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch (_) {}
}

function formatAmount(n) {
  return n.toLocaleString('fa-IR') + ' تومان';
}

function formatAmountEn(n) {
  return n.toLocaleString('en-US') + ' Toman';
}

function showNotif(order) {
  const lang = document.documentElement.getAttribute('lang') || 'fa';
  const card = document.createElement('div');
  card.className = 'notif-card';
  card.dataset.orderId = order.id;

  const user = order.username ? `@${order.username}` : `#${order.telegram_id}`;
  const amount = lang === 'fa' ? formatAmount(order.amount) : formatAmountEn(order.amount);

  card.innerHTML = `
    <div class="notif-header">
      <i class="ti ti-shopping-cart"></i>
      <span data-fa="سفارش جدید" data-en="New Order">${lang === 'fa' ? 'سفارش جدید' : 'New Order'}</span>
    </div>
    <div class="notif-body">${user} — ${order.plan_name}</div>
    <div class="notif-meta">${amount}</div>
    <div class="notif-actions" onclick="event.stopPropagation()">
      <button class="notif-btn approve" title="تأیید"><i class="ti ti-check"></i></button>
      <button class="notif-btn reject" title="رد"><i class="ti ti-x"></i></button>
    </div>
  `;

  card.addEventListener('click', () => { window.location.href = '/diako/orders/'; });
  stack.appendChild(card);

  setTimeout(() => {
    card.classList.add('hiding');
    card.addEventListener('animationend', () => card.remove());
  }, 10000);
}

function updateBadges(count) {
  document.querySelectorAll('.order-badge').forEach(el => {
    el.textContent = count;
    el.classList.toggle('hidden', count === 0);
  });
}

async function pollPendingOrders() {
  try {
    const res = await fetch('/diako/api/pending-orders/');
    if (!res.ok) return;
    const orders = await res.json();

    updateBadges(orders.length);

    const newOrders = orders.filter(o => !seenOrderIds.has(o.id));
    if (newOrders.length > 0 && seenOrderIds.size > 0) {
      beep();
      if (newOrders.length > 1) {
        // stack: show a single "X new orders" card
        const lang = document.documentElement.getAttribute('lang') || 'fa';
        const card = document.createElement('div');
        card.className = 'notif-card';
        card.innerHTML = `
          <div class="notif-header"><i class="ti ti-bell"></i>
            <span>${lang === 'fa' ? newOrders.length + ' سفارش جدید' : newOrders.length + ' new orders'}</span>
          </div>
        `;
        card.addEventListener('click', () => { window.location.href = '/diako/orders/'; });
        stack.appendChild(card);
        setTimeout(() => {
          card.classList.add('hiding');
          card.addEventListener('animationend', () => card.remove());
        }, 10000);
      } else {
        showNotif(newOrders[0]);
      }
    }

    orders.forEach(o => seenOrderIds.add(o.id));
  } catch (_) {}
}

/* ─── Init ─── */
document.addEventListener('DOMContentLoaded', () => {
  // Theme
  const savedTheme = localStorage.getItem(THEME_KEY) || 'cool';
  applyTheme(savedTheme);

  // Lang
  const savedLang = localStorage.getItem(LANG_KEY) ||
    (navigator.language && navigator.language.startsWith('fa') ? 'fa' : 'en');
  applyLang(savedLang);

  // Sidebar overlay click
  const overlay = document.querySelector('.sidebar-overlay');
  if (overlay) overlay.addEventListener('click', closeSidebar);

  // Seed seen IDs from current page so we don't notify on first load
  fetch('/diako/api/pending-orders/')
    .then(r => r.json())
    .then(orders => {
      orders.forEach(o => seenOrderIds.add(o.id));
      updateBadges(orders.length);
    })
    .catch(() => {});

  // Start polling
  setInterval(pollPendingOrders, 30000);
});
