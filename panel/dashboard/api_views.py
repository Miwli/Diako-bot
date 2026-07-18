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
    get_servers_as_buttons, save_server_order, save_faq_order, save_tutorial_order,
    get_plans_as_buttons, get_services_as_buttons, get_tickets_as_buttons,
    get_tutorials_as_buttons, get_faqs_as_buttons,
    get_admin_plans_as_buttons, get_discount_codes_as_buttons,
    get_admin_tutorials_as_buttons, get_admin_faqs_as_buttons, get_admin_users_as_buttons,
)
from shared_lib.db import update_order_status, delete_order
from shared_lib.db import (
    get_admins, get_admin, add_admin, update_admin, set_admin_status, delete_admin,
    get_admin_by_panel_user, get_admin_by_telegram, build_permissions,
    can_manage_admins, log_admin_action, role_default_permissions,
    ADMIN_SECTIONS, ADMIN_ROLES,
)
from shared_lib.db import (
    get_user, ban_user, unban_user, admin_adjust_balance,
    get_transactions, get_free_test_uses,
    get_user_ticket_counts, get_user_order_counts, get_referral_stats,
    get_referral_by_referred, get_user_services, decrement_free_test_uses,
    get_setting, set_setting,
    add_server, delete_server, toggle_server_status, update_server_name,
    update_server_url, update_server_token,
    update_server_services, update_server_free_test, get_servers,
    add_plan, delete_plan, toggle_plan_status, update_plan, get_plan,
    create_discount_code, toggle_discount_code, delete_discount_code,
    create_tutorial, update_tutorial, toggle_tutorial, delete_tutorial, move_tutorial,
    create_faq, update_faq, toggle_faq, delete_faq, move_faq,
    get_extra_time_request, update_extra_time_request,
    get_extra_volume_request, update_extra_volume_request,
    approve_top_up_atomic, update_top_up_status,
)
from shared_lib.db import (
    BACKUP_MANIFEST, SENSITIVE_SUBITEMS, backup_manifest_counts,
    export_backup, import_backup, create_db_snapshot, replace_database, DB_PATH,
)
from .models import Orders, Servers, Plans, DiscountCodes, TopUpRequests, Users


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


def _send_telegram(chat_id: int, text: str, parse_mode: str = 'HTML'):
    token = _get_bot_token()
    if not token:
        return False, 'BOT_TOKEN یافت نشد — پیام تلگرام ارسال نشد'
    payload = json.dumps({
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
    }).encode('utf-8')
    try:
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{token}/sendMessage',
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if not data.get('ok'):
            return False, data.get('description', 'خطای تلگرام')
        return True, None
    except Exception as e:
        return False, str(e)


def _format_date(dt_str):
    if not dt_str:
        return '—'
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y/%m/%d %H:%M')
    except Exception:
        return dt_str[:16] if len(dt_str) >= 16 else dt_str


def _user_detail_payload(user_id: int):
    user = async_to_sync(get_user)(user_id)
    if not user:
        return None
    user = dict(user)

    uid = user['user_id']
    order_counts = async_to_sync(get_user_order_counts)(uid)
    tickets_open, tickets_closed = async_to_sync(get_user_ticket_counts)(uid)
    free_uses = async_to_sync(get_free_test_uses)(uid)
    ref_stats = async_to_sync(get_referral_stats)(uid)
    referral = async_to_sync(get_referral_by_referred)(uid)
    tx_count = len(async_to_sync(get_transactions)(uid, limit=100))
    services_raw = async_to_sync(get_user_services)(uid)

    referrer = None
    if referral:
        ref_user = async_to_sync(get_user)(referral['referrer_id'])
        if ref_user:
            referrer = {
                'user_id': ref_user['user_id'],
                'first_name': ref_user.get('first_name') or '',
                'username': ref_user.get('username') or '',
            }

    services = []
    for s in services_raw:
        d = dict(s)
        services.append({
            'id': d['id'],
            'plan_name': d.get('plan_name') or '—',
            'vpn_username': d.get('vpn_username') or '—',
            'status': d.get('status') or '',
            'created_at': _format_date(d.get('created_at')),
        })

    return {
        'user_id': uid,
        'first_name': user.get('first_name') or '',
        'username': user.get('username') or '',
        'balance': user.get('balance') or 0,
        'created_at': _format_date(user.get('created_at')),
        'is_banned': bool(user.get('is_banned')),
        'referral_code': user.get('referral_code') or '',
        'free_test_uses': free_uses,
        'orders': {
            'approved': order_counts.get('approved', 0),
            'pending': order_counts.get('pending', 0),
            'rejected': order_counts.get('rejected', 0),
        },
        'tickets': {'open': tickets_open, 'closed': tickets_closed},
        'tx_count': tx_count,
        'referrer': referrer,
        'referral_stats': {
            'count': ref_stats.get('count', 0),
            'total': ref_stats.get('total', 0),
        },
        'services': services,
    }


@login_required
def user_detail(request, user_id):
    payload = _user_detail_payload(user_id)
    if not payload:
        return JsonResponse({'ok': False, 'error': 'کاربر یافت نشد'}, status=404)
    return JsonResponse({'ok': True, 'user': payload})


@login_required
@require_http_methods(["POST"])
def user_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    user_id = data.get('user_id')
    action = data.get('action')

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'user_id نامعتبر'}, status=400)

    user = async_to_sync(get_user)(user_id)
    if not user:
        return JsonResponse({'ok': False, 'error': 'کاربر یافت نشد'}, status=404)

    if action == 'ban':
        async_to_sync(ban_user)(user_id)
        reason = (data.get('reason') or '').strip()
        msg = '⛔️ دسترسی شما به ربات محدود شده است.'
        if reason:
            msg += f'\n\n{reason}'
        _send_telegram(user_id, msg)
        return JsonResponse({'ok': True, 'user': _user_detail_payload(user_id)})

    if action == 'unban':
        async_to_sync(unban_user)(user_id)
        _send_telegram(user_id, '✅ دسترسی شما به ربات بازگردانده شد.')
        return JsonResponse({'ok': True, 'user': _user_detail_payload(user_id)})

    if action in ('add_balance', 'deduct_balance'):
        raw = str(data.get('amount', '')).strip().replace(',', '')
        if not raw.isdigit() or int(raw) <= 0:
            return JsonResponse({'ok': False, 'error': 'مبلغ نامعتبر است'})
        amount = int(raw)
        if action == 'add_balance':
            async_to_sync(admin_adjust_balance)(user_id, amount, 'افزودن دستی از پنل وب')
        else:
            async_to_sync(admin_adjust_balance)(user_id, -amount, 'کسر دستی از پنل وب')
        return JsonResponse({'ok': True, 'user': _user_detail_payload(user_id)})

    if action == 'send_message':
        text = (data.get('message') or '').strip()
        if not text:
            return JsonResponse({'ok': False, 'error': 'پیام خالی است'})
        ok, err = _send_telegram(user_id, f'📨 <b>پیام از پشتیبانی:</b>\n\n{text}')
        if not ok:
            return JsonResponse({'ok': False, 'error': err or 'ارسال ناموفق'})
        return JsonResponse({'ok': True})

    if action == 'grant_free_test':
        async_to_sync(decrement_free_test_uses)(user_id)
        return JsonResponse({'ok': True, 'user': _user_detail_payload(user_id)})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


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
    'buy_vpn':          lambda: async_to_sync(get_servers_as_buttons)(),
    'user_plans':       lambda: async_to_sync(get_plans_as_buttons)(),
    'my_services':      lambda: async_to_sync(get_services_as_buttons)(),
    'my_tickets':       lambda: async_to_sync(get_tickets_as_buttons)(),
    'user_tutorials':   lambda: async_to_sync(get_tutorials_as_buttons)(),
    'user_faqs':        lambda: async_to_sync(get_faqs_as_buttons)(),
    'admin_plans':      lambda: async_to_sync(get_admin_plans_as_buttons)(),
    'admin_discount':   lambda: async_to_sync(get_discount_codes_as_buttons)(),
    'admin_tutorial_list': lambda: async_to_sync(get_admin_tutorials_as_buttons)(),
    'admin_faqs':       lambda: async_to_sync(get_admin_faqs_as_buttons)(),
    'admin_user_list':  lambda: async_to_sync(get_admin_users_as_buttons)(),
}

