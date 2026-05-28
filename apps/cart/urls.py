from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path('', views.cart_detail, name="cart_detail"),
    path('add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('update/<int:product_id>/', views.update_cart, name='update_cart'),
    path('remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear/', views.clear_cart, name='clear_cart'),
    path('momo/checkout/', views.momo_checkout, name='momo_checkout'),
    path('momo/return/', views.momo_return, name='momo_return'),
    path('momo/ipn/', views.momo_ipn, name='momo_ipn'),
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/<str:code>/', views.order_detail, name='order_detail'),
    path('orders/<str:code>/retry/', views.order_retry, name='order_retry'),
]
