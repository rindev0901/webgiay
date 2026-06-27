"""
supply_views.py — Supplier-facing portal + Store Manager views.
URLs:
  /supply/                        — cửa hàng trưởng: analytics
  /supply/requests/               — danh sách đợt yêu cầu
  /supply/requests/<pk>/          — chi tiết đợt
  /supply/requests/create/        — tạo đợt mới
  /supply/requests/<pk>/export/   — tải CSV mẫu
  /supply/requests/<pk>/receive/  — nhận hàng vào kho
  /supply/portal/                 — NCC: hộp thư nhận yêu cầu
  /supply/portal/<pr_pk>/quote/   — NCC nộp báo giá
"""
import csv
import io
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .supply_models import (
    Supplier, PurchaseRequest, PurchaseRequestItem,
    SupplierQuote, SupplierQuoteItem,
)
from .models import ProductVariant
from .supply_permissions import is_store_manager
from .supply_urls_admin import supply_admin_url
from .supply_pagination import paginate_list, paginate_queryset, smart_page_range
from .inventory import adjust_stock


def _suggested_qty(stock, sold=0):
    """Gợi ý SL đặt mua: ưu tiên bù tồn thấp + bán chạy."""
    if stock <= 0:
        return max(10, sold // 2 or 10)
    if stock <= 5:
        return max(10 - stock, 5)
    return max(1, 10 - stock)


def _build_csv_response(pr):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{pr.code}_yeu_cau.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Ma SP', 'Ten san pham', 'Kich thuoc (Size)', 'Mau sac',
        'SKU', 'Ton kho hien tai', 'So luong yeu cau',
        'Don gia bao (NCC dien)', 'So luong NCC con', 'So ngay giao hang', 'Ghi chu'
    ])
    for item in pr.items.select_related(
        'variant', 'variant__product', 'variant__size', 'variant__color'
    ):
        v = item.variant
        writer.writerow([
            v.pk,
            v.product.name,
            v.size.name if v.size else '',
            v.color.name if v.color else 'Mac dinh',
            v.sku,
            item.current_stock,
            item.requested_qty,
            '', '', '', '',
        ])
    return response


def _quote_summary(quotes, request_items):
    """Tổng giá từng NCC để so sánh."""
    qty_map = {i.variant_id: i.requested_qty for i in request_items}
    summaries = []
    for q in quotes:
        total = 0
        covered = 0
        for qi in q.items.all():
            req = qty_map.get(qi.variant_id, 0)
            if req and qi.unit_price:
                total += int(qi.unit_price) * req
                covered += 1
        summaries.append({
            'quote': q,
            'supplier': q.supplier,
            'total': total,
            'covered': covered,
            'item_count': q.items.count(),
        })
    summaries.sort(key=lambda s: (s['total'] or 10**18, -s['covered']))
    return summaries


def _cheapest_supplier(quotes, request_items):
    summaries = _quote_summary(quotes, request_items)
    return summaries[0]['supplier'] if summaries and summaries[0]['total'] else None


def _get_supplier_for_user(user):
    """Return Supplier linked to this user account, or None."""
    return Supplier.objects.filter(user=user, is_active=True).first()


def _querystring(request, exclude=('page',)):
    q = request.GET.copy()
    for key in exclude:
        q.pop(key, None)
    return q.urlencode()


def _pagination_context(request, page_obj, paginator):
    return {
        'page_obj': page_obj,
        'page_range': smart_page_range(page_obj, paginator),
        'querystring': _querystring(request),
    }


# ═══════════════════════════════════════════════════════════
#  STORE MANAGER — Analytics & Purchase Requests
# ═══════════════════════════════════════════════════════════