# کیبوردهایی که ترتیب داینامیک‌شان روی جدول خودشان ذخیره می‌شود
_DYNAMIC_ORDER_SAVERS = {
    'user_faqs':       save_faq_order,
    'user_tutorials':  save_tutorial_order,
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
            saver = _DYNAMIC_ORDER_SAVERS.get(keyboard_name)
            if saver:
                async_to_sync(saver)(dynamic)
            async_to_sync(save_keyboard_layout)(keyboard_name, static)
        else:
            async_to_sync(save_keyboard_layout)(keyboard_name, buttons)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@require_http_methods(["POST"])
@login_required
def order_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    order_id = data.get('order_id')
    action   = data.get('action')
    reason   = data.get('reason', '').strip() or None

    if not order_id or action not in ('reject', 'delete'):
        return JsonResponse({'ok': False, 'error': 'پارامتر نامعتبر'}, status=400)

    try:
        order = Orders.objects.get(id=order_id)
    except Orders.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'سفارش یافت نشد'}, status=404)

    if action == 'delete':
        async_to_sync(delete_order)(order_id)
        return JsonResponse({'ok': True})

    if order.status != 'pending':
        return JsonResponse({'ok': False, 'error': 'سفارش قابل تغییر نیست'})

    async_to_sync(update_order_status)(order_id, 'rejected', reason)
    return JsonResponse({'ok': True})


@login_required
@require_http_methods(["POST"])
def import_config(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'ok': False, 'error': 'فرمت فایل نامعتبر است'}, status=400)

    from shared_lib.db import import_texts, import_keyboards, save_keyboard_actions
    result = {}
    try:
        if 'bot_texts' in data:
            if not isinstance(data['bot_texts'], dict):
                return JsonResponse({'ok': False, 'error': 'bot_texts باید یک آبجکت باشد'}, status=400)
            result['texts'] = async_to_sync(import_texts)(data['bot_texts'])
        if 'keyboards' in data:
            if not isinstance(data['keyboards'], dict):
                return JsonResponse({'ok': False, 'error': 'keyboards باید یک آبجکت باشد'}, status=400)
            result['keyboards'] = async_to_sync(import_keyboards)(data['keyboards'])
        if 'keyboard_actions' in data:
            if not isinstance(data['keyboard_actions'], list):
                return JsonResponse({'ok': False, 'error': 'keyboard_actions باید یک لیست باشد'}, status=400)
            result['actions'] = async_to_sync(save_keyboard_actions)(data['keyboard_actions'])
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'خطا در اعمال: {e}'}, status=400)

    return JsonResponse({'ok': True, 'result': result})


# ═══════════════════════════════════════════════════════════════════════════
#  API — بکاپ و بازگردانی (دیتابیس)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def backup_manifest(request):
    """ساختار دسته‌ها + تعداد رکورد هر زیرشاخه — برای ساخت لیست انتخاب"""
    structure = {cat: [sid for sid, _, _ in items] for cat, items in BACKUP_MANIFEST.items()}
    counts = async_to_sync(backup_manifest_counts)()
    return JsonResponse({
        'ok': True,
        'manifest': structure,
        'counts': counts,
        'sensitive': sorted(SENSITIVE_SUBITEMS),
    })


@login_required
@require_http_methods(["POST"])
def export_data(request):
    """خروجی JSON از زیرشاخه‌های انتخاب‌شده"""
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)
    subitems = body.get('subitems') or []
    include_sensitive = bool(body.get('include_sensitive'))
    if not isinstance(subitems, list) or not subitems:
        return JsonResponse({'ok': False, 'error': 'هیچ موردی انتخاب نشده'}, status=400)
    data = async_to_sync(export_backup)(subitems, include_sensitive)
    return JsonResponse({'ok': True, 'data': data})


@login_required
@require_http_methods(["GET"])
def export_full_db(request):
    """دانلود کل دیتابیس به‌صورت فایل خام (اسنپ‌شات سازگار)"""
    import tempfile
    from django.http import HttpResponse
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    try:
        create_db_snapshot(tmp)
        with open(tmp, 'rb') as f:
            blob = f.read()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    resp = HttpResponse(blob, content_type='application/octet-stream')
    resp['Content-Disposition'] = f'attachment; filename="diako-full-{stamp}.db"'
    return resp


@login_required
@require_http_methods(["POST"])
def import_data(request):
    """اعمال یک فایل JSON روی زیرشاخه‌های انتخاب‌شده با حالت مشخص"""
    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)
    file_data = body.get('file_data')
    subitems = body.get('subitems') or []
    mode = body.get('mode') or 'upsert'
    if not isinstance(file_data, dict):
        return JsonResponse({'ok': False, 'error': 'محتوای فایل نامعتبر است'}, status=400)
    if mode not in ('upsert', 'replace', 'addnew'):
        return JsonResponse({'ok': False, 'error': 'حالت اعمال نامعتبر'}, status=400)
    if not isinstance(subitems, list) or not subitems:
        return JsonResponse({'ok': False, 'error': 'هیچ موردی انتخاب نشده'}, status=400)
    try:
        result = async_to_sync(import_backup)(file_data, subitems, mode)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'خطا در اعمال: {e}'}, status=400)
    return JsonResponse({'ok': True, 'result': result})


