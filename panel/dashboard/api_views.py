import json
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
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
