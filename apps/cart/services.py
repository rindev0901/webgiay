from decimal import Decimal

from django.apps import apps
from django.db import transaction

from .models import Cart, CartItem

SESSION_KEY = 'cart'
Product = apps.get_model('products', 'Product')


def get_session_cart(session):
    return session.get(SESSION_KEY, {}) or {}


def set_session_cart(session, cart_data):
    session[SESSION_KEY] = cart_data
    session.modified = True


def clear_session_cart(session):
    session.pop(SESSION_KEY, None)
    session.modified = True


def get_or_create_user_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def get_user_cart_item_count(user):
    cart = Cart.objects.filter(user=user).first()
    if not cart:
        return 0
    return sum(item.quantity for item in cart.items.all())


def get_user_cart_items(user):
    cart = Cart.objects.get_or_create(user=user)[0]
    return cart.items.select_related('product', 'product__brand', 'product__category').prefetch_related('product__images')


def add_product_to_user_cart(user, product, quantity):
    cart = get_or_create_user_cart(user)
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={
            'quantity': quantity,
            'price': product.final_price,
        },
    )
    if not created:
        item.quantity += quantity
        item.price = product.final_price
        item.save(update_fields=['quantity', 'price', 'updated_at'])
    return item


def set_user_cart_item_quantity(user, product, quantity):
    cart = get_or_create_user_cart(user)
    if quantity > 0:
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={
                'quantity': quantity,
                'price': product.final_price,
            },
        )
        if not created:
            item.quantity = quantity
            item.price = product.final_price
            item.save(update_fields=['quantity', 'price', 'updated_at'])
        return item

    CartItem.objects.filter(cart=cart, product=product).delete()
    return None


def remove_product_from_user_cart(user, product):
    cart = Cart.objects.filter(user=user).first()
    if cart:
        CartItem.objects.filter(cart=cart, product=product).delete()


def clear_user_cart(user):
    cart = Cart.objects.filter(user=user).first()
    if cart:
        cart.items.all().delete()


def merge_session_cart_into_user_cart(user, session):
    session_cart = get_session_cart(session)
    if not session_cart:
        return 0

    merged_quantity = 0
    cart = get_or_create_user_cart(user)

    with transaction.atomic():
        for product_id, payload in session_cart.items():
            quantity = int(payload.get('quantity', 0))
            if quantity <= 0:
                continue

            product = Product.objects.filter(pk=product_id).first()
            if not product:
                continue

            item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={
                    'quantity': quantity,
                    'price': product.final_price,
                },
            )
            if not created:
                item.quantity += quantity
                item.price = product.final_price
                item.save(update_fields=['quantity', 'price', 'updated_at'])

            merged_quantity += quantity

        clear_session_cart(session)

    return merged_quantity
