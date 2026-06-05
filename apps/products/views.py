from django.shortcuts import render, get_object_or_404
from django.db.models import Prefetch
from django.core.paginator import Paginator
from .models import (
    Product,
    Category,
    Brand,
    ProductVariant,
    ProductImage
)
from django.http import HttpRequest
from django.db.models import Q
from decimal import Decimal, InvalidOperation


def product_list(request: HttpRequest):
    """Trang danh sách sản phẩm"""

    category_slug = request.GET.get('category')
    brand_slug = request.GET.get('brand')
    sort = request.GET.get('sort', '-created_at')
    price_range = request.GET.get('price_range')

    products = Product.objects.filter(is_active=True)\
        .select_related('brand', 'category')\
        .prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.filter(
                is_active=True)),
            Prefetch('images', queryset=ProductImage.objects.filter(
                is_primary=True))
    )

    # Filter by category
    if category_slug:
        products = products.filter(category__slug=category_slug)

    # Filter by brand
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)

    # Price range filter
    min_price = None
    max_price = None

    if price_range:
        try:
            parts = price_range.split('-')
            if len(parts) == 2:
                min_price = int(parts[0])
                max_price = int(parts[1])

                # Filter by final_price (discount_price or price)
                products = products.filter(
                    Q(discount_price__gte=min_price, discount_price__lte=max_price) |
                    Q(discount_price__isnull=True, price__gte=min_price, price__lte=max_price)
                )
        except (ValueError, IndexError):
            pass

    # Manual min/max price filter (for custom input)
    manual_min = request.GET.get('min_price')
    manual_max = request.GET.get('max_price')
    if manual_min:
        try:
            min_val = Decimal(manual_min)
            products = products.filter(
                Q(discount_price__gte=min_val) |
                Q(discount_price__isnull=True, price__gte=min_val)
            )
            min_price = int(min_val)
        except (InvalidOperation, ValueError):
            pass
    if manual_max:
        try:
            max_val = Decimal(manual_max)
            products = products.filter(
                Q(discount_price__lte=max_val) |
                Q(discount_price__isnull=True, price__lte=max_val)
            )
            max_price = int(max_val)
        except (InvalidOperation, ValueError):
            pass

    # Sorting
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    else:
        products = products.order_by(sort)

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    categories = Category.objects.filter(is_active=True)
    brands = Brand.objects.filter(is_active=True)

    context = {
        'products': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'categories': categories,
        'brands': brands,
        'title': 'Tất cả sản phẩm - WebGiày',
        'current_category': category_slug,
        'current_brand': brand_slug,
        'current_sort': sort,
        'current_price_range': price_range,
        'query_string': query_string,
        'min_price': min_price,
        'max_price': max_price,
    }
    return render(request, 'product_list.html', context)


def landing(request: HttpRequest):
    """Landing page with featured products"""
    # Sản phẩm nổi bật (dùng cho section Siêu Khuyến Mãi)
    featured = Product.objects.filter(is_active=True, featured=True)\
        .select_related('brand', 'category')\
        .prefetch_related(
            Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
        )[:10]

    # Sản phẩm đang giảm giá (có discount_price)
    sale_products = Product.objects.filter(is_active=True, discount_price__isnull=False)\
        .select_related('brand', 'category')\
        .prefetch_related(
            Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
        )[:10]

    # Danh mục cho thanh điều hướng
    categories = Category.objects.filter(is_active=True)

    # Tất cả thương hiệu cho tab Giày Sneaker
    brands = Brand.objects.filter(is_active=True)

    # Sản phẩm Giày Sneaker (tất cả, dùng filter JS phía client)
    sneaker_products = Product.objects.filter(is_active=True)\
        .select_related('brand', 'category')\
        .prefetch_related(
            Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
        ).order_by('-created_at')[:10]

    context = {
        'featured': featured,
        'sale_products': sale_products,
        'sneaker_products': sneaker_products,
        'brands': brands,
        'categories': categories,
        'title': 'Dat Shoes - Giày Chính Hãng',
    }
    return render(request, 'index.html', context)


