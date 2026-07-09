import json
import os
from django.conf import settings as dj_settings
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.translation import gettext as _
from asgiref.sync import async_to_sync
from django.db.models import Count, Q, Subquery, OuterRef, IntegerField, Value
from django.db.models.functions import Coalesce
from shared_lib.db import (
    get_admin_stats, get_all_keyboard_buttons, get_keyboard_actions, get_all_texts,
    get_setting, get_all_keyboard_buttons_grouped,
)
from .models import (
    Orders, Servers, Users, Plans, DiscountCodes, TopUpRequests, Transactions,
    Tutorials, Faqs, ExtraVolumePlans, ExtraVolumeRequests,
    ExtraTimePlans, ExtraTimeRequests, LocationChangeRequests,
    PaymentCards, RequiredChannels,
)


def _page_ctx(request, nav, tab=None):
    titles = {
        'dashboard': _('داشبورد'),
        'sales':     _('زیرساخت'),
        'orders':    _('سفارش‌ها'),
        'users':     _('کاربران'),
        'finance':   _('مالی'),
        'settings':  _('تنظیمات'),
        'customize': _('شخصی‌سازی'),
    }
    groups = {
        'sales': [
            ('servers',    'diako_servers',       _('سرورها'),            'ti-server'),
            ('monitoring', 'diako_monitoring',    _('مانیتورینگ'),        'ti-world'),
            ('plans',      'diako_plans',         _('پلن‌ها'),             'ti-list-details'),
        ],
        'orders': [
            ('orders',   'diako_orders',          _('سفارش‌ها'),           'ti-package'),
            ('extra',    'diako_extra_requests',  _('درخواست‌های اضافه'),  'ti-clock-plus'),
        ],
        'settings': [
            ('bot',      'diako_settings_bot',    _('ربات'),              'ti-robot'),
            ('database', 'diako_import_export',   _('دیتابیس'),           'ti-database'),
        ],
        'customize': [
            ('keyboard', 'diako_keyboard_editor', _('کیبورد'),            'ti-keyboard'),
            ('texts',    'diako_texts_editor',    _('متن‌ها'),             'ti-text-size'),
        ],
    }
    tabs = [
        {'key': key, 'url': reverse(name), 'label': label, 'icon': icon, 'active': key == tab}
        for key, name, label, icon in groups.get(nav, [])
    ]
    return {
        'nav': nav,
        'tabs': tabs,
        'page_title': titles.get(nav, _('دیاکو')),
        'admin_username': request.user.username,
    }


