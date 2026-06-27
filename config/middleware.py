# middleware.py

from threading import local
from django.shortcuts import redirect

_thread_data = local()


class CurrentRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_data.request = request
        response = self.get_response(request)
        return response


class SupplyRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Dynamic import to prevent AppRegistryNotReady
            from apps.products.supply_permissions import is_supplier_user, is_store_manager
            
            # 1. Nếu là Nhà Cung Cấp
            if is_supplier_user(request.user):
                path = request.path
                if path.startswith('/admin/') and not path.startswith('/admin/logout'):
                    return redirect('/supply/portal/')
                if path == '/' or path == '/accounts/login/':
                    return redirect('/supply/portal/')
            
            # 2. Nếu là Cửa hàng trưởng (không phải admin tối cao)
            elif is_store_manager(request.user) and not request.user.is_superuser:
                path = request.path
                if path.startswith('/admin/') and not path.startswith('/admin/logout'):
                    return redirect('/supply/')
                if path == '/' or path == '/accounts/login/':
                    return redirect('/supply/')
                    
        return self.get_response(request)
