from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from apps.products import views as product_views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path("cart/", include(("apps.cart.urls", "cart"), namespace="cart")),
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path('', product_views.landing, name='landing'),
    path('products/', include('apps.products.urls')),

]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
