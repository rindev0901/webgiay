from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from apps.products import views as product_views
from django.conf.urls.static import static
from django.conf import settings
import config.admin  # noqa: F401 — load User/Group unfold overrides

urlpatterns = [
    path('admin/', admin.site.urls),
    path("cart/", include(("apps.cart.urls", "cart"), namespace="cart")),
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path('', product_views.landing, name='landing'),
    path('products/', include('apps.products.urls')),
    path('supply/', include('apps.products.supply_urls')),
    # Legacy admin supply URLs → standalone app
    path('admin/products/supplier/bien-do/', RedirectView.as_view(url='/supply/', permanent=False)),
    path('admin/products/supplier/bien-do/requests/', RedirectView.as_view(url='/supply/requests/', permanent=False)),
    path('admin/products/supplier/bao-gia/', RedirectView.as_view(url='/supply/portal/', permanent=False)),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
