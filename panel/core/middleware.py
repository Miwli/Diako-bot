from django.http import Http404


class AdminAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/') and request.META.get('REMOTE_ADDR') != '127.0.0.1':
            raise Http404
        return self.get_response(request)
