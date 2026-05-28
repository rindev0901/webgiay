from .services import get_session_cart, get_user_cart_item_count


def cart_count(request):
    if request.user.is_authenticated:
        total_items = get_user_cart_item_count(request.user)
    else:
        cart = get_session_cart(request.session)
        total_items = sum(int(item.get('quantity', 0)) for item in cart.values())
    return {'cart_count': total_items}
