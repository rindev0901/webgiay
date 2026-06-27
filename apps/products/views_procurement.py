"""
views_procurement.py — Toàn bộ nghiệp vụ nhập hàng.

Luồng:
    stock_dashboard → purchase_request_create → purchase_request_list
    → purchase_request_detail → submit_quote → quote_inbox
    → compare_quotes → receive_goods
"""
from __future__ import annotations

import csv
import io
from decimal import Decimal, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q
from django.http import HttpResponse, HttpRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    ProductVariant,
    StockMovement,
    PurchaseRequest,
    PurchaseRequestItem,
    Supplier,
    QuoteSubmission,
    QuoteSubmissionItem,
)
from .inventory import adjust_stock


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
LOW_STOCK_THRESHOLD = 5      # ≤ 5 = sắp hết
HOT_SELL_THRESHOLD  = 10     # ≥ 10 sold / 30 ngày = bán chạy
SLOW_SELL_THRESHOLD = 2      # ≤ 2 sold / 30 ngày + stock cao = bán ế


def _sold_last_30(variant_ids: list[int]) -> dict[int, int]:
    """Trả về {variant_id: số_lượng_đã_bán_30_ngày}"""
    since = timezone.now() - timezone.timedelta(days=30)
    rows = (
        StockMovement.objects
        .filter(variant_id__in=variant_ids, movement_type='out', created_at__gte=since)
        .values('variant_id')
        .annotate(sold=Sum('quantity'))
    )
    return {r['variant_id']: abs(r['sold'] or 0) for r in rows}


def _classify(stock: int, sold_30: int) -> str:
    """Phân loại biến thể: hot / slow / low / out / normal"""
    if stock == 0:
        return 'out'
    if stock <= LOW_STOCK_THRESHOLD:
        return 'low'
    if sold_30 >= HOT_SELL_THRESHOLD:
        return 'hot'
    if sold_30 <= SLOW_SELL_THRESHOLD and stock >= 10:
        return 'slow'
    return 'normal'


# ─────────────────────────────────────────────────────────
# 1. Dashboard Biên Độ Tồn Kho
# ─────────────────────────────────────────────────────────
@staff_member_required
def stock_dashboard(request: HttpRequest):
    """Bảng tồn kho với biên độ màu sắc + checkbox chọn để tạo đơn."""
    # Filter params
    status_filter = request.GET.get('status', '')
    brand_filter  = request.GET.get('brand', '')
    search_q      = request.GET.get('q', '')

    variants = (
        ProductVariant.objects
        .filter(is_active=True)
        .select_related('product', 'product__brand', 'size', 'color')
        .order_by('product__brand__name', 'product__name', 'size__order')
    )

    if brand_filter:
        variants = variants.filter(product__brand__id=brand_filter)
    if search_q:
        variants = variants.filter(
            Q(product__name__icontains=search_q) |
            Q(sku__icontains=search_q)
        )

    variant_ids = list(variants.values_list('id', flat=True))
    sold_map    = _sold_last_30(variant_ids)

    rows = []
    for v in variants:
        sold = sold_map.get(v.id, 0)
        cls  = _classify(v.stock, sold)
        rows.append({
            'variant': v,
            'sold_30': sold,
            'class':   cls,
        })

    # Filter theo status sau khi classify
    if status_filter:
        rows = [r for r in rows if r['class'] == status_filter]

    # Summary counts
    counts = {'hot': 0, 'slow': 0, 'low': 0, 'out': 0, 'normal': 0}
    for r in rows:
        counts[r['class']] += 1

    from .models import Brand
    brands = Brand.objects.filter(is_active=True)

    context = {
        'rows':          rows,
        'counts':        counts,
        'brands':        brands,
        'status_filter': status_filter,
        'brand_filter':  brand_filter,
        'search_q':      search_q,
        'title':         'Biên Độ Tồn Kho',
    }
    return render(request, 'admin/products/stock_dashboard.html', context)


