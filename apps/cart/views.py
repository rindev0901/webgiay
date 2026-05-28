from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.apps import apps
from django.views.decorators.http import require_POST

from .services import (
    add_product_to_user_cart,
    clear_session_cart,
    clear_user_cart,
    get_or_create_user_cart,
    get_session_cart,
    get_user_cart_items,
    remove_product_from_user_cart,
    set_session_cart,
    set_user_cart_item_quantity,
)

Product = apps.get_model('products', 'Product')


def _get_cart(request):
    return request.session.setdefault('cart', {})


def cart_detail(request):
    items = []
    total = Decimal('0')

    if request.user.is_authenticated:
        for item in get_user_cart_items(request.user):
            price = item.price or item.product.final_price
            subtotal = price * item.quantity
            items.append({
                'product': item.product,
                'quantity': item.quantity,
                'price': price,
                'subtotal': subtotal,
                'cart_item': item,
            })
            total += subtotal
    else:
        cart = get_session_cart(request.session)
        product_ids = [int(pid) for pid in cart.keys()] if cart else []
        products = Product.objects.filter(id__in=product_ids)
        for p in products:
            pid = str(p.pk)
            qty = int(cart.get(pid, {}).get('quantity', 0))
            price = getattr(p, 'discount_price', None) or getattr(p, 'price', 0)
            subtotal = price * qty
            items.append({
                'product': p,
                'quantity': qty,
                'price': price,
                'subtotal': subtotal,
            })
            total += subtotal

    return render(request, 'cart_detail.html', {'cart_items': items, 'total': total})


@require_POST
def add_to_cart(request, product_id):
    qty = int(request.POST.get('quantity', 1))
    product = get_object_or_404(Product, pk=product_id)

    if request.user.is_authenticated:
        add_product_to_user_cart(request.user, product, qty)
    else:
        cart = _get_cart(request)
        pid = str(product_id)
        cart.setdefault(pid, {'quantity': 0})
        cart[pid]['quantity'] = cart[pid].get('quantity', 0) + qty
        request.session.modified = True

    next_url = request.POST.get(
        'next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


@require_POST
def update_cart(request, product_id):
    qty = int(request.POST.get('quantity', 0))
    product = get_object_or_404(Product, pk=product_id)

    if request.user.is_authenticated:
        set_user_cart_item_quantity(request.user, product, qty)
    else:
        cart = _get_cart(request)
        pid = str(product_id)
        if qty > 0:
            cart[pid] = {'quantity': qty}
        else:
            cart.pop(pid, None)
        request.session.modified = True

    return redirect('cart:cart_detail')


def remove_from_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.user.is_authenticated:
        remove_product_from_user_cart(request.user, product)
    else:
        cart = _get_cart(request)
        cart.pop(str(product_id), None)
        request.session.modified = True

    return redirect('cart:cart_detail')


def clear_cart(request):
    if request.user.is_authenticated:
        clear_user_cart(request.user)
    clear_session_cart(request.session)
    return redirect('cart:cart_detail')
