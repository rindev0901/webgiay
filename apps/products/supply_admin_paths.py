"""Admin/public URL paths for supply chain pages."""

SUPPLY_PATHS = {
    "bien_do": "/supply/",
    "request_list": "/supply/requests/",
    "request_create": "/supply/requests/create/",
    "request_detail": "/supply/requests/{pk}/",
    "export_csv": "/supply/requests/{pk}/export/",
    "send": "/supply/requests/{pk}/send/",
    "approve": "/supply/requests/{pk}/approve/",
    "receive": "/supply/requests/{pk}/receive/",
    "bao_gia": "/supply/portal/",
    "submit_quote": "/supply/portal/{pk}/quote/",
    "supplier_export": "/supply/portal/{pk}/export/",
    # Inventory Check Paths
    "inventory_check_list": "/supply/inventory-checks/",
    "inventory_check_detail": "/supply/inventory-checks/{pk}/",
    "perform_inventory_check": "/supply/inventory-checks/{pk}/perform/",
    "approve_inventory_check": "/supply/inventory-checks/{pk}/approve/",
    "add_stock_from_check": "/supply/inventory-checks/{pk}/add-stock/",
    "create_payment_from_check": "/supply/inventory-checks/{pk}/create-payment/",
    # Payment Voucher Paths
    "payment_voucher_list": "/supply/payment-vouchers/",
    "payment_voucher_detail": "/supply/payment-vouchers/{pk}/",
    "mark_payment_paid": "/supply/payment-vouchers/{pk}/mark-paid/",
    "admin_index": "/admin/",
}

SUPPLY_ALIASES = {
    "analytics": "bien_do",
    "request_list": "request_list",
    "request_create": "request_create",
    "request_detail": "request_detail",
    "export_csv": "export_csv",
    "send_to_suppliers": "send",
    "approve_request": "approve",
    "receive_goods": "receive",
    "supplier_portal": "bao_gia",
    "submit_quote": "submit_quote",
    "supplier_export_csv": "supplier_export",
    # Inventory Check Aliases
    "inventory_check_list": "inventory_check_list",
    "inventory_check_detail": "inventory_check_detail",
    "perform_inventory_check": "perform_inventory_check",
    "approve_inventory_check": "approve_inventory_check",
    "add_stock_from_check": "add_stock_from_check",
    "create_payment_from_check": "create_payment_from_check",
    # Payment Voucher Aliases
    "payment_voucher_list": "payment_voucher_list",
    "payment_voucher_detail": "payment_voucher_detail",
    "mark_payment_paid": "mark_payment_paid",
}


def supply_path(name, pk=None):
    key = SUPPLY_ALIASES.get(name, name)
    path = SUPPLY_PATHS.get(key, "/supply/")
    if pk is not None and "{pk}" in path:
        return path.format(pk=pk)
    return path
