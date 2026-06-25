import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from asgiref.sync import async_to_sync
from shared_lib.db import get_admin_stats, get_all_keyboard_buttons, get_keyboard_actions, get_all_texts, get_setting
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


@login_required
def keyboard_editor_view(request):
    buttons = async_to_sync(get_all_keyboard_buttons)("user_main")
    actions = async_to_sync(get_keyboard_actions)()
    all_texts_rows = async_to_sync(get_all_texts)()
    bot_texts = {row['key']: row['value'] for row in all_texts_rows}
    banner_caption = async_to_sync(get_setting)('banner_caption') or ''
    return render(request, 'diako/keyboard_editor.html', {
        'buttons_json': json.dumps(buttons, ensure_ascii=False),
        'actions_json': json.dumps(actions, ensure_ascii=False),
        'bot_texts_json': json.dumps(bot_texts, ensure_ascii=False),
        'banner_caption_json': json.dumps(banner_caption, ensure_ascii=False),
        'admin_username': request.user.username,
    })