@login_required
def analytics_view(request):
    """Biên độ tồn kho: bán chạy / ế / sắp hết + tạo đợt yêu cầu."""
    if not is_store_manager(request.user):
        messages.error(request, 'Bạn không có quyền truy cập.')
        return redirect('admin:index')

    from apps.cart.models import OrderItem

    days          = int(request.GET.get('days', 30))
    low_threshold = int(request.GET.get('low', 5))
    tag_filter    = request.GET.get('tag', '')
    per_page      = int(request.GET.get('per_page', 25))
    since         = timezone.now() - timedelta(days=days)

    sales_qs = (
        OrderItem.objects
        .filter(order__payment_status='paid', order__created_at__gte=since)
        .values('variant_id')
        .annotate(sold=Sum('quantity'))
    )
    sales_map = {r['variant_id']: r['sold'] for r in sales_qs if r['variant_id']}

    variants = (
        ProductVariant.objects
        .filter(is_active=True)
        .select_related('product', 'product__brand', 'size', 'color')
        .order_by('product__name', 'size__order')
    )

    rows = []
    for v in variants:
        sold = sales_map.get(v.pk, 0)
        tag  = 'hot' if sold >= 10 else ('slow' if sold == 0 else 'normal')
        rows.append({
            'variant': v,
            'product': v.product.name,
            'brand':   v.product.brand.name if v.product.brand else '',
            'size':    v.size.name if v.size else '',
            'color':   v.color.name if v.color else 'Mặc định',
            'stock':   v.stock,
            'sold':    sold,
            'tag':     tag,
            'low':     v.stock <= low_threshold,
            'suggest_qty': _suggested_qty(v.stock, sold),
        })

    rows.sort(key=lambda r: (-r['sold'], r['stock']))

    hot_count  = sum(1 for r in rows if r['tag'] == 'hot')
    slow_count = sum(1 for r in rows if r['tag'] == 'slow')
    low_count  = sum(1 for r in rows if r['low'])
    total_all  = len(rows)

    if tag_filter == 'hot':
        rows = [r for r in rows if r['tag'] == 'hot']
    elif tag_filter == 'slow':
        rows = [r for r in rows if r['tag'] == 'slow']
    elif tag_filter == 'low':
        rows = [r for r in rows if r['low']]

    page_obj, paginator = paginate_list(request, rows, per_page=per_page)

    context = {
        'rows':          page_obj.object_list,
        'page_obj':      page_obj,
        'page_range':    smart_page_range(page_obj, paginator),
        'querystring':   _querystring(request),
        'days':          days,
        'low_threshold': low_threshold,
        'tag_filter':    tag_filter,
        'per_page':      per_page,
        'hot_count':     hot_count,
        'slow_count':    slow_count,
        'low_count':     low_count,
        'total':         total_all,
        'suppliers':     Supplier.objects.filter(is_active=True),
    }
    return render(request, 'supply/analytics.html', context)


@login_required
def request_list(request):
    """Danh sách các đợt yêu cầu đặt hàng."""
    if not is_store_manager(request.user):
        return redirect('admin:index')

    qs = PurchaseRequest.objects.prefetch_related('items', 'suppliers').order_by('-created_at')
    page_obj, paginator = paginate_queryset(request, qs, per_page=15)
    context = {'requests': page_obj.object_list}
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, 'supply/request_list.html', context)


@login_required
def request_detail(request, pk):
    """Chi tiết 1 đợt yêu cầu."""
    if not is_store_manager(request.user):
        return redirect('admin:index')

    pr    = get_object_or_404(
        PurchaseRequest.objects.prefetch_related('suppliers'), pk=pk
    )
    items_qs = pr.items.select_related('variant', 'variant__product', 'variant__size', 'variant__color')
    items_page, items_paginator = paginate_queryset(request, items_qs, per_page=20, page_param='items_page')
    quotes = pr.quotes.select_related('supplier').prefetch_related('items')

    # Best price per variant (cheapest across all NCC quotes)
    best_price = {}
    for q in quotes:
        for qi in q.items.all():
            vid = qi.variant_id
            if vid not in best_price or qi.unit_price < best_price[vid]['price']:
                best_price[vid] = {'price': qi.unit_price, 'supplier': q.supplier}

    quote_summaries = _quote_summary(quotes, items_qs)
    recommended = _cheapest_supplier(quotes, items_qs)

    context = {
        'pr':              pr,
        'items':           items_page.object_list,
        'items_page':      items_page,
        'items_page_range': smart_page_range(items_page, items_paginator),
        'items_querystring': _querystring(request, exclude=('items_page',)),
        'quotes':          quotes,
        'best_price':      best_price,
        'quote_summaries': quote_summaries,
        'recommended':     recommended,
        'suppliers':       Supplier.objects.filter(is_active=True),
    }
    return render(request, 'supply/request_detail.html', context)