def category_detail(request, slug):
    """Xem theo danh mục + chỉ hiển thị thương hiệu có trong danh mục đó"""
    category = get_object_or_404(Category, slug=slug, is_active=True)

    # Lấy sản phẩm thuộc danh mục
    products = Product.objects.filter(
        category=category,
        is_active=True
    ).select_related('brand', 'category').prefetch_related('variants', 'images')

    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    # Lấy THƯƠNG HIỆU chỉ có trong danh mục này
    brands_in_category = Brand.objects.filter(
        products__category=category,
        is_active=True
    ).distinct()

    context = {
        'category': category,
        'products': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'categories': Category.objects.filter(is_active=True),
        'brands': brands_in_category,           # ← Quan trọng nhất
        'current_category': category.slug,
        'title': f'{category.name} - WebGiày'
        ,
        'query_string': query_string,
    }
    return render(request, 'product_list.html', context)


def product_detail(request: HttpRequest, slug: str):
    """Chi tiết sản phẩm"""
    import json
    product = get_object_or_404(Product, slug=slug, is_active=True)

    variants = product.variants.filter(is_active=True).select_related('color', 'size').order_by('size__order', 'size__name')
    images = product.images.all().select_related('color').order_by('-is_primary', 'color', 'order')

    # Group ảnh theo color_id để JS đổi gallery khi chọn màu
    # color_id=0 → ảnh chung (không gắn màu cụ thể)
    images_by_color: dict = {}   # {color_id_or_0: [{url, alt}]}
    all_images_list = []         # flat list cho gallery fallback
    for img in images:
        cid = img.color_id or 0
        if cid not in images_by_color:
            images_by_color[cid] = []
        entry = {'url': img.image.url, 'alt': img.alt_text or product.name}
        images_by_color[cid].append(entry)
        all_images_list.append(entry)

    # Group variants by color
    colors_map = {}
    for v in variants:
        color_id = v.color_id or 0
        color_name = v.color.name if v.color else 'Mặc định'
        color_hex = v.color.hex_code if v.color else ''
        if color_id not in colors_map:
            colors_map[color_id] = {
                'id': color_id,
                'name': color_name,
                'hex': color_hex,
                'sizes': [],
                # Ảnh của màu này: ưu tiên ảnh gắn màu, fallback ảnh chung
                'images': images_by_color.get(color_id)
                          or images_by_color.get(0)
                          or all_images_list,
            }
        colors_map[color_id]['sizes'].append({
            'id': v.id,
            'size': v.size.name,
            'size_id': v.size_id,
            'stock': v.stock,
            'sku': v.sku,
            'price': str(v.price or product.final_price),
        })

    colors_list = list(colors_map.values())

    # Đọc state từ URL params
    try:
        url_color_id = int(request.GET.get('color', 0))
    except (ValueError, TypeError):
        url_color_id = 0
    try:
        url_size_id = int(request.GET.get('size', 0))
    except (ValueError, TypeError):
        url_size_id = 0

    valid_color_ids = set(colors_map.keys())
    if url_color_id not in valid_color_ids:
        url_color_id = colors_list[0]['id'] if colors_list else 0

    selected_color_data = colors_map.get(url_color_id, {})
    valid_size_ids = {s['size_id'] for s in selected_color_data.get('sizes', [])}
    if url_size_id not in valid_size_ids:
        for s in selected_color_data.get('sizes', []):
            if s['stock'] > 0:
                url_size_id = s['size_id']
                break
        else:
            url_size_id = 0

    related_products = Product.objects.filter(
        category=product.category, is_active=True
    ).exclude(id=product.pk).prefetch_related(
        Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
    )[:6]

    # Ảnh hiển thị ban đầu (theo màu được chọn từ URL)
    initial_images = (
        images_by_color.get(url_color_id)
        or images_by_color.get(0)
        or all_images_list
    )

    context = {
        'product': product,
        'variants': variants,
        'colors_list': colors_list,
        'variants_json': json.dumps(colors_list),
        'images_by_color_json': json.dumps(images_by_color),
        'initial_images': initial_images,
        'initial_color_id': url_color_id,
        'initial_size_id': url_size_id,
        'related_products': related_products,
        'title': f'{product.name} - Dat Shoes',
    }

    # Track recently viewed (lưu session, tối đa 8 sản phẩm)
    rv = request.session.get('recently_viewed', [])
    if product.id in rv:
        rv.remove(product.id)
    rv.insert(0, product.id)
    request.session['recently_viewed'] = rv[:8]

    return render(request, 'product_detail.html', context)
