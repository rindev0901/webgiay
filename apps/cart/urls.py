from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path('', views.cart_detail, name="cart_detail"),
    path('checkout/', views.checkout, name='checkout'),
    path('add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('update/<int:product_id>/', views.update_cart, name='update_cart'),
    path('remove/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear/', views.clear_cart, name='clear_cart'),
    # MoMo
    path('momo/checkout/', views.momo_checkout, name='momo_checkout'),
    path('momo/return/', views.momo_return, name='momo_return'),
    path('momo/ipn/', views.momo_ipn, name='momo_ipn'),
    # SePay
    path('sepay/checkout/', views.sepay_checkout, name='sepay_checkout'),
    path('sepay/return/', views.sepay_return, name='sepay_return'),
    path('sepay/ipn/', views.sepay_ipn, name='sepay_ipn'),
    # Voucher
    path('voucher/apply/',  views.apply_voucher,  name='apply_voucher'),
    path('voucher/remove/', views.remove_voucher, name='remove_voucher'),
    # Orders
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/<str:code>/', views.order_detail, name='order_detail'),
    path('orders/<str:code>/retry/', views.order_retry, name='order_retry'),
    path('orders/<str:code>/confirm-delivery/', views.order_qr_confirm, name='order_qr_confirm'),
]
