from django.urls import path
from . import supply_views as v

app_name = 'supply'

urlpatterns = [
    path('', v.analytics_view, name='analytics'),
    path('requests/', v.request_list, name='request_list'),
    path('requests/create/', v.request_create, name='request_create'),
    path('requests/<int:pk>/', v.request_detail, name='request_detail'),
    path('requests/<int:pk>/export/', v.export_csv, name='export_csv'),
    path('requests/<int:pk>/send/', v.send_to_suppliers, name='send_to_suppliers'),
    path('requests/<int:pk>/approve/', v.approve_request, name='approve_request'),
    path('requests/<int:pk>/receive/', v.receive_goods, name='receive_goods'),

    # Inventory Check URLs
    path('inventory-checks/', v.inventory_check_list, name='inventory_check_list'),
    path('inventory-checks/<int:pk>/', v.inventory_check_detail, name='inventory_check_detail'),
    path('inventory-checks/<int:pk>/perform/', v.perform_inventory_check, name='perform_inventory_check'),
    path('inventory-checks/<int:pk>/approve/', v.approve_inventory_check, name='approve_inventory_check'),
    path('inventory-checks/<int:pk>/add-stock/', v.add_stock_from_check, name='add_stock_from_check'),
    path('inventory-checks/<int:pk>/create-payment/', v.create_payment_from_check, name='create_payment_from_check'),

    # Payment Voucher URLs
    path('payment-vouchers/', v.payment_voucher_list, name='payment_voucher_list'),
    path('payment-vouchers/<int:pk>/', v.payment_voucher_detail, name='payment_voucher_detail'),
    path('payment-vouchers/<int:pk>/mark-paid/', v.mark_payment_paid, name='mark_payment_paid'),

    # Supplier Portal URLs
    path('portal/', v.supplier_portal, name='supplier_portal'),
    path('portal/<int:pr_pk>/quote/', v.submit_quote, name='submit_quote'),
    path('portal/<int:pr_pk>/export/', v.supplier_export_csv, name='supplier_export_csv'),

    # Director / General Director URLs
    path('dashboard/', v.director_dashboard, name='director_dashboard'),
    path('activity-log/', v.activity_log_view, name='activity_log'),
]

