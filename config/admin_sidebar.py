"""Cấu hình sidebar Unfold — tất cả nhóm cùng cấp."""
from apps.products.supply_admin_paths import SUPPLY_PATHS

SIDEBAR_NAVIGATION = [
    {
        "title": "Chuỗi cung ứng",
        "separator": True,
        "collapsible": True,
        "items": [
            {"title": "Biên độ / CHT", "icon": "analytics", "link": SUPPLY_PATHS["bien_do"]},
            {"title": "Yêu cầu đặt hàng", "icon": "inventory_2", "link": SUPPLY_PATHS["request_list"]},
            {"title": "Báo giá NCC", "icon": "mail", "link": SUPPLY_PATHS["bao_gia"]},
        ],
    },
    {
        "title": "Quản lý Sản phẩm",
        "collapsible": True,
        "items": [
            {"title": "Sản phẩm", "icon": "inventory", "link": "/admin/products/product/"},
            {"title": "Biến thể", "icon": "style", "link": "/admin/products/productvariant/"},
            {"title": "Danh mục", "icon": "category", "link": "/admin/products/category/"},
            {"title": "Thương hiệu", "icon": "sell", "link": "/admin/products/brand/"},
            {"title": "Màu sắc", "icon": "palette", "link": "/admin/products/color/"},
            {"title": "Kích thước", "icon": "straighten", "link": "/admin/products/size/"},
            {"title": "Hình ảnh sản phẩm", "icon": "image", "link": "/admin/products/productimage/"},
            {"title": "Nhà cung cấp", "icon": "store", "link": "/admin/products/supplier/"},
            {"title": "Lịch sử tồn kho", "icon": "history", "link": "/admin/products/stockmovement/"},
        ],
    },
    {
        "title": "Quản lý Đơn hàng",
        "collapsible": True,
        "items": [
            {"title": "Đơn hàng", "icon": "shopping_cart", "link": "/admin/cart/order/"},
            {"title": "Phiếu giảm giá", "icon": "confirmation_number", "link": "/admin/cart/voucher/"},
        ],
    },
    {
        "title": "Xác thực và ủy quyền",
        "collapsible": True,
        "items": [
            {"title": "Người sử dụng", "icon": "person", "link": "/admin/auth/user/"},
            {"title": "Các nhóm", "icon": "group", "link": "/admin/auth/group/"},
        ],
    },
]