# ─────────────────────────────────────────────────────────
# 2. Tạo đơn yêu cầu mua hàng
# ─────────────────────────────────────────────────────────
@staff_member_required
def purchase_request_create(request: HttpRequest):
    """Nhận danh sách variant_ids từ POST (dashboard), tạo PurchaseRequest."""
    if request.method == 'POST' and 'variant_ids' in request.POST:
        # Bước 1: Hiển thị form chỉnh số lượng
        raw_ids = request.POST.getlist('variant_ids')
        try:
            variant_ids = [int(i) for i in raw_ids if i]
        except ValueError:
            messages.error(request, 'Dữ liệu không hợp lệ.')
            return redirect('products:stock_dashboard')

        if not variant_ids:
            messages.warning(request, 'Vui lòng chọn ít nhất một sản phẩm.')
            return redirect('products:stock_dashboard')

        variants = (
            ProductVariant.objects
            .filter(id__in=variant_ids, is_active=True)
            .select_related('product', 'product__brand', 'size', 'color')
        )
        context = {
            'variants': variants,
            'title':    'Tạo Đơn Yêu Cầu Mua Hàng',
        }
        return render(request, 'admin/products/purchase_request_create.html', context)

    elif request.method == 'POST' and 'confirm_create' in request.POST:
        # Bước 2: Lưu đơn
        note = request.POST.get('note', '').strip()
        raw_items = {}
        for key, val in request.POST.items():
            if key.startswith('qty_'):
                try:
                    vid = int(key[4:])
                    qty = int(val)
                    if qty > 0:
                        raw_items[vid] = qty
                except (ValueError, TypeError):
                    continue

        if not raw_items:
            messages.error(request, 'Vui lòng nhập số lượng cần nhập cho ít nhất một sản phẩm.')
            # Re-render with previously selected variants
            raw_ids = request.POST.getlist('variant_ids')
            variants = ProductVariant.objects.filter(
                id__in=[int(i) for i in raw_ids if i], is_active=True
            ).select_related('product', 'product__brand', 'size', 'color')
            return render(request, 'admin/products/purchase_request_create.html', {
                'variants': variants, 'title': 'Tạo Đơn Yêu Cầu Mua Hàng',
            })

        with transaction.atomic():
            pr = PurchaseRequest.objects.create(
                note=note,
                created_by=request.user,
                status=PurchaseRequest.Status.DRAFT,
            )
            variants_qs = ProductVariant.objects.filter(id__in=list(raw_items.keys()))
            for v in variants_qs:
                PurchaseRequestItem.objects.create(
                    request=pr,
                    variant=v,
                    qty_requested=raw_items[v.id],
                )

        messages.success(request, f'Đã tạo đợt mua hàng {pr.code}!')
        return redirect('products:purchase_request_detail', pk=pr.pk)

    return redirect('products:stock_dashboard')


# ─────────────────────────────────────────────────────────
# 3. Danh sách đợt mua hàng
# ─────────────────────────────────────────────────────────
@staff_member_required
def purchase_request_list(request: HttpRequest):
    requests_qs = PurchaseRequest.objects.all().prefetch_related('items', 'quotes')
    context = {
        'purchase_requests': requests_qs,
        'title': 'Danh Sách Đợt Mua Hàng',
    }
    return render(request, 'admin/products/purchase_request_list.html', context)


# ─────────────────────────────────────────────────────────
# 4. Chi tiết đợt mua hàng
# ─────────────────────────────────────────────────────────
@staff_member_required
def purchase_request_detail(request: HttpRequest, pk: int):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    items = pr.items.select_related(
        'variant', 'variant__product', 'variant__product__brand',
        'variant__size', 'variant__color'
    )
    quotes = pr.quotes.select_related('supplier')
    context = {
        'pr':     pr,
        'items':  items,
        'quotes': quotes,
        'title':  f'Chi tiết Đợt {pr.code}',
    }
    return render(request, 'admin/products/purchase_request_detail.html', context)


# ─────────────────────────────────────────────────────────
# 5. Download CSV mẫu
# ─────────────────────────────────────────────────────────
@staff_member_required
def download_csv_template(request: HttpRequest, pk: int):
    """Xuất file CSV gửi cho NCC với danh sách sản phẩm cần báo giá."""
    pr    = get_object_or_404(PurchaseRequest, pk=pk)
    items = pr.items.select_related(
        'variant', 'variant__product', 'variant__size', 'variant__color'
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="don-mua-{pr.code}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Mã SP (SKU)', 'Tên sản phẩm', 'Kích thước (Size)', 'Màu sắc',
        'Số lượng yêu cầu', 'Đơn giá báo (để trống)', 'Kho còn (để trống)'
    ])
    for item in items:
        v = item.variant
        writer.writerow([
            v.sku,
            v.product.name,
            v.size.name if v.size else '',
            v.color.name if v.color else 'Mặc định',
            item.qty_requested,
            '',  # NCC điền giá
            '',  # NCC điền kho
        ])

    # Đánh dấu đã gửi NCC
    if pr.status == PurchaseRequest.Status.DRAFT:
        pr.status = PurchaseRequest.Status.SENT
        pr.save(update_fields=['status'])

    return response


