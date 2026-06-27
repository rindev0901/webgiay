"""Admin/public URL paths for supply chain pages."""
SUPPLY_PATHS = {
    'bien_do': '/supply/',
    'request_list': '/supply/requests/',
    'request_create': '/supply/requests/create/',
    'request_detail': '/supply/requests/{pk}/',
    'export_csv': '/supply/requests/{pk}/export/',
    'send': '/supply/requests/{pk}/send/',
    'approve': '/supply/requests/{pk}/approve/',
    'receive': '/supply/requests/{pk}/receive/',
    'bao_gia': '/supply/portal/',
    'submit_quote': '/supply/portal/{pk}/quote/',
    'supplier_export': '/supply/portal/{pk}/export/',
    'admin_index': '/admin/',
}

SUPPLY_ALIASES = {
    'analytics': 'bien_do',
    'request_list': 'request_list',
    'request_create': 'request_create',
    'request_detail': 'request_detail',
    'export_csv': 'export_csv',
    'send_to_suppliers': 'send',
    'approve_request': 'approve',
    'receive_goods': 'receive',
    'supplier_portal': 'bao_gia',
    'submit_quote': 'submit_quote',
    'supplier_export_csv': 'supplier_export',
}


def supply_path(name, pk=None):
    key = SUPPLY_ALIASES.get(name, name)
    path = SUPPLY_PATHS.get(key, '/supply/')
    if pk is not None and '{pk}' in path:
        return path.format(pk=pk)
    return path
