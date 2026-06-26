import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from asgiref.sync import async_to_sync
from shared_lib.db import get_admin_stats, get_all_keyboard_buttons, get_keyboard_actions, get_all_texts
from .models import Orders, Servers


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
