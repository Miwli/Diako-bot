import time

from asgiref.sync import async_to_sync
from django.conf import settings

# short-lived cache so we don't hit the DB on every request
_lang_cache = {'value': None, 'ts': 0.0}


def _default_lang():
    now = time.time()
    if now - _lang_cache['ts'] > 5:
        try:
            from shared_lib.db import get_setting
            _lang_cache['value'] = async_to_sync(get_setting)('panel_default_lang')
        except Exception:
            _lang_cache['value'] = None
        _lang_cache['ts'] = now
    return _lang_cache['value']


class PanelDefaultLanguageMiddleware:
    """Apply the panel's default language for visitors who have not explicitly
    picked one. LocaleMiddleware reads the language cookie; when it is absent we
    inject the configured default into request.COOKIES so LocaleMiddleware uses
    it. A user who switches language via the topbar sets a real cookie, which
    takes precedence and is never overridden here."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_name = settings.LANGUAGE_COOKIE_NAME
        if cookie_name not in request.COOKIES:
            default = _default_lang()
            if default in ('fa', 'en'):
                request.COOKIES[cookie_name] = default
        return self.get_response(request)
