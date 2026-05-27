from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

# Redirect trang chủ về danh sách sản phẩm
def home_redirect(request):
    return redirect('products:product_list')


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API
    path('api/', include('apps.products.urls')),
    
    # Frontend - Trang chủ và các trang sản phẩm
    path('', home_redirect, name='home'),           # ← Trang chủ
    path('', include('apps.products.urls')),        # ← Các trang sản phẩm
]