def login_view(request):
    if request.user.is_authenticated:
        return redirect('diako_dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('diako_dashboard')
        else:
            error = True

    return render(request, 'diako/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('diako_login')


@login_required
def dashboard_view(request):
    stats = async_to_sync(get_admin_stats)()
    servers = list(Servers.objects.all())
    online_count = sum(1 for s in servers if s.is_active)
    recent_orders = list(
        Orders.objects.select_related('plan')
        .exclude(order_type='free_test')
        .order_by('-id')[:4]
    )

    checklist = {
        'server': Servers.objects.exists(),
        'plan':   Plans.objects.exists(),
        'card':   PaymentCards.objects.exists(),
        'sale':   Orders.objects.filter(status='approved').exists(),
    }
    setup_done = all(checklist.values())

    feed = []
    for o in Orders.objects.select_related('plan').order_by('-id')[:6]:
        feed.append({
            'kind': 'order',
            'status': o.status,
            'title': f'@{o.username}' if o.username else f'#{o.user_id}',
            'sub': o.plan.name if o.plan_id else '—',
            'time': o.created_at,
        })
    for u in Users.objects.order_by('-created_at')[:4]:
        feed.append({
            'kind': 'user',
            'title': u.first_name or (f'@{u.username}' if u.username else f'#{u.user_id}'),
            'sub': '',
            'time': u.created_at,
        })
    feed.sort(key=lambda x: x['time'] or '', reverse=True)
    feed = feed[:8]

    ctx = {
        'stats': stats,
        'servers': servers,
        'online_count': online_count,
        'recent_orders': recent_orders,
        'checklist': checklist,
        'setup_done': setup_done,
        'feed': feed,
    }
    ctx.update(_page_ctx(request, 'dashboard'))
    return render(request, 'diako/dashboard.html', ctx)


_TEXT_GROUPS = [
    ("خوش‌آمدگویی",  ["start", "coming", "profile"]),
    ("خرید",          ["buy", "payment", "order", "topup"]),
    ("تست رایگان",    ["free"]),
    ("سرویس‌ها",      ["services", "service", "status", "renew", "delete", "sublink"]),
    ("کیف پول",       ["wallet"]),
    ("پشتیبانی",      ["support"]),
    ("آموزش و FAQ",   ["tutorial", "faq"]),
    ("تخفیف و دعوت", ["discount", "referral"]),
    ("ادمین",         ["admin"]),
]

def _group_texts(rows):
    raw = [{'key': r['key'], 'value': r['value']} for r in rows]
    grouped = {name: [] for name, _prefixes in _TEXT_GROUPS}
    grouped["سایر"] = []
    for t in raw:
        prefix = t['key'].split('_')[0]
        placed = False
        for name, prefixes in _TEXT_GROUPS:
            if prefix in prefixes:
                grouped[name].append(t)
                placed = True
                break
        if not placed:
            grouped["سایر"].append(t)
    if not grouped["سایر"]:
        del grouped["سایر"]
    return grouped


@login_required
def texts_editor_view(request):
    all_texts_rows = async_to_sync(get_all_texts)()
    grouped = _group_texts(all_texts_rows)
    ctx = {
        'groups_json': json.dumps(grouped, ensure_ascii=False),
    }
    ctx.update(_page_ctx(request, 'customize', 'texts'))
    return render(request, 'diako/texts_editor.html', ctx)


@login_required
def orders_view(request):
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('q', '').strip()
    page_num = max(1, int(request.GET.get('page', 1)))
    per_page = 20

    qs = Orders.objects.select_related('plan').order_by('-id')
    if status_filter != 'all':
        qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(username__icontains=search)

    stats = {
        'all':      Orders.objects.count(),
        'pending':  Orders.objects.filter(status='pending').count(),
        'approved': Orders.objects.filter(status='approved').count(),
        'rejected': Orders.objects.filter(status='rejected').count(),
    }

    total = qs.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page_num = min(page_num, total_pages)
    orders = list(qs[(page_num - 1) * per_page: page_num * per_page])

    pr_start = max(1, page_num - 3)
    pr_end   = min(total_pages + 1, page_num + 4)

    ctx = {
        'orders':        orders,
        'stats':         stats,
        'status_filter': status_filter,
        'search':        search,
        'page':          page_num,
        'total_pages':   total_pages,
        'total':         total,
        'page_range':    range(pr_start, pr_end),
    }
    ctx.update(_page_ctx(request, 'orders', 'orders'))
    return render(request, 'diako/orders.html', ctx)


@login_required
def users_view(request):
    filter_type = request.GET.get('filter', 'newest')
    if filter_type not in ('newest', 'topbuyers', 'banned'):
        filter_type = 'newest'
    search = request.GET.get('q', '').strip()
    page_num = max(1, int(request.GET.get('page', 1)))
    per_page = 20

    dash_stats = async_to_sync(get_admin_stats)()
    stats = {
        'all':     dash_stats.get('total_users', 0),
        'banned':  dash_stats.get('banned_users', 0),
        'today':   dash_stats.get('users_today', 0),
        'wallet':  dash_stats.get('total_wallet', 0),
    }

    if search:
        if search.lstrip('-').isdigit():
            qs = Users.objects.filter(user_id=int(search))
        else:
            q_clean = search.lstrip('@')
            qs = Users.objects.filter(
                Q(username__icontains=q_clean) | Q(first_name__icontains=search)
            )
        total = qs.count()
        users = list(qs.order_by('-created_at')[:20])
        total_pages = 1
        page_num = 1
        page_range = range(1, 2)
    else:
        qs = Users.objects.all()
        if filter_type == 'banned':
            qs = qs.filter(is_banned=1)
        elif filter_type == 'topbuyers':
            approved_subq = (
                Orders.objects.filter(user_id=OuterRef('user_id'), status='approved')
                .values('user_id')
                .annotate(c=Count('id'))
                .values('c')[:1]
            )
            qs = qs.annotate(
                approved_orders=Coalesce(
                    Subquery(approved_subq, output_field=IntegerField()),
                    Value(0),
                )
            ).order_by('-approved_orders', '-user_id')
        else:
            qs = qs.order_by('-created_at')

        total = qs.count()
        total_pages = max(1, (total + per_page - 1) // per_page)
        page_num = min(page_num, total_pages)
        users = list(qs[(page_num - 1) * per_page: page_num * per_page])
        pr_start = max(1, page_num - 3)
        pr_end = min(total_pages + 1, page_num + 4)
        page_range = range(pr_start, pr_end)

    ctx = {
        'users':          users,
        'stats':          stats,
        'filter_type':    filter_type,
        'search':         search,
        'page':           page_num,
        'total_pages':    total_pages,
        'total':          total if not search else len(users),
        'page_range':     page_range,
    }
    ctx.update(_page_ctx(request, 'users'))
    return render(request, 'diako/users.html', ctx)


@login_required
def keyboard_editor_view(request):
    buttons = async_to_sync(get_all_keyboard_buttons)("user_main")
    actions = async_to_sync(get_keyboard_actions)()
    all_texts_rows = async_to_sync(get_all_texts)()
    bot_texts = {row['key']: row['value'] for row in all_texts_rows}
    ctx = {
        'buttons_json': json.dumps(buttons, ensure_ascii=False),
        'actions_json': json.dumps(actions, ensure_ascii=False),
        'bot_texts_json': json.dumps(bot_texts, ensure_ascii=False),
    }
    ctx.update(_page_ctx(request, 'customize', 'keyboard'))
    return render(request, 'diako/keyboard_editor.html', ctx)


@login_required
def monitoring_view(request):
    ctx = _page_ctx(request, 'sales', 'monitoring')
    return render(request, 'diako/monitoring.html', ctx)


@login_required
def import_export_view(request):
    db_path = str(dj_settings.DATABASES['default']['NAME'])
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    db_stats = {
        'size_mb': round(db_size / (1024 * 1024), 2),
        'users': Users.objects.count(),
        'orders': Orders.objects.count(),
        'servers': Servers.objects.count(),
        'plans': Plans.objects.count(),
    }
    ctx = {'db_stats': db_stats}
    ctx.update(_page_ctx(request, 'settings', 'database'))
    return render(request, 'diako/import_export.html', ctx)


# ─── سرورها ──────────────────────────────────────────────────────────────────

@login_required
def servers_view(request):
    servers = list(Servers.objects.all().order_by('id'))
    plan_counts = {
        r['server_id']: r['c']
        for r in Plans.objects.filter(server_id__isnull=False).values('server_id').annotate(c=Count('id'))
    }
    for s in servers:
        s.plan_count = plan_counts.get(s.id, 0)
    ctx = {'servers': servers}
    ctx.update(_page_ctx(request, 'sales', 'servers'))
    return render(request, 'diako/servers.html', ctx)


# ─── پلن‌ها ───────────────────────────────────────────────────────────────────

@login_required
def plans_view(request):
    plans = list(Plans.objects.select_related('server').all().order_by('server__id', 'id'))
    servers = list(Servers.objects.all())
    ctx = {'plans': plans, 'servers': servers}
    ctx.update(_page_ctx(request, 'sales', 'plans'))
    return render(request, 'diako/plans.html', ctx)


# ─── مالی ─────────────────────────────────────────────────────────────────────

@login_required
def finance_view(request):
    cards = list(PaymentCards.objects.all())
    card_active = async_to_sync(get_setting)('card_active') == '1'
    card_mode = async_to_sync(get_setting)('card_select_mode') or 'round_robin'
    card_fixed_id = async_to_sync(get_setting)('card_fixed_id')
    topups = list(TopUpRequests.objects.all().order_by('-id')[:20])
    transactions = list(Transactions.objects.select_related('user').order_by('-id')[:20])
    discounts = list(DiscountCodes.objects.all().order_by('-id'))
    stats = async_to_sync(get_admin_stats)()
    ctx = {
        'cards': cards,
        'card_active': card_active,
        'card_mode': card_mode,
        'card_fixed_id': int(card_fixed_id) if card_fixed_id else None,
        'topups': topups,
        'transactions': transactions,
        'discounts': discounts,
        'rev_total': stats.get('rev_total', 0),
        'rev_month': stats.get('rev_month', 0),
        'rev_today': stats.get('rev_today', 0),
        'total_wallet': stats.get('total_wallet', 0),
    }
    ctx.update(_page_ctx(request, 'finance'))
    return render(request, 'diako/finance.html', ctx)


# ─── درخواست‌های افزودن حجم/زمان ─────────────────────────────────────────────

@login_required
def extra_requests_view(request):
    ev_requests = list(ExtraVolumeRequests.objects.all().order_by('-id')[:20])
    et_requests = list(ExtraTimeRequests.objects.all().order_by('-id')[:20])
    lc_requests = list(LocationChangeRequests.objects.all().order_by('-id')[:20])
    ev_plans = list(ExtraVolumePlans.objects.all().order_by('order_index'))
    et_plans = list(ExtraTimePlans.objects.all().order_by('order_index'))
    server_names = {s.id: s.name for s in Servers.objects.all()}
    for r in lc_requests:
        r.from_server_name = server_names.get(r.from_server_id, f"#{r.from_server_id}")
        r.to_server_name = server_names.get(r.to_server_id, f"#{r.to_server_id}")
    changeloc_need_admin = (async_to_sync(get_setting)('changeloc_need_admin') or '1') == '1'
    ctx = {
        'ev_requests': ev_requests,
        'et_requests': et_requests,
        'lc_requests': lc_requests,
        'ev_plans': ev_plans,
        'et_plans': et_plans,
        'changeloc_need_admin': changeloc_need_admin,
    }
    ctx.update(_page_ctx(request, 'orders', 'extra'))
    return render(request, 'diako/extra_requests.html', ctx)


# ─── تنظیمات ربات (جوین اجباری + آموزش‌ها) ───────────────────────────────────

@login_required
def settings_bot_view(request):
    channels = list(RequiredChannels.objects.all())
    force_join_enabled = async_to_sync(get_setting)('force_join_enabled') == '1'
    tutorials = list(Tutorials.objects.all().order_by('order_index', 'id'))
    faqs = list(Faqs.objects.all().order_by('order_index', 'id'))
    ctx = {
        'channels': channels,
        'force_join_enabled': force_join_enabled,
        'tutorials': tutorials,
        'faqs': faqs,
    }
    ctx.update(_page_ctx(request, 'settings', 'bot'))
    return render(request, 'diako/settings_bot.html', ctx)