@login_required
@require_http_methods(["POST"])
def import_full_db(request):
    """جایگزینی کل دیتابیس با فایل .db آپلودشده (با بکاپ خودکار اختیاری قبلش)"""
    up = request.FILES.get('file')
    if not up:
        return JsonResponse({'ok': False, 'error': 'فایلی آپلود نشده'}, status=400)
    backup_first = request.POST.get('backup_first') == '1'
    dbdir = os.path.dirname(DB_PATH)
    tmp = os.path.join(dbdir, '.restore-upload.db')
    with open(tmp, 'wb') as out:
        for chunk in up.chunks():
            out.write(chunk)
    try:
        backup_path = replace_database(tmp, backup_first=backup_first)
    except ValueError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
    except Exception as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return JsonResponse({'ok': False, 'error': f'خطا در بازگردانی: {e}'}, status=400)
    return JsonResponse({
        'ok': True,
        'backup': os.path.basename(backup_path) if backup_path else None,
    })


@login_required
@require_http_methods(["POST"])
def service_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')
    order_id = data.get('order_id')
    if not order_id:
        return JsonResponse({'ok': False, 'error': 'order_id الزامی است'}, status=400)

    from shared_lib.db import get_service_by_order, set_service_note
    order = async_to_sync(get_service_by_order)(int(order_id))
    if not order:
        return JsonResponse({'ok': False, 'error': 'سرویس یافت نشد'}, status=404)

    if action == 'changestatus':
        from shared_lib.rebecca_api import RebeccaAPI
        api = RebeccaAPI(order['panel_url'], order['panel_token'])
        try:
            live = async_to_sync(api.get_user)(order['vpn_username'])
            target_active = live.get('status') != 'active'
            async_to_sync(api.toggle_status)(order['vpn_username'], target_active)
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'خطای API: {e}'})
        return JsonResponse({'ok': True, 'active': target_active})

    if action == 'set_note':
        note = (data.get('note') or '').strip()
        if len(note) > 500:
            return JsonResponse({'ok': False, 'error': 'یادداشت حداکثر ۵۰۰ نویسه می‌تواند باشد'})
        async_to_sync(set_service_note)(int(order_id), note)
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'اکشن نامعتبر'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  API — مانیتورینگ نودها
# ═══════════════════════════════════════════════════════════════════════════

async def _geo_lookup(host: str) -> dict:
    """موقعیت جغرافیایی یک هاست — با کش در DB تا هر بار سراغ ip-api نریم"""
    import asyncio
    import aiohttp
    from shared_lib.db import get_geo_cache, set_geo_cache

    if not host:
        return {}
    cached = await get_geo_cache(host)
    if cached and cached['lat'] is not None:
        return dict(cached)
    try:
        loop = asyncio.get_event_loop()
        infos = await loop.getaddrinfo(host, None)
        ip = infos[0][4][0]
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country',
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                geo = await resp.json()
        if geo.get('status') == 'success':
            await set_geo_cache(host, ip, geo['lat'], geo['lon'],
                                geo.get('city', ''), geo.get('country', ''))
            return {'ip': ip, 'lat': geo['lat'], 'lon': geo['lon'],
                    'city': geo.get('city', ''), 'country': geo.get('country', '')}
    except Exception:
        pass
    return {}


# وضعیت نود در Rebecca → وضعیتی که کره نشون می‌ده
_NODE_STATUS_MAP = {
    'connected':  'online',
    'connecting': 'connecting',
    'error':      'error',
    'disabled':   'disabled',
}


async def _check_all_servers(servers: list) -> list:
    """چک موازی همه‌ی سرورها: تاخیر، آمار سیستم و نودهای داخل هر پنل"""
    import asyncio
    import aiohttp
    import math
    import time
    from urllib.parse import urlparse
    from shared_lib.rebecca_api import RebeccaAPI

    async def check(s: dict) -> dict:
        host = urlparse(s['panel_url']).hostname or ''
        info = {
            'id':        s['id'],
            'name':      s['name'],
            'host':      host,
            'is_active': s.get('is_active', 1),
            'status':    'offline',
            'latency':   None,
            'lat': None, 'lon': None, 'city': '', 'country': '',
            'stats':     None,
            'nodes':     [],
            'nodes_error': None,
        }

        geo = await _geo_lookup(host)
        if geo:
            info.update(lat=geo['lat'], lon=geo['lon'],
                        city=geo.get('city', ''), country=geo.get('country', ''))

        api = RebeccaAPI(s['panel_url'], s['panel_token'])

        try:
            start = time.monotonic()
            stats = await api.get_system_stats()
            info['latency'] = int((time.monotonic() - start) * 1000)
            info['status'] = 'online'
            info['stats'] = {
                'version':            stats.get('version'),
                'users_active':       stats.get('users_active'),
                'users_total':        stats.get('total_user'),
                'cpu_usage':          stats.get('cpu_usage'),
                'cpu_cores':          stats.get('cpu_cores'),
                'mem_used':           (stats.get('memory') or {}).get('current'),
                'mem_total':          (stats.get('memory') or {}).get('total'),
                'incoming_bandwidth': stats.get('incoming_bandwidth'),
                'outgoing_bandwidth': stats.get('outgoing_bandwidth'),
            }
        except Exception:
            # شاید پنل /api/system نداشته باشه — با /api/admin چک می‌کنیم
            import aiohttp
            try:
                headers = {'Authorization': f"Bearer {s['panel_token']}"}
                start = time.monotonic()
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(
                        s['panel_url'].rstrip('/') + '/api/admin',
                        ssl=False,
                        timeout=aiohttp.ClientTimeout(total=6)
                    ) as resp:
                        await resp.read()
                        info['latency'] = int((time.monotonic() - start) * 1000)
                        info['status'] = 'online' if resp.status == 200 else 'error'
            except Exception:
                pass
            if info['status'] != 'online':
                return info

        try:
            raw_nodes = await api.get_nodes()
        except aiohttp.ClientResponseError as e:
            raw_nodes = []
            if e.status == 403:
                info['nodes_error'] = 'ادمین این سرور در پنل ربکا دسترسی مشاهده‌ی نودها را ندارد'
            else:
                info['nodes_error'] = f'دریافت نودها ناموفق بود (HTTP {e.status})'
        except Exception:
            raw_nodes = []
            info['nodes_error'] = 'دریافت نودها ناموفق بود'

        async def node_info(n: dict, idx: int) -> dict:
            raw_status = n.get('status', '')
            node = {
                'id':           n.get('id'),
                'name':         n.get('name', ''),
                'address':      n.get('address', ''),
                'status':       _NODE_STATUS_MAP.get(raw_status, 'error'),
                'raw_status':   raw_status,
                'xray_version': n.get('xray_version'),
                'message':      n.get('message'),
                'uplink':       n.get('uplink'),
                'downlink':     n.get('downlink'),
                'lat': None, 'lon': None, 'city': '', 'country': '', 'geo_is_fallback': False,
            }
            g = await _geo_lookup(n.get('address', ''))
            if g:
                node.update(lat=g['lat'], lon=g['lon'],
                            city=g.get('city', ''), country=g.get('country', ''))
            elif info['lat'] is not None:
                # نتونستیم آدرس نود رو geolocate کنیم — دورتادور سرور والدش پخششون می‌کنیم که روی هم نیفتن
                angle = idx * 137.5 * math.pi / 180  # زاویه‌ی طلایی — پخش یکنواخت
                node.update(
                    lat=info['lat'] + 1.1 * math.cos(angle),
                    lon=info['lon'] + 1.1 * math.sin(angle),
                    geo_is_fallback=True,
                )
            return node

        info['nodes'] = list(await asyncio.gather(*[node_info(dict(n), i) for i, n in enumerate(raw_nodes)]))
        return info

    return list(await asyncio.gather(*[check(dict(s)) for s in servers]))


