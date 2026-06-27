"""URL helpers for supply chain views."""
from .supply_admin_paths import supply_path


def supply_admin_url(name, *args, **kwargs):
    pk = args[0] if args else kwargs.get('pk')
    return supply_path(name, pk=pk)