@login_required
def request_create(request):
    """Tạo đợt yêu cầu mới từ danh sách variant đã chọn."""
    if not is_store_manager(request.user):
        return redirect('admin:index')

    if request.method == 'POST':
        title      = request.POST.get('title', 'Đợt thu mua bổ sung tồn kho')
        note       = request.POST.get('note', '')
        deadline   = request.POST.get('deadline') or None
        variant_ids = request.POST.getlist('variant_ids')
        supplier_ids = request.POST.getlist('supplier_ids')

        pr = PurchaseRequest.objects.create(
            title=title, note=note, deadline=deadline,
            status=PurchaseRequest.Status.DRAFT,
            created_by=request.user,
        )
        if supplier_ids:
            pr.suppliers.set(Supplier.objects.filter(pk__in=supplier_ids))

        for vid in variant_ids:
            v = ProductVariant.objects.filter(pk=vid, is_active=True).first()
            if v:
                raw = request.POST.get(f'qty_{vid}')
                if raw is not None:
                    try:
                        qty = int(raw)
                    except (ValueError, TypeError):
                        qty = _suggested_qty(v.stock)
                else:
                    qty = _suggested_qty(v.stock)
                PurchaseRequestItem.objects.create(
                    request=pr, variant=v,
                    current_stock=v.stock,
                    requested_qty=max(1, qty),
                )

        # Mark sent if suppliers selected
        if supplier_ids:
            pr.status = PurchaseRequest.Status.SENT
            pr.save(update_fields=['status'])
            messages.success(request, f'Đã tạo và gửi đợt yêu cầu {pr.code} cho {len(supplier_ids)} NCC!')
        else:
            messages.success(request, f'Đã tạo đợt yêu cầu {pr.code} (bản nháp).')

        return redirect(supply_admin_url('request_detail', pr.pk))

    # Pre-populate from analytics selection
    variant_ids = request.GET.get('variants', '').split(',')
    variants = list(ProductVariant.objects.filter(
        pk__in=[v for v in variant_ids if v.strip().isdigit()],
        is_active=True
    ).select_related('product', 'size', 'color'))
    for v in variants:
        v.suggested_qty = _suggested_qty(v.stock)

    page_obj, paginator = paginate_list(request, variants, per_page=20)

    context = {
        'variants':     page_obj.object_list,
        'all_variants': variants,
        'suppliers':    Supplier.objects.filter(is_active=True),
    }
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, 'supply/request_create.html', context)


@login_required
def export_csv(request, pk):
    """Tải file CSV mẫu gửi NCC."""
    if not is_store_manager(request.user):
        return redirect('admin:index')

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    response = _build_csv_response(pr)

    if pr.status == PurchaseRequest.Status.DRAFT:
        pr.status = PurchaseRequest.Status.SENT
        pr.save(update_fields=['status', 'updated_at'])

    return response


@login_required
def supplier_export_csv(request, pr_pk):
    """NCC tải CSV mẫu của đợt được gửi."""
    supplier = _get_supplier_for_user(request.user)
    if not supplier:
        return redirect('admin:index')
    pr = get_object_or_404(PurchaseRequest, pk=pr_pk, suppliers=supplier)
    return _build_csv_response(pr)


@login_required
@require_POST
def send_to_suppliers(request, pk):
    """Gửi đợt nháp đến các NCC đã chọn."""
    if not is_store_manager(request.user):
        return redirect('admin:index')

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    supplier_ids = request.POST.getlist('supplier_ids')
    if supplier_ids:
        pr.suppliers.set(Supplier.objects.filter(pk__in=supplier_ids, is_active=True))
        if pr.status == PurchaseRequest.Status.DRAFT:
            pr.status = PurchaseRequest.Status.SENT
            pr.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Đã gửi đợt {pr.code} cho {len(supplier_ids)} NCC.')
    else:
        messages.error(request, 'Vui lòng chọn ít nhất 1 nhà cung cấp.')
    return redirect(supply_admin_url('request_detail', pk))


@login_required
def approve_request(request, pk):
    """Cửa hàng trưởng duyệt NCC rẻ nhất."""
    if not is_store_manager(request.user):
        return redirect('admin:index')

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')
        if supplier_id == 'auto':
            items = pr.items.all()
            quotes = pr.quotes.prefetch_related('items')
            supplier = _cheapest_supplier(quotes, items)
            if not supplier:
                messages.error(request, 'Chưa có báo giá hợp lệ để tự chọn.')
                return redirect(supply_admin_url('request_detail', pk))
        else:
            supplier = get_object_or_404(Supplier, pk=supplier_id)
        pr.approved_supplier = supplier
        pr.approved_by = request.user
        pr.approved_at = timezone.now()
        pr.status = PurchaseRequest.Status.APPROVED
        pr.save(update_fields=['approved_supplier', 'approved_by', 'approved_at', 'status', 'updated_at'])
        messages.success(request, f'Đã duyệt NCC "{supplier.name}" cho đợt {pr.code}.')
    return redirect(supply_admin_url('request_detail', pk))