@login_required
def nodes_status(request):
    from shared_lib.db import get_servers
    servers = async_to_sync(get_servers)(False)
    result = async_to_sync(_check_all_servers)([dict(s) for s in servers])
    return JsonResponse({'servers': result})


# ═══════════════════════════════════════════════════════════════════════════
#  API — مدیریت سرورها
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def server_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')

    if action == 'fetch_services':
        url = (data.get('url') or '').strip()
        token = (data.get('token') or '').strip()
        if not url or not token:
            return JsonResponse({'ok': False, 'error': 'آدرس و توکن الزامی است'})
        if not url.startswith('https://') or url.endswith('/'):
            return JsonResponse({'ok': False, 'error': 'آدرس باید با https:// شروع و بدون / در انتها باشد'})
        from shared_lib.rebecca_api import RebeccaAPI
        api = RebeccaAPI(url, token)
        try:
            services = async_to_sync(api.get_services)()
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'اتصال به پنل ناموفق بود: {e}'})
        return JsonResponse({'ok': True, 'services': [
            {'id': s.get('id'), 'name': s.get('name', f"سرویس {s.get('id')}")} for s in services
        ]})

    if action == 'add':
        name = (data.get('name') or '').strip()
        url = (data.get('url') or '').strip()
        token = (data.get('token') or '').strip()
        service_ids = data.get('service_ids') or []
        if not name or not url or not token:
            return JsonResponse({'ok': False, 'error': 'نام، آدرس و توکن الزامی است'})
        if not url.startswith('https://') or url.endswith('/'):
            return JsonResponse({'ok': False, 'error': 'آدرس باید با https:// شروع و بدون / در انتها باشد'})
        if not service_ids:
            return JsonResponse({'ok': False, 'error': 'حداقل یک سرویس را انتخاب کنید'})
        async_to_sync(add_server)(name, url, token, [int(i) for i in service_ids])
        return JsonResponse({'ok': True})

    if action == 'delete':
        server_id = data.get('server_id')
        if not server_id:
            return JsonResponse({'ok': False, 'error': 'server_id الزامی است'}, status=400)
        async_to_sync(delete_server)(int(server_id))
        return JsonResponse({'ok': True})

    if action == 'toggle':
        server_id = data.get('server_id')
        if not server_id:
            return JsonResponse({'ok': False, 'error': 'server_id الزامی است'}, status=400)
        async_to_sync(toggle_server_status)(int(server_id))
        return JsonResponse({'ok': True})

    if action == 'update_name':
        server_id = data.get('server_id')
        name = (data.get('name') or '').strip()
        if not server_id or not name:
            return JsonResponse({'ok': False, 'error': 'server_id و نام الزامی است'})
        try:
            async_to_sync(update_server_name)(int(server_id), name)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'این نام قبلاً استفاده شده است'})
        return JsonResponse({'ok': True})

    if action == 'update_url':
        server_id = data.get('server_id')
        url = (data.get('url') or '').strip()
        if not server_id or not url:
            return JsonResponse({'ok': False, 'error': 'server_id و url الزامی است'})
        if not url.startswith('https://') or url.endswith('/'):
            return JsonResponse({'ok': False, 'error': 'آدرس نامعتبر'})
        async_to_sync(update_server_url)(int(server_id), url)
        return JsonResponse({'ok': True})

    if action == 'update_token':
        server_id = data.get('server_id')
        token = (data.get('token') or '').strip()
        if not server_id or not token:
            return JsonResponse({'ok': False, 'error': 'server_id و token الزامی است'})
        async_to_sync(update_server_token)(int(server_id), token)
        return JsonResponse({'ok': True})

    if action == 'update_services':
        server_id = data.get('server_id')
        service_ids = data.get('service_ids') or []
        if not server_id:
            return JsonResponse({'ok': False, 'error': 'server_id الزامی است'}, status=400)
        if not service_ids:
            return JsonResponse({'ok': False, 'error': 'حداقل یک سرویس را انتخاب کنید'})
        async_to_sync(update_server_services)(int(server_id), [int(i) for i in service_ids])
        return JsonResponse({'ok': True})

    if action == 'update_free_test':
        server_id = data.get('server_id')
        if not server_id:
            return JsonResponse({'ok': False, 'error': 'server_id الزامی است'}, status=400)
        enabled = data.get('enabled')
        duration = data.get('duration')
        traffic = data.get('traffic')
        kwargs = {}
        if enabled is not None:
            kwargs['enabled'] = int(enabled)
        if duration is not None:
            kwargs['duration'] = float(duration)
        if traffic is not None:
            kwargs['traffic'] = float(traffic)
        async_to_sync(update_server_free_test)(int(server_id), **kwargs)
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  API — مدیریت پلن‌ها
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def plan_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')

    if action == 'add':
        server_id = data.get('server_id')
        name = (data.get('name') or '').strip()
        price = data.get('price')
        duration = data.get('duration')
        traffic = data.get('traffic')
        if not name or price is None or duration is None or traffic is None:
            return JsonResponse({'ok': False, 'error': 'همه فیلدها الزامی است'})
        try:
            price = int(price)
            duration = int(duration)
            traffic = int(traffic)
            ip_limit = int(data.get('ip_limit') or 0)
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'قیمت، مدت، حجم و تعداد کاربر باید عدد باشند'})
        async_to_sync(add_plan)(int(server_id) if server_id else None, name, price, duration, traffic,
                                ip_limit=ip_limit)
        return JsonResponse({'ok': True})

    if action == 'delete':
        plan_id = data.get('plan_id')
        if not plan_id:
            return JsonResponse({'ok': False, 'error': 'plan_id الزامی است'}, status=400)
        async_to_sync(delete_plan)(int(plan_id))
        return JsonResponse({'ok': True})

    if action == 'toggle':
        plan_id = data.get('plan_id')
        if not plan_id:
            return JsonResponse({'ok': False, 'error': 'plan_id الزامی است'}, status=400)
        async_to_sync(toggle_plan_status)(int(plan_id))
        return JsonResponse({'ok': True})

    if action == 'update':
        plan_id = data.get('plan_id')
        name = (data.get('name') or '').strip()
        price = data.get('price')
        duration = data.get('duration')
        traffic = data.get('traffic')
        if not plan_id or not name or price is None or duration is None or traffic is None:
            return JsonResponse({'ok': False, 'error': 'همه فیلدها الزامی است'})
        try:
            price = int(price)
            duration = int(duration)
            traffic = int(traffic)
            ip_limit = int(data.get('ip_limit') or 0)
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'قیمت، مدت، حجم و تعداد کاربر باید عدد باشند'})
        async_to_sync(update_plan)(int(plan_id), name, price, duration, traffic, ip_limit=ip_limit)
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  API — مدیریت مالی
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def finance_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')

    if action == 'toggle_card_active':
        card_active = async_to_sync(get_setting)('card_active')
        async_to_sync(set_setting)('card_active', '0' if card_active == '1' else '1')
        return JsonResponse({'ok': True})

    if action == 'set_card_mode':
        mode = data.get('mode')
        if mode not in ('round_robin', 'random', 'fixed'):
            return JsonResponse({'ok': False, 'error': 'حالت نامعتبر است'})
        async_to_sync(set_setting)('card_select_mode', mode)
        return JsonResponse({'ok': True})

    if action == 'set_fixed_card':
        card_id = data.get('card_id')
        if not card_id:
            return JsonResponse({'ok': False, 'error': 'card_id الزامی است'}, status=400)
        async_to_sync(set_setting)('card_fixed_id', str(card_id))
        return JsonResponse({'ok': True})

    if action == 'add_card':
        from shared_lib.db import add_payment_card
        number = (data.get('number') or '').strip().replace(' ', '')
        owner = (data.get('owner') or '').strip()
        if not number:
            return JsonResponse({'ok': False, 'error': 'شماره کارت الزامی است'})
        if len(number) != 16 or not number.isdigit():
            return JsonResponse({'ok': False, 'error': 'شماره کارت باید ۱۶ رقم باشد'})
        async_to_sync(add_payment_card)(number, owner or None)
        return JsonResponse({'ok': True})

    if action == 'update_card':
        from shared_lib.db import update_payment_card
        card_id = data.get('card_id')
        if not card_id:
            return JsonResponse({'ok': False, 'error': 'card_id الزامی است'}, status=400)
        number = (data.get('number') or '').strip().replace(' ', '')
        owner = (data.get('owner') or '').strip()
        if not number:
            return JsonResponse({'ok': False, 'error': 'شماره کارت الزامی است'})
        if len(number) != 16 or not number.isdigit():
            return JsonResponse({'ok': False, 'error': 'شماره کارت باید ۱۶ رقم باشد'})
        async_to_sync(update_payment_card)(int(card_id), number=number, owner=owner)
        return JsonResponse({'ok': True})

    if action == 'toggle_card_item':
        from shared_lib.db import toggle_payment_card
        card_id = data.get('card_id')
        if not card_id:
            return JsonResponse({'ok': False, 'error': 'card_id الزامی است'}, status=400)
        async_to_sync(toggle_payment_card)(int(card_id))
        return JsonResponse({'ok': True})

    if action == 'delete_card':
        from shared_lib.db import delete_payment_card
        card_id = data.get('card_id')
        if not card_id:
            return JsonResponse({'ok': False, 'error': 'card_id الزامی است'}, status=400)
        async_to_sync(delete_payment_card)(int(card_id))
        return JsonResponse({'ok': True})

    if action == 'approve_topup':
        topup_id = data.get('topup_id')
        if not topup_id:
            return JsonResponse({'ok': False, 'error': 'topup_id الزامی است'}, status=400)
        ok = async_to_sync(approve_top_up_atomic)(int(topup_id))
        if not ok:
            return JsonResponse({'ok': False, 'error': 'این درخواست قبلاً پردازش شده'})
        from shared_lib.db import get_top_up_request, add_balance_and_transaction
        req = async_to_sync(get_top_up_request)(int(topup_id))
        if req:
            async_to_sync(add_balance_and_transaction)(
                req['user_id'], req['amount'], 'topup', f'شارژ حساب — تایید از پنل وب #{topup_id}'
            )
            _send_telegram(req['user_id'], f'✅ <b>شارژ حساب تایید شد!</b>\n\n💰 مبلغ <b>{req["amount"]:,}</b> تومان به کیف پول شما اضافه شد.')
        return JsonResponse({'ok': True})

    if action == 'reject_topup':
        topup_id = data.get('topup_id')
        if not topup_id:
            return JsonResponse({'ok': False, 'error': 'topup_id الزامی است'}, status=400)
        async_to_sync(update_top_up_status)(int(topup_id), 'rejected')
        from shared_lib.db import get_top_up_request
        req = async_to_sync(get_top_up_request)(int(topup_id))
        if req:
            _send_telegram(req['user_id'], '❌ متأسفانه درخواست شارژ حساب شما تایید نشد.')
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  API — مدیریت کدهای تخفیف
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def discount_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')

    if action == 'add':
        code = (data.get('code') or '').strip().upper()
        type_ = data.get('type', 'percent')
        value = data.get('value')
        max_uses = data.get('max_uses', 0)
        expires_at = (data.get('expires_at') or '').strip() or None
        if not code or value is None:
            return JsonResponse({'ok': False, 'error': 'کد و مقدار الزامی است'})
        if not (2 <= len(code) <= 20) or not code.isalnum():
            return JsonResponse({'ok': False, 'error': 'کد باید ۲ تا ۲۰ کاراکتر انگلیسی یا عدد باشد'})
        try:
            value = int(value)
            max_uses = int(max_uses)
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'مقدار و محدودیت باید عدد باشند'})
        if type_ == 'percent' and not (1 <= value <= 100):
            return JsonResponse({'ok': False, 'error': 'درصد باید بین ۱ تا ۱۰۰ باشد'})
        async_to_sync(create_discount_code)(code, type_, value, max_uses, expires_at)
        return JsonResponse({'ok': True})

    if action == 'toggle':
        code_id = data.get('code_id')
        if not code_id:
            return JsonResponse({'ok': False, 'error': 'code_id الزامی است'}, status=400)
        async_to_sync(toggle_discount_code)(int(code_id))
        return JsonResponse({'ok': True})

    if action == 'delete':
        code_id = data.get('code_id')
        if not code_id:
            return JsonResponse({'ok': False, 'error': 'code_id الزامی است'}, status=400)
        async_to_sync(delete_discount_code)(int(code_id))
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  API — مدیریت آموزش‌ها و سوالات متداول
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def tutorial_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')

    if action == 'add_tutorial':
        title = (data.get('title') or '').strip()
        caption = (data.get('caption') or '').strip()
        if not title:
            return JsonResponse({'ok': False, 'error': 'عنوان الزامی است'})
        async_to_sync(create_tutorial)(title, 'text', None, caption or None)
        return JsonResponse({'ok': True})

    if action == 'update_tutorial':
        tid = data.get('id')
        title = (data.get('title') or '').strip()
        caption = (data.get('caption') or '').strip()
        if not tid or not title:
            return JsonResponse({'ok': False, 'error': 'id و عنوان الزامی است'})
        async_to_sync(update_tutorial)(int(tid), title, 'text', None, caption or None)
        return JsonResponse({'ok': True})

    if action == 'toggle_tutorial':
        tid = data.get('id')
        if not tid:
            return JsonResponse({'ok': False, 'error': 'id الزامی است'}, status=400)
        async_to_sync(toggle_tutorial)(int(tid))
        return JsonResponse({'ok': True})

    if action == 'delete_tutorial':
        tid = data.get('id')
        if not tid:
            return JsonResponse({'ok': False, 'error': 'id الزامی است'}, status=400)
        async_to_sync(delete_tutorial)(int(tid))
        return JsonResponse({'ok': True})

    if action == 'move_tutorial':
        tid = data.get('id')
        direction = data.get('direction')
        if not tid or direction not in ('up', 'down'):
            return JsonResponse({'ok': False, 'error': 'id و direction الزامی است'})
        async_to_sync(move_tutorial)(int(tid), direction)
        return JsonResponse({'ok': True})

    if action == 'add_faq':
        question = (data.get('question') or '').strip()
        answer = (data.get('answer') or '').strip()
        if not question or not answer:
            return JsonResponse({'ok': False, 'error': 'سوال و جواب الزامی است'})
        async_to_sync(create_faq)(question, answer)
        return JsonResponse({'ok': True})

    if action == 'update_faq':
        fid = data.get('id')
        question = (data.get('question') or '').strip()
        answer = (data.get('answer') or '').strip()
        if not fid or not question or not answer:
            return JsonResponse({'ok': False, 'error': 'id، سوال و جواب الزامی است'})
        async_to_sync(update_faq)(int(fid), question, answer)
        return JsonResponse({'ok': True})

    if action == 'toggle_faq':
        fid = data.get('id')
        if not fid:
            return JsonResponse({'ok': False, 'error': 'id الزامی است'}, status=400)
        async_to_sync(toggle_faq)(int(fid))
        return JsonResponse({'ok': True})

    if action == 'delete_faq':
        fid = data.get('id')
        if not fid:
            return JsonResponse({'ok': False, 'error': 'id الزامی است'}, status=400)
        async_to_sync(delete_faq)(int(fid))
        return JsonResponse({'ok': True})

    if action == 'move_faq':
        fid = data.get('id')
        direction = data.get('direction')
        if not fid or direction not in ('up', 'down'):
            return JsonResponse({'ok': False, 'error': 'id و direction الزامی است'})
        async_to_sync(move_faq)(int(fid), direction)
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  API — مدیریت درخواست‌های افزودن حجم/زمان
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def extra_request_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')
    req_id = data.get('req_id')

    if action == 'approve_ev':
        if not req_id:
            return JsonResponse({'ok': False, 'error': 'req_id الزامی است'}, status=400)
        req = async_to_sync(get_extra_volume_request)(int(req_id))
        if not req:
            return JsonResponse({'ok': False, 'error': 'درخواست یافت نشد'}, status=404)
        if req['status'] == 'approved':
            return JsonResponse({'ok': False, 'error': 'قبلاً تایید شده'})
        from shared_lib.db import get_plan_with_server
        plan_data = async_to_sync(get_plan_with_server)(req['vpn_plan_id'])
        if not plan_data:
            return JsonResponse({'ok': False, 'error': 'سرور VPN مرتبط یافت نشد'})
        from shared_lib.rebecca_api import RebeccaAPI
        api = RebeccaAPI(plan_data['panel_url'], plan_data['panel_token'])
        try:
            async_to_sync(api.add_volume)(req['vpn_username'], req['traffic_gb'])
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'خطای API: {e}'})
        async_to_sync(update_extra_volume_request)(int(req_id), 'approved')
        from shared_lib.db import get_text
        from shared_lib.formatters import fmt_traffic_gb
        _send_telegram(req['user_id'], get_text('extra_volume_approved', traffic=fmt_traffic_gb(req['traffic_gb'])))
        return JsonResponse({'ok': True})

    if action == 'reject_ev':
        if not req_id:
            return JsonResponse({'ok': False, 'error': 'req_id الزامی است'}, status=400)
        async_to_sync(update_extra_volume_request)(int(req_id), 'rejected')
        req = async_to_sync(get_extra_volume_request)(int(req_id))
        if req:
            _send_telegram(req['user_id'], '❌ درخواست افزودن حجم رد شد.')
        return JsonResponse({'ok': True})

    if action == 'approve_et':
        if not req_id:
            return JsonResponse({'ok': False, 'error': 'req_id الزامی است'}, status=400)
        req = async_to_sync(get_extra_time_request)(int(req_id))
        if not req:
            return JsonResponse({'ok': False, 'error': 'درخواست یافت نشد'}, status=404)
        if req['status'] == 'approved':
            return JsonResponse({'ok': False, 'error': 'قبلاً تایید شده'})
        from shared_lib.db import get_plan_with_server
        plan_data = async_to_sync(get_plan_with_server)(req['vpn_plan_id'])
        if not plan_data:
            return JsonResponse({'ok': False, 'error': 'سرور VPN مرتبط یافت نشد'})
        from shared_lib.rebecca_api import RebeccaAPI
        api = RebeccaAPI(plan_data['panel_url'], plan_data['panel_token'])
        try:
            async_to_sync(api.add_time)(req['vpn_username'], req['days'])
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'خطای API: {e}'})
        async_to_sync(update_extra_time_request)(int(req_id), 'approved')
        _send_telegram(req['user_id'], f'✅ <b>افزودن زمان تایید شد!</b>\n\n📅 <b>{req["days"]} روز</b> به سرویس شما اضافه شد.')
        return JsonResponse({'ok': True})

    if action == 'reject_et':
        if not req_id:
            return JsonResponse({'ok': False, 'error': 'req_id الزامی است'}, status=400)
        async_to_sync(update_extra_time_request)(int(req_id), 'rejected')
        req = async_to_sync(get_extra_time_request)(int(req_id))
        if req:
            _send_telegram(req['user_id'], '❌ درخواست افزودن زمان رد شد.')
        return JsonResponse({'ok': True})

    if action == 'approve_lc':
        if not req_id:
            return JsonResponse({'ok': False, 'error': 'req_id الزامی است'}, status=400)
        from shared_lib.db import (get_location_change_request, update_location_change_request,
                                   perform_location_change, get_text)
        req = async_to_sync(get_location_change_request)(int(req_id))
        if not req:
            return JsonResponse({'ok': False, 'error': 'درخواست یافت نشد'}, status=404)
        if req['status'] != 'pending':
            return JsonResponse({'ok': False, 'error': 'قبلاً پردازش شده'})
        try:
            result = async_to_sync(perform_location_change)(req['order_id'], req['to_server_id'])
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'خطا در انتقال: {e}'})
        async_to_sync(update_location_change_request)(int(req_id), 'approved')
        _send_telegram(req['user_id'], get_text(
            'changeloc_user_approved',
            server=req['to_server_name'], url=result['subscription_url']
        ))
        return JsonResponse({'ok': True})

    if action == 'reject_lc':
        if not req_id:
            return JsonResponse({'ok': False, 'error': 'req_id الزامی است'}, status=400)
        from shared_lib.db import (get_location_change_request, update_location_change_request,
                                   get_text)
        req = async_to_sync(get_location_change_request)(int(req_id))
        if not req:
            return JsonResponse({'ok': False, 'error': 'درخواست یافت نشد'}, status=404)
        if req['status'] != 'pending':
            return JsonResponse({'ok': False, 'error': 'قبلاً پردازش شده'})
        async_to_sync(update_location_change_request)(int(req_id), 'rejected')
        _send_telegram(req['user_id'], get_text('changeloc_user_rejected'))
        return JsonResponse({'ok': True})

    if action == 'toggle_changeloc_admin':
        from shared_lib.db import get_setting as _gs, set_setting as _ss
        current = (async_to_sync(_gs)('changeloc_need_admin') or '1') == '1'
        async_to_sync(_ss)('changeloc_need_admin', '0' if current else '1')
        return JsonResponse({'ok': True, 'need_admin': not current})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