# ─────────────────────────────────────────────────────────
# 6. Hộp thư báo giá (NCC nộp)
# ─────────────────────────────────────────────────────────
@staff_member_required
def quote_inbox(request: HttpRequest):
    """Danh sách các đợt mua hàng đang chờ báo giá."""
    pending_requests = PurchaseRequest.objects.filter(
        status__in=[
            PurchaseRequest.Status.SENT,
            PurchaseRequest.Status.QUOTED,
        ]
    ).prefetch_related('items', 'quotes__supplier').order_by('-created_at')

    context = {
        'pending_requests': pending_requests,
        'title': 'Hộp Thư Yêu Cầu Báo Giá',
    }
    return render(request, 'admin/products/quote_inbox.html', context)


# ─────────────────────────────────────────────────────────
# 7. Nộp hồ sơ báo giá
# ─────────────────────────────────────────────────────────
@staff_member_required
def submit_quote(request: HttpRequest, pk: int):
    """NCC (hoặc admin thay NCC) nộp file báo giá CSV."""
    pr      = get_object_or_404(PurchaseRequest, pk=pk)
    items   = pr.items.select_related('variant', 'variant__product', 'variant__size', 'variant__color')
    suppliers = Supplier.objects.filter(is_active=True)

    if request.method == 'POST':
        supplier_id = request.POST.get('supplier')
        note        = request.POST.get('note', '').strip()
        csv_file    = request.FILES.get('csv_file')

        if not supplier_id:
            messages.error(request, 'Vui lòng chọn nhà cung cấp.')
        elif not csv_file:
            messages.error(request, 'Vui lòng tải lên file CSV báo giá.')
        else:
            try:
                supplier = Supplier.objects.get(pk=supplier_id)
            except Supplier.DoesNotExist:
                messages.error(request, 'Nhà cung cấp không tồn tại.')
                return render(request, 'admin/products/submit_quote.html', {
                    'pr': pr, 'items': items, 'suppliers': suppliers, 'title': 'Nộp Hồ Sơ Báo Giá',
                })

            with transaction.atomic():
                qs_obj, _ = QuoteSubmission.objects.get_or_create(
                    request=pr,
                    supplier=supplier,
                    defaults={
                        'status':       QuoteSubmission.Status.PENDING,
                        'note':         note,
                        'csv_file':     csv_file,
                        'submitted_at': timezone.now(),
                    }
                )
                # Update nếu đã tồn tại
                qs_obj.note         = note
                qs_obj.csv_file     = csv_file
                qs_obj.submitted_at = timezone.now()
                qs_obj.status       = QuoteSubmission.Status.SUBMITTED
                qs_obj.save()

                # Parse CSV để lưu QuoteSubmissionItem
                csv_file.seek(0)
                decoded = csv_file.read().decode('utf-8-sig')
                reader  = csv.DictReader(io.StringIO(decoded))

                qs_obj.quote_items.all().delete()  # reset cũ
                sku_map = {item.variant.sku: item.variant for item in items}

                for row in reader:
                    sku       = (row.get('Mã SP (SKU)') or '').strip()
                    price_raw = (row.get('Đơn giá báo (để trống)') or '0').strip()
                    qty_raw   = (row.get('Kho còn (để trống)') or '0').strip()
                    variant   = sku_map.get(sku)
                    if not variant:
                        continue
                    try:
                        unit_price    = Decimal(price_raw) if price_raw else Decimal('0')
                        qty_available = int(qty_raw) if qty_raw else 0
                    except (InvalidOperation, ValueError):
                        unit_price, qty_available = Decimal('0'), 0

                    QuoteSubmissionItem.objects.create(
                        submission=qs_obj,
                        variant=variant,
                        unit_price=unit_price,
                        qty_available=qty_available,
                    )

                # Cập nhật trạng thái PR sang quoted
                if pr.status == PurchaseRequest.Status.SENT:
                    pr.status = PurchaseRequest.Status.QUOTED
                    pr.save(update_fields=['status'])

            messages.success(request, f'Đã nộp báo giá từ {supplier.name} thành công!')
            return redirect('products:purchase_request_detail', pk=pr.pk)

    context = {
        'pr':        pr,
        'items':     items,
        'suppliers': suppliers,
        'title':     'Nộp Hồ Sơ Báo Giá',
    }
    return render(request, 'admin/products/submit_quote.html', context)


