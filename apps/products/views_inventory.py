"""Views for inventory management"""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from .models import Product, ProductVariant
from .inventory import adjust_stock


@staff_member_required
def stock_in_view(request):
    """Giao diện nhập kho hàng"""
    product_id = request.GET.get('product')
    selected_product = None
    variants = []
    
    if product_id:
        selected_product = get_object_or_404(Product, id=product_id, is_active=True)
        variants = selected_product.variants.filter(is_active=True).select_related('size', 'color').order_by('size__order', 'color__name')
    
    if request.method == 'POST':
        note = request.POST.get('note', 'Nhập kho')
        actor = str(request.user)
        success_count = 0
        
        with transaction.atomic():
            for variant in variants:
                qty_key = f'qty_{variant.id}'
                quantity = request.POST.get(qty_key, '0')
                
                try:
                    quantity = int(quantity)
                    if quantity > 0:
                        adjust_stock(
                            variant=variant,
                            quantity=quantity,
                            note=note,
                            actor=actor
                        )
                        success_count += 1
                except (ValueError, TypeError):
                    continue
        
        if success_count > 0:
            from apps.accounts.signals import create_log
            create_log(
                action="Cộng tồn kho",
                target=f"Sản phẩm: {selected_product.name}" if selected_product else "Sản phẩm",
                changes=f"Nhập kho thành công cho {success_count} biến thể | Ghi chú: {note}",
                user=request.user
            )
            messages.success(request, f'Đã nhập kho thành công {success_count} biến thể!')
            return redirect('admin:products_product_changelist')
        else:
            messages.warning(request, 'Không có biến thể nào được nhập kho.')
    
    # Get all products for dropdown
    products = Product.objects.filter(is_active=True).order_by('name')
    
    context = {
        'products': products,
        'selected_product': selected_product,
        'variants': variants,
        'title': 'Nhập kho hàng',
    }
    
    return render(request, 'admin/products/stock_in_dark.html', context)