# ═══════════════════════════════════════════════════════════════════════════
#  API — جوین اجباری کانال
# ═══════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def force_join_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')
    channel_id = data.get('channel_id')

    if action == 'toggle_enabled':
        enabled = async_to_sync(get_setting)('force_join_enabled')
        async_to_sync(set_setting)('force_join_enabled', '0' if enabled == '1' else '1')
        return JsonResponse({'ok': True})

    if action == 'add':
        from shared_lib.db import add_required_channel
        chat_id = (data.get('chat_id') or '').strip()
        title = (data.get('title') or '').strip()
        link = (data.get('invite_link') or '').strip()
        if not chat_id.startswith('@') and not chat_id.startswith('-100'):
            return JsonResponse({'ok': False, 'error': 'آیدی باید با @ یا -100 شروع بشه'})
        async_to_sync(add_required_channel)(chat_id, title or None, link or None)
        return JsonResponse({'ok': True})

    if action == 'update':
        from shared_lib.db import update_required_channel
        if not channel_id:
            return JsonResponse({'ok': False, 'error': 'channel_id الزامی است'}, status=400)
        chat_id = (data.get('chat_id') or '').strip()
        title = (data.get('title') or '').strip()
        link = (data.get('invite_link') or '').strip()
        if not chat_id.startswith('@') and not chat_id.startswith('-100'):
            return JsonResponse({'ok': False, 'error': 'آیدی باید با @ یا -100 شروع بشه'})
        async_to_sync(update_required_channel)(int(channel_id), chat_id=chat_id, title=title, invite_link=link)
        return JsonResponse({'ok': True})

    if action == 'toggle':
        from shared_lib.db import toggle_required_channel
        if not channel_id:
            return JsonResponse({'ok': False, 'error': 'channel_id الزامی است'}, status=400)
        async_to_sync(toggle_required_channel)(int(channel_id))
        return JsonResponse({'ok': True})

    if action == 'delete':
        from shared_lib.db import delete_required_channel
        if not channel_id:
            return JsonResponse({'ok': False, 'error': 'channel_id الزامی است'}, status=400)
        async_to_sync(delete_required_channel)(int(channel_id))
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)

