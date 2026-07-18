/* ─── Theme ─── */
const THEME_KEY = 'diako-theme';

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

/* ─── Helpers ─── */
const I18N = window.DIAKO_I18N || {};
const CSRF_TOKEN = (document.cookie.match('(^|;) ?csrftoken=([^;]*)(;|$)') || [])[2] || '';
const IS_FA = (document.documentElement.getAttribute('lang') || 'fa') === 'fa';

async function apiPost(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
    body: JSON.stringify(payload),
  });
  return res.json();
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

/* ─── Toast ─── */
function showToast(title, body, type) {
  const stack = document.getElementById('notif-stack');
  if (!stack) return;
  const card = document.createElement('div');
  card.className = 'notif-card ' + (type || 'info');
  card.innerHTML = `
    <div class="notif-header"><i class="ti ${type === 'error' ? 'ti-alert-circle' : type === 'success' ? 'ti-circle-check' : 'ti-info-circle'}"></i><span></span></div>
    <div class="notif-body"></div>`;
  card.querySelector('.notif-header span').textContent = title;
  card.querySelector('.notif-body').textContent = body || '';
  stack.appendChild(card);
  setTimeout(() => {
    card.classList.add('hiding');
    card.addEventListener('animationend', () => card.remove());
  }, 3500);
}

/* ─── Orders polling ─── */
let seenOrderIds = new Set();

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
  return n.toLocaleString(IS_FA ? 'fa-IR' : 'en-US') + ' ' + (I18N.toman || 'تومان');
}

function showOrderNotif(order) {
  const stack = document.getElementById('notif-stack');
  if (!stack) return;
  const card = document.createElement('div');
  card.className = 'notif-card';
  card.dataset.orderId = order.id;

  const user = order.username ? `@${order.username}` : `#${order.telegram_id}`;
  card.innerHTML = `
    <div class="notif-header">
      <i class="ti ti-shopping-cart"></i>
      <span>${I18N.newOrder || 'سفارش جدید'}</span>
    </div>
    <div class="notif-body">${user} — ${order.plan_name}</div>
    <div class="notif-meta">${formatAmount(order.amount)}</div>`;

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
        const stack = document.getElementById('notif-stack');
        const card = document.createElement('div');
        card.className = 'notif-card';
        card.innerHTML = `
          <div class="notif-header"><i class="ti ti-bell"></i>
            <span>${newOrders.length} ${I18N.newOrders || 'سفارش جدید'}</span>
          </div>`;
        card.addEventListener('click', () => { window.location.href = '/diako/orders/'; });
        stack.appendChild(card);
        setTimeout(() => {
          card.classList.add('hiding');
          card.addEventListener('animationend', () => card.remove());
        }, 10000);
      } else {
        showOrderNotif(newOrders[0]);
      }
      if (typeof window.onNewOrders === 'function') window.onNewOrders(newOrders);
    }

    orders.forEach(o => seenOrderIds.add(o.id));
  } catch (_) {}
}

/* ─── Bot status ─── */
async function pollBotStatus() {
  const el = document.getElementById('bot-status');
  if (!el) return;
  try {
    const res = await fetch('/diako/api/bot-status/');
    const data = await res.json();
    el.classList.toggle('online', !!data.online);
    el.classList.toggle('offline', !data.online);
    const label = el.querySelector('.bs-label');
    if (label) label.textContent = data.online ? (I18N.botOnline || 'آنلاین') : (I18N.botOffline || 'آفلاین');
    if (data.bot_name) el.title = '@' + data.bot_name;
  } catch (_) {}
}

/* ─── Command palette ─── */
const PALETTE_ICONS = { user: 'ti-user', order: 'ti-package', server: 'ti-server', plan: 'ti-list-details' };
let paletteTimer = null;
let paletteIndex = -1;

function openPalette() {
  const p = document.getElementById('palette');
  if (!p) return;
  p.classList.add('open');
  const input = document.getElementById('palette-input');
  input.value = '';
  paletteIndex = -1;
  document.getElementById('palette-list').innerHTML =
    `<div class="palette-empty">${I18N.typeToSearch || 'برای جستجو تایپ کنید'}</div>`;
  setTimeout(() => input.focus(), 50);
}

function closePalette() {
  const p = document.getElementById('palette');
  if (p) p.classList.remove('open');
}

function renderPaletteResults(items) {
  const list = document.getElementById('palette-list');
  paletteIndex = -1;
  if (!items.length) {
    list.innerHTML = `<div class="palette-empty">${I18N.noResults || 'چیزی پیدا نشد'}</div>`;
    return;
  }
  list.innerHTML = '';
  items.forEach(item => {
    const a = document.createElement('a');
    a.className = 'palette-item';
    a.href = item.url;
    a.innerHTML = `
      <span class="pi-ico"><i class="ti ${PALETTE_ICONS[item.kind] || 'ti-search'}"></i></span>
      <span class="pi-text"><small></small></span>
      <span class="pi-kind"></span>`;
    a.querySelector('.pi-text').prepend(document.createTextNode(item.title));
    a.querySelector('.pi-text small').textContent = item.sub || '';
    a.querySelector('.pi-kind').textContent =
      I18N['kind' + item.kind.charAt(0).toUpperCase() + item.kind.slice(1)] || item.kind;
    list.appendChild(a);
  });
}

function movePaletteHl(dir) {
  const items = [...document.querySelectorAll('.palette-item')];
  if (!items.length) return;
  paletteIndex = (paletteIndex + dir + items.length) % items.length;
  items.forEach((el, i) => el.classList.toggle('hl', i === paletteIndex));
  items[paletteIndex].scrollIntoView({ block: 'nearest' });
}

async function paletteSearch(q) {
  try {
    const res = await fetch('/diako/api/search/?q=' + encodeURIComponent(q));
    const data = await res.json();
    renderPaletteResults(data.results || []);
  } catch (_) {}
}

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    openPalette();
    return;
  }
  const p = document.getElementById('palette');
  if (!p || !p.classList.contains('open')) return;
  if (e.key === 'Escape') { closePalette(); }
  else if (e.key === 'ArrowDown') { e.preventDefault(); movePaletteHl(1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); movePaletteHl(-1); }
  else if (e.key === 'Enter') {
    const hl = document.querySelector('.palette-item.hl') || document.querySelector('.palette-item');
    if (hl) window.location.href = hl.href;
  }
});

/* ─── Init ─── */
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(localStorage.getItem(THEME_KEY) || window.PANEL_DEFAULT_THEME || 'cool');

  const overlay = document.querySelector('.sidebar-overlay');
  if (overlay) overlay.addEventListener('click', closeSidebar);

  const palette = document.getElementById('palette');
  if (palette) {
    palette.addEventListener('click', (e) => { if (e.target === palette) closePalette(); });
    document.getElementById('palette-input').addEventListener('input', (e) => {
      clearTimeout(paletteTimer);
      const q = e.target.value.trim();
      if (q.length < 2) {
        document.getElementById('palette-list').innerHTML =
          `<div class="palette-empty">${I18N.typeToSearch || 'برای جستجو تایپ کنید'}</div>`;
        return;
      }
      paletteTimer = setTimeout(() => paletteSearch(q), 250);
    });
  }

  if (document.getElementById('notif-stack')) {
    fetch('/diako/api/pending-orders/')
      .then(r => r.json())
      .then(orders => {
        orders.forEach(o => seenOrderIds.add(o.id));
        updateBadges(orders.length);
      })
      .catch(() => {});
    setInterval(pollPendingOrders, 30000);
  }

  pollBotStatus();
  setInterval(pollBotStatus, 30000);
});
