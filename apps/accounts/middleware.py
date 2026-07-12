import threading

_thread_locals = threading.local()

class CurrentRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        response = self.get_response(request)
        if hasattr(_thread_locals, "request"):
            del _thread_locals.request
        return response

    @classmethod
    def get_current_request(cls):
        return getattr(_thread_locals, "request", None)

    @classmethod
    def get_current_user(cls):
        request = cls.get_current_request()
        if request and request.user and request.user.is_authenticated:
            return request.user
        return None

    @classmethod
    def get_client_ip(cls):
        request = cls.get_current_request()
        if not request:
            return None
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
