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


def product_list(request: HttpRequest):
    """Trang danh sách sản phẩm"""

    category_slug = request.GET.get('category')
    brand_slug = request.GET.get('brand')
    sort = request.GET.get('sort', '-created_at')

    products = Product.objects.filter(is_active=True)\
        .select_related('brand', 'category')\
        .prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.filter(
                is_active=True)),
            Prefetch('images', queryset=ProductImage.objects.filter(
                is_primary=True))
    )

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)

    # Sắp xếp
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    else:
        products = products.order_by(sort)

    paginator = Paginator(products, 9)
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
        'query_string': query_string,
    }
    return render(request, 'product_list.html', context)


def landing(request: HttpRequest):
    """Landing page with featured products"""
    featured = Product.objects.filter(is_active=True, featured=True)
    # Prefetch primary images for featured display
    featured = featured.select_related('brand', 'category').prefetch_related(
        Prefetch('images', queryset=ProductImage.objects.filter(is_primary=True))
    )[:8]

    categories = Category.objects.filter(is_active=True)

    context = {
        'featured': featured,
        'categories': categories,
        'title': 'WebGiày - Trang chủ'
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
    product = get_object_or_404(Product, slug=slug, is_active=True)

    variants = product.variants.filter(is_active=True).select_related('color')
    images = product.images.all().order_by('-is_primary')

    related_products = Product.objects.filter(
        category=product.category,
        is_active=True
    ).exclude(id=product.pk)[:4]

    context = {
        'product': product,
        'variants': variants,
        'images': images,
        'related_products': related_products,
        'title': f'{product.name} - WebGiày'
    }
    return render(request, 'product_detail.html', context)