@login_required
def receive_goods(request, pk):
    """Kho nhận hàng: nhập số lượng thực nhận → cộng tồn kho."""
    if not is_store_manager(request.user):
        return redirect('admin:index')

    pr    = get_object_or_404(PurchaseRequest, pk=pk, status=PurchaseRequest.Status.APPROVED)
    items_qs = pr.items.select_related('variant', 'variant__product', 'variant__size', 'variant__color')

    if request.method == 'POST':
        count = 0
        for item in items_qs:
            key = f'received_{item.pk}'
            if key not in request.POST:
                continue
            try:
                qty = int(request.POST.get(key, 0))
            except (ValueError, TypeError):
                qty = 0
            if qty > 0:
                item.received_qty = qty
                item.save(update_fields=['received_qty'])
                adjust_stock(
                    variant=item.variant,
                    quantity=qty,
                    note=f'Nhập hàng từ đợt {pr.code}',
                    actor=str(request.user),
                )
                count += 1

        pr.status = PurchaseRequest.Status.RECEIVED
        pr.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'Đã nhập kho {count} mặt hàng từ đợt {pr.code}!')
        return redirect(supply_admin_url('request_detail', pk))

    items_page, items_paginator = paginate_queryset(request, items_qs, per_page=20)
    context = {
        'pr': pr,
        'items': items_page.object_list,
        'items_page': items_page,
        'items_page_range': smart_page_range(items_page, items_paginator),
        'items_querystring': _querystring(request),
    }
    return render(request, 'supply/receive_goods.html', context)


# ═══════════════════════════════════════════════════════════
#  SUPPLIER PORTAL — NCC views
# ═══════════════════════════════════════════════════════════

@login_required
def supplier_portal(request):
    """NCC: hộp thư — danh sách đợt yêu cầu gửi đến mình."""
    supplier = _get_supplier_for_user(request.user)
    if not supplier:
        messages.error(request, 'Tài khoản của bạn chưa được liên kết với nhà cung cấp.')
        return redirect('admin:index')

    requests_qs = PurchaseRequest.objects.filter(
        suppliers=supplier,
        status__in=[PurchaseRequest.Status.SENT, PurchaseRequest.Status.QUOTED,
                    PurchaseRequest.Status.APPROVED, PurchaseRequest.Status.RECEIVED]
    ).prefetch_related('items').order_by('-created_at')

    page_obj, paginator = paginate_queryset(request, requests_qs, per_page=12)

    submitted = set(SupplierQuote.objects.filter(
        supplier=supplier,
        request_id__in=[r.pk for r in page_obj.object_list],
    ).values_list('request_id', flat=True))

    context = {
        'supplier':  supplier,
        'requests':  page_obj.object_list,
        'submitted': submitted,
    }
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, 'supply/supplier_portal.html', context)


@login_required
def submit_quote(request, pr_pk):
    """NCC nộp hồ sơ báo giá (upload CSV)."""
    supplier = _get_supplier_for_user(request.user)
    if not supplier:
        return redirect('admin:index')

    pr = get_object_or_404(PurchaseRequest, pk=pr_pk, suppliers=supplier)

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        note     = request.POST.get('note', '')

        if not csv_file:
            messages.error(request, 'Vui lòng chọn file CSV.')
        else:
            quote, _ = SupplierQuote.objects.update_or_create(
                request=pr, supplier=supplier,
                defaults={'note': note, 'csv_file': csv_file},
            )
            # Parse CSV → create SupplierQuoteItem rows
            try:
                content = csv_file.read().decode('utf-8-sig')
                reader  = csv.DictReader(io.StringIO(content))
                quote.items.all().delete()
                errors = []
                for row in reader:
                    try:
                        vid        = int(row.get('Ma SP', 0))
                        unit_price = float(str(row.get('Don gia bao (NCC dien)', '0')).replace(',', '').replace('.', '') or 0)
                        avail_qty  = int(row.get('So luong NCC con', 0) or 0)
                        lead_days  = int(row.get('So ngay giao hang', 3) or 3)
                        v = ProductVariant.objects.filter(pk=vid).first()
                        if v and unit_price > 0:
                            SupplierQuoteItem.objects.create(
                                quote=quote, variant=v,
                                unit_price=int(unit_price),
                                available_qty=avail_qty,
                                lead_days=lead_days,
                            )
                    except (ValueError, TypeError):
                        errors.append(str(row))
                        continue

                # Update request status
                if pr.status == PurchaseRequest.Status.SENT:
                    pr.status = PurchaseRequest.Status.QUOTED
                    pr.save(update_fields=['status', 'updated_at'])

                if errors:
                    messages.warning(request, f'Đã nộp báo giá. {len(errors)} dòng lỗi bị bỏ qua.')
                else:
                    messages.success(request, 'Nộp hồ sơ báo giá thành công!')
            except Exception as e:
                messages.error(request, f'Lỗi đọc file CSV: {e}')

        return redirect(supply_admin_url('bao_gia'))

    items_qs = pr.items.select_related('variant', 'variant__product', 'variant__size', 'variant__color')
    items_page, items_paginator = paginate_queryset(request, items_qs, per_page=20)

    context = {
        'pr': pr,
        'supplier': supplier,
        'items': items_page.object_list,
        'items_page': items_page,
        'items_page_range': smart_page_range(items_page, items_paginator),
        'items_querystring': _querystring(request),
    }
    return render(request, 'supply/submit_quote.html', context)
