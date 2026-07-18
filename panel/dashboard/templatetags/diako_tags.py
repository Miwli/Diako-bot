import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import jdatetime
from asgiref.sync import async_to_sync
from django import template

register = template.Library()

TEHRAN = ZoneInfo("Asia/Tehran")

# short-lived cache for the calendar preference so a page full of dates
# does not hit the DB per value
_cal_cache = {'value': None, 'ts': 0.0}


def _calendar_pref():
    now = time.time()
    if now - _cal_cache['ts'] > 5:
        try:
            from shared_lib.db import get_setting
            _cal_cache['value'] = async_to_sync(get_setting)('panel_default_calendar') or 'jalali'
        except Exception:
            _cal_cache['value'] = 'jalali'
        _cal_cache['ts'] = now
    return _cal_cache['value']


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
    if _calendar_pref() == 'gregorian':
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
