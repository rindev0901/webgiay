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
    path('portal/', v.supplier_portal, name='supplier_portal'),
    path('portal/<int:pr_pk>/quote/', v.submit_quote, name='submit_quote'),
    path('portal/<int:pr_pk>/export/', v.supplier_export_csv, name='supplier_export_csv'),
]
