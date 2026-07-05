from django.conf import settings
from django.http import Http404


def _client_ip(request):
    """برگرداندن IP واقعی کاربر — هدر X-Forwarded-For/nginx در محیط production."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # اولین IP در زنجیره = IP واقعی کاربر
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AdminAccessMiddleware:
    """محدود کردن دسترسی به /admin/ فقط برای IP های مجاز.

    اگر ALLOWED_ADMIN_IPS در تنظیمات تعریف شده باشد، فقط آن IP ها مجازند.
    اگر تعریف نشده باشد (پیش‌فرض)، همه دسترسی دارند (کنترل دسترسی با login انجام می‌شود).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed = getattr(settings, 'ALLOWED_ADMIN_IPS', None)
        if allowed and request.path.startswith('/admin/'):
            ip = _client_ip(request)
            if ip not in allowed:
                raise Http404
        return self.get_response(request)
