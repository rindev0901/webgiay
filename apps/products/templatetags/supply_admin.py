from django import template

from apps.products.supply_admin_paths import supply_path

register = template.Library()


@register.simple_tag
def supply_url(name, arg=None):
    return supply_path(name, pk=arg)
