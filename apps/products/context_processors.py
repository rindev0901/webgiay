"""Context processors for products app"""
from .models import Category, Brand


def navigation_data(request):
    """
    Make categories and brands available to all templates
    for navigation menu in base.html
    """
    return {
        'categories': Category.objects.filter(is_active=True).order_by('name'),
        'brands': Brand.objects.filter(is_active=True).order_by('name'),
    }
