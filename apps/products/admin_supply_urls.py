"""Đăng ký URL supply chain trên AdminSite — chạy trong AppConfig.ready()."""
from django.contrib import admin
from django.urls import path

from . import supply_views as sv
from .supply_permissions import can_view_bien_do, can_view_bao_gia


def _wrap(view, check=None):
    def wrapper(request, *args, **kwargs):
        if check and not check(request):
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, 'Ban khong co quyen truy cap trang nay.')
            return redirect('admin:index')
        return view(request, *args, **kwargs)
    return admin.site.admin_view(wrapper)


def register_supply_admin_urls():
    """Gắn URL supply vào admin site (một lần)."""
    if getattr(admin.site, '_supply_urls_registered', False):
        return

    original_get_urls = admin.site.get_urls

    def get_urls():
        custom = [
            path(
                'products/supplier/bien-do/',
                _wrap(sv.analytics_view, can_view_bien_do),
                name='products_supplier_bien_do',
            ),
            path(
                'products/supplier/bien-do/requests/',
                _wrap(sv.request_list, can_view_bien_do),
                name='products_supplier_request_list',
            ),
            path(
                'products/supplier/bien-do/requests/create/',
                _wrap(sv.request_create, can_view_bien_do),
                name='products_supplier_request_create',
            ),
            path(
                'products/supplier/bien-do/requests/<int:pk>/',
                _wrap(sv.request_detail, can_view_bien_do),
                name='products_supplier_request_detail',
            ),
            path(
                'products/supplier/bien-do/requests/<int:pk>/export/',
                _wrap(sv.export_csv, can_view_bien_do),
                name='products_supplier_export_csv',
            ),
            path(
                'products/supplier/bien-do/requests/<int:pk>/send/',
                _wrap(sv.send_to_suppliers, can_view_bien_do),
                name='products_supplier_send',
            ),
            path(
                'products/supplier/bien-do/requests/<int:pk>/approve/',
                _wrap(sv.approve_request, can_view_bien_do),
                name='products_supplier_approve',
            ),
            path(
                'products/supplier/bien-do/requests/<int:pk>/receive/',
                _wrap(sv.receive_goods, can_view_bien_do),
                name='products_supplier_receive',
            ),
            path(
                'products/supplier/bao-gia/',
                _wrap(sv.supplier_portal, can_view_bao_gia),
                name='products_supplier_bao_gia',
            ),
            path(
                'products/supplier/bao-gia/<int:pr_pk>/quote/',
                _wrap(sv.submit_quote, can_view_bao_gia),
                name='products_supplier_submit_quote',
            ),
            path(
                'products/supplier/bao-gia/<int:pr_pk>/export/',
                _wrap(sv.supplier_export_csv, can_view_bao_gia),
                name='products_supplier_supplier_export',
            ),
        ]
        return custom + original_get_urls()

    admin.site.get_urls = get_urls
    admin.site._supply_urls_registered = True
