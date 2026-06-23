import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.views.decorators.http import require_http_methods
from datetime import datetime, timedelta
from asgiref.sync import async_to_sync
from shared_lib.db import get_all_keyboard_buttons, get_keyboard_actions, save_keyboard_layout
from .models import Orders


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


@login_required
def keyboard_data(request, keyboard_name):
    if request.GET.get('all') == '1':
        buttons = async_to_sync(get_all_keyboard_buttons)(keyboard_name)
    else:
        from shared_lib.db import get_keyboard_buttons
        buttons = async_to_sync(get_keyboard_buttons)(keyboard_name)
    return JsonResponse({'buttons': buttons})


@login_required
@require_http_methods(["POST"])
def save_keyboard(request):
    try:
        data = json.loads(request.body)
        buttons = data.get('buttons', [])
        keyboard_name = data.get('keyboard_name', 'user_main')
        async_to_sync(save_keyboard_layout)(keyboard_name, buttons)
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)