# ─── وضعیت بات و جستجوی سراسری ───────────────────────────────────────────────

@login_required
def bot_status(request):
    from datetime import timezone as _tz
    heartbeat = async_to_sync(get_setting)('bot_heartbeat')
    bot_name = async_to_sync(get_setting)('bot_username') or ''
    online = False
    if heartbeat:
        try:
            last = datetime.fromisoformat(heartbeat)
            if last.tzinfo is None:
                last = last.replace(tzinfo=_tz.utc)
            online = (datetime.now(_tz.utc) - last).total_seconds() < 150
        except ValueError:
            pass
    return JsonResponse({'online': online, 'bot_name': bot_name})


@login_required
def global_search(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    results = []
    q_clean = q.lstrip('@')

    from django.db.models import Q as _Q
    users_qs = Users.objects.filter(
        _Q(username__icontains=q_clean) | _Q(first_name__icontains=q)
    )
    if q.lstrip('-').isdigit():
        users_qs = Users.objects.filter(user_id=int(q)) | users_qs
    for u in users_qs[:5]:
        title = u.first_name or (f'@{u.username}' if u.username else f'#{u.user_id}')
        results.append({
            'kind': 'user',
            'title': title,
            'sub': f'{u.user_id}' + (f' — @{u.username}' if u.username else ''),
            'url': f'/diako/users/?q={u.user_id}',
        })

    orders_qs = Orders.objects.select_related('plan').filter(username__icontains=q_clean).order_by('-id')
    if q.isdigit():
        orders_qs = Orders.objects.select_related('plan').filter(id=int(q)) | orders_qs
    for o in orders_qs[:5]:
        results.append({
            'kind': 'order',
            'title': f'#{o.id}' + (f' — @{o.username}' if o.username else ''),
            'sub': (o.plan.name if o.plan_id else '—') + f' · {o.status}',
            'url': f'/diako/orders/?q={o.username or ""}',
        })

    for s in Servers.objects.filter(name__icontains=q)[:4]:
        results.append({
            'kind': 'server',
            'title': s.name,
            'sub': s.panel_url or '',
            'url': '/diako/servers/',
        })

    for p in Plans.objects.filter(name__icontains=q)[:4]:
        results.append({
            'kind': 'plan',
            'title': p.name,
            'sub': f'{p.price:,}',
            'url': '/diako/plans/',
        })

    return JsonResponse({'results': results[:14]})


@require_http_methods(["POST"])
@login_required
def bot_settings_action(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    action = data.get('action')

    def _valid_group(v):
        v = (v or '').strip()
        return v == '' or v.lstrip('-').isdigit()

    if action == 'save_groups':
        ticket = (data.get('ticket_group') or '').strip()
        notif = (data.get('notif_group') or '').strip()
        if not _valid_group(ticket) or not _valid_group(notif):
            return JsonResponse({'ok': False, 'error': 'آیدی گروه باید عددی باشد (مثل -1001234567890)'})
        async_to_sync(set_setting)('support_group_id', ticket)
        async_to_sync(set_setting)('notif_group_id', notif)
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)


# ─── admins (access control) ─────────────────────────────────────────────────

def _bootstrap_ids():
    raw = os.environ.get('ADMIN_IDS', '')
    if not raw:
        env_path = pathlib.Path(__file__).parent.parent.parent / 'bot' / '.env'
        try:
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith('ADMIN_IDS='):
                    raw = line[len('ADMIN_IDS='):].strip()
                    break
        except Exception:
            pass
    ids = set()
    for part in raw.replace(',', ' ').split():
        if part.strip().lstrip('-').isdigit():
            ids.add(int(part))
    return ids


def _panel_can_manage(request):
    if request.user.is_superuser:
        return True
    admin = async_to_sync(get_admin_by_panel_user)(request.user.id)
    return can_manage_admins(admin) if admin else False


def _actor(request):
    """(admin_id, name) of the acting panel user, for the audit log."""
    admin = async_to_sync(get_admin_by_panel_user)(request.user.id)
    if admin:
        return admin['id'], (admin.get('display_name') or request.user.username)
    return None, request.user.username


@require_http_methods(["POST"])
@login_required
def admin_action(request):
    if not _panel_can_manage(request):
        return JsonResponse({'ok': False, 'error': 'دسترسی مدیریت ادمین‌ها را نداری'}, status=403)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    from django.contrib.auth.models import User

    action = data.get('action')
    admin_id = data.get('id')
    actor_id, actor_name = _actor(request)

    def _clean_perms(d):
        role = d.get('role') or 'standard'
        if role not in ADMIN_ROLES:
            role = 'standard'
        sections = d.get('sections') or {}
        mgmt = d.get('admin_management') or {}
        if not sections and not mgmt:
            return role, role_default_permissions(role)
        return role, build_permissions(sections, mgmt)

    if action == 'add':
        display_name = (data.get('display_name') or '').strip() or None
        is_bot = 1 if data.get('is_bot_admin') else 0
        is_panel = 1 if data.get('is_panel_admin') else 0
        note = (data.get('note') or '').strip() or None
        if not is_bot and not is_panel:
            return JsonResponse({'ok': False, 'error': 'حداقل یکی از بات یا پنل را انتخاب کن'})
        role, permissions = _clean_perms(data)

        telegram_id = None
        if is_bot:
            tid = str(data.get('telegram_id') or '').strip()
            if not tid.lstrip('-').isdigit():
                return JsonResponse({'ok': False, 'error': 'آیدی تلگرام باید عددی باشد'})
            telegram_id = int(tid)
            if telegram_id in _bootstrap_ids():
                return JsonResponse({'ok': False, 'error': 'این آیدی از قبل مالک (env) است'})
            if async_to_sync(get_admin_by_telegram)(telegram_id):
                return JsonResponse({'ok': False, 'error': 'ادمینی با این آیدی تلگرام وجود دارد'})

        panel_user_id = None
        if is_panel:
            username = (data.get('username') or '').strip()
            password = data.get('password') or ''
            if not username or not password:
                return JsonResponse({'ok': False, 'error': 'یوزرنیم و پسورد پنل لازم است'})
            if User.objects.filter(username=username).exists():
                return JsonResponse({'ok': False, 'error': 'این یوزرنیم قبلاً ثبت شده'})
            user = User.objects.create_user(username=username, password=password)
            user.is_staff = True
            user.is_superuser = (role == 'sudo')
            user.save()
            panel_user_id = user.id

        new_id = async_to_sync(add_admin)(
            display_name=display_name, role=role, telegram_id=telegram_id,
            panel_user_id=panel_user_id, is_bot_admin=is_bot, is_panel_admin=is_panel,
            permissions=permissions, note=note, added_by=actor_id,
        )
        async_to_sync(log_admin_action)(
            actor_id, actor_name, 'admin.add',
            display_name or (str(telegram_id) if telegram_id else data.get('username')))
        return JsonResponse({'ok': True, 'id': new_id})

    # everything below targets an existing managed admin
    if not admin_id:
        return JsonResponse({'ok': False, 'error': 'id الزامی است'}, status=400)
    target = async_to_sync(get_admin)(int(admin_id))
    if not target:
        return JsonResponse({'ok': False, 'error': 'ادمین پیدا نشد'}, status=404)
    if target['telegram_id'] in _bootstrap_ids():
        return JsonResponse({'ok': False, 'error': 'مالک اصلی (env) قابل تغییر نیست'})

    if action == 'toggle':
        new_status = 0 if target['status'] else 1
        async_to_sync(set_admin_status)(target['id'], new_status)
        if target['panel_user_id']:
            User.objects.filter(id=target['panel_user_id']).update(is_active=bool(new_status))
        async_to_sync(log_admin_action)(actor_id, actor_name, 'admin.toggle',
                                        target.get('display_name') or str(target['id']))
        return JsonResponse({'ok': True})

    if action == 'update':
        display_name = (data.get('display_name') or '').strip() or None
        is_bot = 1 if data.get('is_bot_admin') else 0
        is_panel = 1 if data.get('is_panel_admin') else 0
        note = (data.get('note') or '').strip() or None
        if not is_bot and not is_panel:
            return JsonResponse({'ok': False, 'error': 'حداقل یکی از بات یا پنل را انتخاب کن'})
        role, permissions = _clean_perms(data)

        fields = {
            'display_name': display_name, 'role': role, 'permissions': permissions,
            'is_bot_admin': is_bot, 'is_panel_admin': is_panel, 'note': note,
        }

        if is_bot:
            tid = str(data.get('telegram_id') or '').strip()
            if not tid.lstrip('-').isdigit():
                return JsonResponse({'ok': False, 'error': 'آیدی تلگرام باید عددی باشد'})
            telegram_id = int(tid)
            existing = async_to_sync(get_admin_by_telegram)(telegram_id)
            if existing and existing['id'] != target['id']:
                return JsonResponse({'ok': False, 'error': 'ادمین دیگری با این آیدی تلگرام هست'})
            fields['telegram_id'] = telegram_id
        else:
            fields['telegram_id'] = None

        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        if is_panel:
            if target['panel_user_id']:
                user = User.objects.filter(id=target['panel_user_id']).first()
                if user:
                    if username and username != user.username:
                        if User.objects.filter(username=username).exclude(id=user.id).exists():
                            return JsonResponse({'ok': False, 'error': 'این یوزرنیم قبلاً ثبت شده'})
                        user.username = username
                    if password:
                        user.set_password(password)
                    user.is_superuser = (role == 'sudo')
                    user.is_active = True
                    user.save()
            else:
                if not username or not password:
                    return JsonResponse({'ok': False, 'error': 'برای دسترسی پنل، یوزرنیم و پسورد لازم است'})
                if User.objects.filter(username=username).exists():
                    return JsonResponse({'ok': False, 'error': 'این یوزرنیم قبلاً ثبت شده'})
                user = User.objects.create_user(username=username, password=password)
                user.is_staff = True
                user.is_superuser = (role == 'sudo')
                user.save()
                fields['panel_user_id'] = user.id
        elif target['panel_user_id']:
            User.objects.filter(id=target['panel_user_id']).update(is_active=False)

        async_to_sync(update_admin)(target['id'], **fields)
        async_to_sync(log_admin_action)(actor_id, actor_name, 'admin.update',
                                        display_name or str(target['id']))
        return JsonResponse({'ok': True})

    if action == 'delete':
        if target['panel_user_id']:
            User.objects.filter(id=target['panel_user_id']).delete()
        async_to_sync(delete_admin)(target['id'])
        async_to_sync(log_admin_action)(actor_id, actor_name, 'admin.delete',
                                        target.get('display_name') or str(target['id']))
        return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'action نامعتبر'}, status=400)
