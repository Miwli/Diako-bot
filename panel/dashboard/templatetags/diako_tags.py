from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import jdatetime
from django import template
from django.utils.translation import get_language

register = template.Library()

TEHRAN = ZoneInfo("Asia/Tehran")


def _to_tehran(value):
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TEHRAN)


@register.filter
def jdate(value, fmt='full'):
    dt = _to_tehran(value)
    if dt is None:
        return '—'
    if get_language() == 'en':
        if fmt == 'short':
            return dt.strftime('%Y/%m/%d')
        return dt.strftime('%Y/%m/%d %H:%M')
    jdt = jdatetime.datetime.fromgregorian(datetime=dt)
    if fmt == 'short':
        return jdt.strftime('%Y/%m/%d')
    return jdt.strftime('%Y/%m/%d %H:%M')


@register.filter
def toman(value):
    try:
        return f'{int(value):,}'
    except (TypeError, ValueError):
        return value if value is not None else '۰'