# ─────────────────────────────────────────────────────────
# 8. So sánh báo giá & duyệt
# ─────────────────────────────────────────────────────────
@staff_member_required
def compare_quotes(request: HttpRequest, pk: int):
    """So sánh giá từ các NCC, highlight NCC rẻ nhất, cho phép duyệt."""
    pr     = get_object_or_404(PurchaseRequest, pk=pk)
    quotes = pr.quotes.filter(status=QuoteSubmission.Status.SUBMITTED).select_related('supplier')
    items  = pr.items.select_related('variant', 'variant__product', 'variant__size', 'variant__color')

    # POST: duyệt NCC
    if request.method == 'POST':
        approved_quote_id = request.POST.get('approve_quote')
        if approved_quote_id:
            with transaction.atomic():
                approved = get_object_or_404(QuoteSubmission, pk=approved_quote_id, request=pr)
                # Reject các cái khác
                pr.quotes.exclude(pk=approved.pk).update(status=QuoteSubmission.Status.REJECTED)
                approved.status      = QuoteSubmission.Status.APPROVED
                approved.approved_by = request.user
                approved.approved_at = timezone.now()
                approved.save()

                pr.status      = PurchaseRequest.Status.APPROVED
                pr.approved_by = request.user
                pr.approved_at = timezone.now()
                pr.save(update_fields=['status', 'approved_by', 'approved_at'])

            messages.success(request, f'Đã duyệt báo giá từ {approved.supplier.name}!')
            return redirect('products:purchase_request_detail', pk=pr.pk)

    # Build comparison matrix: {variant_id: {supplier_id: QuoteSubmissionItem}}
    compare_matrix = {}   # variant → {supplier_id: item}
    min_price_map  = {}   # variant_id → min unit_price

    for q in quotes:
        for qi in q.quote_items.select_related('variant', 'variant__size', 'variant__color'):
            vid = qi.variant_id
            if vid not in compare_matrix:
                compare_matrix[vid] = {'variant': qi.variant, 'suppliers': {}}
            compare_matrix[vid]['suppliers'][q.supplier_id] = {
                'price':         qi.unit_price,
                'qty_available': qi.qty_available,
                'quote_id':      q.pk,
            }
            cur_min = min_price_map.get(vid, None)
            if cur_min is None or qi.unit_price < cur_min:
                min_price_map[vid] = qi.unit_price

    context = {
        'pr':            pr,
        'quotes':        quotes,
        'compare_matrix': list(compare_matrix.values()),
        'min_price_map': min_price_map,
        'title':         f'So Sánh Báo Giá — {pr.code}',
    }
    return render(request, 'admin/products/compare_quotes.html', context)


# ─────────────────────────────────────────────────────────
# 9. Nhận hàng & nhập kho
# ─────────────────────────────────────────────────────────
@staff_member_required
def receive_goods(request: HttpRequest, pk: int):
    """Kho nhận & kiểm hàng, điền SL thực nhận, nhập kho."""
    pr    = get_object_or_404(PurchaseRequest, pk=pk)
    items = pr.items.select_related(
        'variant', 'variant__product', 'variant__product__brand',
        'variant__size', 'variant__color'
    )

    # Lấy báo giá đã duyệt (nếu có)
    approved_quote = pr.quotes.filter(status=QuoteSubmission.Status.APPROVED).first()

    if request.method == 'POST':
        note   = request.POST.get('note', f'Nhập hàng từ đợt {pr.code}').strip()
        actor  = str(request.user)
        total_received = 0

        with transaction.atomic():
            for item in items:
                qty_key = f'qty_received_{item.id}'
                try:
                    qty = int(request.POST.get(qty_key, 0))
                except (ValueError, TypeError):
                    qty = 0

                if qty > 0:
                    adjust_stock(
                        variant=item.variant,
                        quantity=qty,
                        note=f'{note} | {pr.code}',
                        actor=actor,
                    )
                    item.qty_received = qty
                    item.save(update_fields=['qty_received'])
                    total_received += qty

            if total_received > 0:
                pr.status = PurchaseRequest.Status.DONE
                pr.save(update_fields=['status'])

        if total_received > 0:
            messages.success(request, f'Đã nhập kho {total_received} biến thể. Đợt {pr.code} hoàn thành!')
        else:
            messages.warning(request, 'Không có biến thể nào được nhập kho.')

        return redirect('products:purchase_request_detail', pk=pr.pk)

    context = {
        'pr':             pr,
        'items':          items,
        'approved_quote': approved_quote,
        'title':          f'Nhận Hàng — {pr.code}',
    }
    return render(request, 'admin/products/receive_goods.html', context)
