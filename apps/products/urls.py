from django.urls import path
from . import views
from . import views_inventory

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('<slug:slug>/', views.product_detail, name='product_detail'),
    
    # Inventory management
    path('admin/stock-in/', views_inventory.stock_in_view, name='stock_in'),
]