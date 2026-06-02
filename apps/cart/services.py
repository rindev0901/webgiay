from decimal import Decimal

from django.apps import apps
from django.db import transaction

from .models import Cart, CartItem, Order, OrderItem

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


def create_order_from_cart(user, session, customer_info=None, voucher=None):
    cart_items = []

    if user and user.is_authenticated:
        cart_items = list(get_user_cart_items(user))
    else:
        session_cart = get_session_cart(session)
        if not session_cart:
            return None

        product_ids = [int(product_id) for product_id in session_cart.keys()]
        products = Product.objects.filter(id__in=product_ids).select_related('brand', 'category')
        product_map = {str(product.pk): product for product in products}

        for product_id, payload in session_cart.items():
            product = product_map.get(str(product_id))
            if not product:
                continue

            quantity = int(payload.get('quantity', 0))
            if quantity <= 0:
                continue

            cart_items.append({
                'product': product,
                'quantity': quantity,
                'price': getattr(product, 'discount_price', None) or product.final_price,
            })

    if not cart_items:
        return None

    with transaction.atomic():
        # Tính tổng trước khi giảm
        subtotal = Decimal('0')
        order_items = []
        for item in cart_items:
            product = item.product if hasattr(item, 'product') else item['product']
            quantity = item.quantity if hasattr(item, 'quantity') else item['quantity']
            price = item.price if hasattr(item, 'price') else item['price']
            subtotal += price * quantity
            order_items.append((product, quantity, price))

        # Tính discount
        discount_amount = Decimal('0')
        if voucher:
            ok, _ = voucher.is_valid(subtotal)
            if ok:
                discount_amount = voucher.calc_discount(subtotal)

        total_amount = subtotal - discount_amount

        order = Order.objects.create(
            user=user if user and user.is_authenticated else None,
            full_name=(customer_info or {}).get('full_name', ''),
            phone=(customer_info or {}).get('phone', ''),
            email=(customer_info or {}).get('email', ''),
            address=(customer_info or {}).get('address', ''),
            note=(customer_info or {}).get('note', ''),
            total_amount=total_amount,
            discount_amount=discount_amount,
            voucher=voucher,
            voucher_code=voucher.code if voucher else '',
        )

        OrderItem.objects.bulk_create([
            OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                price=price,
                quantity=quantity,
            )
            for product, quantity, price in order_items
        ])

        # Tăng used_count sau khi order được tạo thành công
        if voucher and discount_amount > 0:
            Voucher = voucher.__class__
            Voucher.objects.filter(pk=voucher.pk).update(used_count=voucher.used_count + 1)

    return order
