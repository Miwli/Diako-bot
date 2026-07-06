import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
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
    ExtraTimePlans, ExtraTimeRequests,
)


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
    return render(request, 'diako/dashboard.html', {
        'stats': stats,
        'servers': servers,
        'online_count': online_count,
        'recent_orders': recent_orders,
        'admin_username': request.user.username,
    })


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
    grouped = {name: [] for name, _ in _TEXT_GROUPS}
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
    return render(request, 'diako/texts_editor.html', {
        'groups_json': json.dumps(grouped, ensure_ascii=False),
        'admin_username': request.user.username,
    })


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

    return render(request, 'diako/orders.html', {
        'orders':        orders,
        'stats':         stats,
        'status_filter': status_filter,
        'search':        search,
        'page':          page_num,
        'total_pages':   total_pages,
        'total':         total,
        'page_range':    range(pr_start, pr_end),
        'admin_username': request.user.username,
    })


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

    return render(request, 'diako/users.html', {
        'users':          users,
        'stats':          stats,
        'filter_type':    filter_type,
        'search':         search,
        'page':           page_num,
        'total_pages':    total_pages,
        'total':          total if not search else len(users),
        'page_range':     page_range,
        'admin_username': request.user.username,
    })


@login_required
def keyboard_editor_view(request):
    buttons = async_to_sync(get_all_keyboard_buttons)("user_main")
    actions = async_to_sync(get_keyboard_actions)()
    all_texts_rows = async_to_sync(get_all_texts)()
    bot_texts = {row['key']: row['value'] for row in all_texts_rows}
    return render(request, 'diako/keyboard_editor.html', {
        'buttons_json': json.dumps(buttons, ensure_ascii=False),
        'actions_json': json.dumps(actions, ensure_ascii=False),
        'bot_texts_json': json.dumps(bot_texts, ensure_ascii=False),
        'admin_username': request.user.username,
    })


@login_required
def import_export_view(request):
    all_texts_rows = async_to_sync(get_all_texts)()
    bot_texts = {row['key']: row['value'] for row in all_texts_rows}
    keyboards = async_to_sync(get_all_keyboard_buttons_grouped)()
    actions = async_to_sync(get_keyboard_actions)()
    return render(request, 'diako/import_export.html', {
        'bot_texts_json':        json.dumps(bot_texts, ensure_ascii=False),
        'keyboards_json':        json.dumps(keyboards, ensure_ascii=False),
        'keyboard_actions_json': json.dumps(actions, ensure_ascii=False),
        'admin_username':        request.user.username,
    })


# ─── سرورها ──────────────────────────────────────────────────────────────────

@login_required
def servers_view(request):
    servers = list(Servers.objects.all().order_by('id'))
    return render(request, 'diako/servers.html', {
        'servers': servers,
        'admin_username': request.user.username,
    })


# ─── پلن‌ها ───────────────────────────────────────────────────────────────────

@login_required
def plans_view(request):
    plans = list(Plans.objects.select_related('server').all().order_by('server__id', 'id'))
    servers = list(Servers.objects.all())
    return render(request, 'diako/plans.html', {
        'plans': plans,
        'servers': servers,
        'admin_username': request.user.username,
    })


# ─── مالی ─────────────────────────────────────────────────────────────────────

@login_required
def finance_view(request):
    card_number = async_to_sync(get_setting)('card_number') or ''
    card_owner = async_to_sync(get_setting)('card_owner') or ''
    topups = list(TopUpRequests.objects.all().order_by('-id')[:20])
    transactions = list(Transactions.objects.select_related('user').order_by('-id')[:20])
    return render(request, 'diako/finance.html', {
        'card_number': card_number,
        'card_owner': card_owner,
        'topups': topups,
        'transactions': transactions,
        'admin_username': request.user.username,
    })


# ─── کدهای تخفیف ──────────────────────────────────────────────────────────────

@login_required
def discounts_view(request):
    discounts = list(DiscountCodes.objects.all().order_by('-id'))
    return render(request, 'diako/discounts.html', {
        'discounts': discounts,
        'admin_username': request.user.username,
    })


# ─── آموزش‌ها و سوالات متداول ─────────────────────────────────────────────────

@login_required
def tutorials_view(request):
    tutorials = list(Tutorials.objects.all().order_by('order_index', 'id'))
    faqs = list(Faqs.objects.all().order_by('order_index', 'id'))
    return render(request, 'diako/tutorials.html', {
        'tutorials': tutorials,
        'faqs': faqs,
        'admin_username': request.user.username,
    })


# ─── درخواست‌های افزودن حجم/زمان ─────────────────────────────────────────────

@login_required
def extra_requests_view(request):
    ev_requests = list(ExtraVolumeRequests.objects.all().order_by('-id')[:20])
    et_requests = list(ExtraTimeRequests.objects.all().order_by('-id')[:20])
    ev_plans = list(ExtraVolumePlans.objects.all().order_by('order_index'))
    et_plans = list(ExtraTimePlans.objects.all().order_by('order_index'))
    return render(request, 'diako/extra_requests.html', {
        'ev_requests': ev_requests,
        'et_requests': et_requests,
        'ev_plans': ev_plans,
        'et_plans': et_plans,
        'admin_username': request.user.username,
    })