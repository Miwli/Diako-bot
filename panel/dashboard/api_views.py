import json
import os
import pathlib
import urllib.request
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta
from asgiref.sync import async_to_sync
from shared_lib.db import (
    get_all_keyboard_buttons, get_keyboard_actions, save_keyboard_layout,
    get_servers_as_buttons, save_server_order,
    get_plans_as_buttons, get_services_as_buttons, get_tickets_as_buttons,
    get_tutorials_as_buttons, get_faqs_as_buttons,
    get_admin_plans_as_buttons, get_discount_codes_as_buttons,
)
from .models import Orders


def _get_bot_token():
    token = os.environ.get('BOT_TOKEN', '')
    if not token:
        env_path = pathlib.Path(__file__).parent.parent.parent / 'bot' / '.env'
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith('BOT_TOKEN='):
                    token = line[len('BOT_TOKEN='):].strip()
                    break
        except Exception:
            pass
    return token


@login_required
def pending_orders(request):
    rows = (
        Orders.objects
        .filter(status='pending')
        .select_related('plan')
        .order_by('-id')
        .values('id', 'user_id', 'username', 'plan__name', 'plan__price', 'created_at')
    )
    data = [
        {
            'id': r['id'],
            'telegram_id': r['user_id'],
            'username': r['username'] or '',
            'plan_name': r['plan__name'] or '—',
            'amount': r['plan__price'] or 0,
            'created_at': r['created_at'] or '',
        }
        for r in rows
    ]
    return JsonResponse(data, safe=False)


@login_required
def chart_data(request):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                date(o.created_at, '+210 minutes') AS day,
                COALESCE(SUM(p.price), 0)          AS revenue,
                COUNT(*)                            AS orders
            FROM orders o
            LEFT JOIN plans p ON o.plan_id = p.id
            WHERE o.status = 'approved'
              AND (o.order_type = 'purchase' OR o.order_type IS NULL)
              AND o.created_at >= datetime('now', '-6 days')
            GROUP BY day
            ORDER BY day
        """)
        rows = cursor.fetchall()

    today = datetime.now().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    by_date = {row[0]: (row[1], row[2]) for row in rows}

    return JsonResponse({
        'labels': dates,
        'revenue': [by_date.get(d, (0, 0))[0] for d in dates],
        'orders':  [by_date.get(d, (0, 0))[1] for d in dates],
    })


_DYNAMIC_LOADERS = {
    'buy_vpn':      lambda: async_to_sync(get_servers_as_buttons)(),
    'user_plans':   lambda: async_to_sync(get_plans_as_buttons)(),
    'my_services':  lambda: async_to_sync(get_services_as_buttons)(),
    'my_tickets':   lambda: async_to_sync(get_tickets_as_buttons)(),
    'user_tutorials': lambda: async_to_sync(get_tutorials_as_buttons)(),
    'user_faqs':    lambda: async_to_sync(get_faqs_as_buttons)(),
    'admin_plans':  lambda: async_to_sync(get_admin_plans_as_buttons)(),
    'admin_discount': lambda: async_to_sync(get_discount_codes_as_buttons)(),
}


def keyboard_data(request, keyboard_name):
    if keyboard_name in _DYNAMIC_LOADERS:
        buttons = _DYNAMIC_LOADERS[keyboard_name]()
    elif request.GET.get('all') == '1':
        buttons = async_to_sync(get_all_keyboard_buttons)(keyboard_name)
    else:
        from shared_lib.db import get_keyboard_buttons
        buttons = async_to_sync(get_keyboard_buttons)(keyboard_name)
    return JsonResponse({'buttons': buttons})


@login_required
def bot_info(request):
    token = _get_bot_token()
    if not token:
        return JsonResponse({'ok': False, 'error': 'BOT_TOKEN پیکربندی نشده'})
    try:
        with urllib.request.urlopen(
            f'https://api.telegram.org/bot{token}/getMe', timeout=6
        ) as r:
            me = json.loads(r.read())
        if not me.get('ok'):
            return JsonResponse({'ok': False, 'error': 'خطای Telegram API'})
        bot = me['result']
        avatar_url = None
        try:
            with urllib.request.urlopen(
                f'https://api.telegram.org/bot{token}/getUserProfilePhotos?user_id={bot["id"]}&limit=1',
                timeout=5,
            ) as r:
                photos_resp = json.loads(r.read())
            photos = photos_resp.get('result', {}).get('photos', [])
            if photos:
                file_id = photos[0][-1]['file_id']
                with urllib.request.urlopen(
                    f'https://api.telegram.org/bot{token}/getFile?file_id={file_id}',
                    timeout=5,
                ) as r:
                    file_resp = json.loads(r.read())
                file_path = file_resp.get('result', {}).get('file_path', '')
                if file_path:
                    avatar_url = f'https://api.telegram.org/file/bot{token}/{file_path}'
        except Exception:
            pass
        return JsonResponse({
            'ok': True,
            'name': bot.get('first_name', 'Bot'),
            'username': bot.get('username', ''),
            'avatar_url': avatar_url,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def update_text(request):
    try:
        data = json.loads(request.body)
        key = data.get('key', '').strip()
        value = data.get('value', '')
        if not key:
            return JsonResponse({'ok': False, 'error': 'key الزامی است'})
        from shared_lib.db import set_text
        async_to_sync(set_text)(key, value)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def save_keyboard(request):
    try:
        data = json.loads(request.body)
        buttons = data.get('buttons', [])
        keyboard_name = data.get('keyboard_name', 'user_main')
        static  = [b for b in buttons if not b.get('is_dynamic')]
        dynamic = [b for b in buttons if b.get('is_dynamic')]
        if keyboard_name == 'buy_vpn':
            async_to_sync(save_server_order)(dynamic)
            async_to_sync(save_keyboard_layout)('buy_vpn', static)
        elif keyboard_name in _DYNAMIC_LOADERS:
            # داینامیک‌های دیگه: فقط دکمه‌های ثابت ذخیره می‌شن
            async_to_sync(save_keyboard_layout)(keyboard_name, static)
        else:
            async_to_sync(save_keyboard_layout)(keyboard_name, buttons)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
