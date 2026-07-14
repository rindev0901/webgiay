"""
supply_views.py — Supplier-facing portal + Store Manager views.

Quy trình nhập hàng mới:
  1. CHT duyệt báo giá → tự động tạo phiếu kiểm kê
  2. Nhân viên kiểm kê → nhập số lượng thực nhận
  3. CHT duyệt phiếu kiểm kê → tự động cộng tồn kho + tạo phiếu chi tiền
  4. CHT thanh toán cho NCC

URLs:
  /supply/                        — cửa hàng trưởng: analytics
  /supply/requests/               — danh sách đợt yêu cầu
  /supply/requests/<pk>/          — chi tiết đợt
  /supply/requests/create/        — tạo đợt mới
  /supply/requests/<pk>/export/   — tải CSV mẫu
  /supply/requests/<pk>/approve/  — duyệt báo giá (tạo phiếu kiểm kê)
  /supply/inventory-checks/       — danh sách phiếu kiểm kê
  /supply/inventory-checks/<pk>/  — chi tiết phiếu kiểm kê
  /supply/inventory-checks/<pk>/perform/ — thực hiện kiểm kê
  /supply/inventory-checks/<pk>/approve/ — duyệt phiếu kiểm kê (cộng kho + tạo phiếu chi)
  /supply/payment-vouchers/       — danh sách phiếu chi tiền
  /supply/payment-vouchers/<pk>/  — chi tiết phiếu chi
  /supply/portal/                 — NCC: hộp thư nhận yêu cầu
  /supply/portal/<pr_pk>/quote/   — NCC nộp báo giá
"""

import csv
import io
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .supply_models import (
    Supplier,
    PurchaseRequest,
    PurchaseRequestItem,
    SupplierQuote,
    SupplierQuoteItem,
    InventoryCheck,
    InventoryCheckItem,
    PaymentVoucher,
)
from .models import ProductVariant
from .supply_permissions import is_store_manager, is_warehouse_manager, is_director_or_general_director
from .supply_urls_admin import supply_admin_url
from .supply_pagination import paginate_list, paginate_queryset, smart_page_range
from .inventory import adjust_stock
from apps.accounts.models import ActivityLog
from apps.cart.models import Order


def _suggested_qty(stock, sold=0):
    """Gợi ý SL đặt mua: ưu tiên bù tồn thấp + bán chạy."""
    if stock <= 0:
        return max(10, sold // 2 or 10)
    if stock <= 5:
        return max(10 - stock, 5)
    return max(1, 10 - stock)


def _build_csv_response(pr):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{pr.code}_yeu_cau.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Ma SP",
            "Ten san pham",
            "Kich thuoc (Size)",
            "Mau sac",
            "SKU",
            "Ton kho hien tai",
            "So luong yeu cau",
            "Don gia bao",
            "So luong NCC con",
            "So ngay giao hang",
            "Ghi chu",
        ]
    )
    for item in pr.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    ):
        v = item.variant
        writer.writerow(
            [
                v.pk,
                v.product.name,
                v.size.name if v.size else "",
                v.color.name if v.color else "Mac dinh",
                v.sku,
                item.current_stock,
                item.requested_qty,
                "",
                "",
                "",
                "",
            ]
        )
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
        summaries.append(
            {
                "quote": q,
                "supplier": q.supplier,
                "total": total,
                "covered": covered,
                "item_count": q.items.count(),
            }
        )
    summaries.sort(key=lambda s: (s["total"] or 10**18, -s["covered"]))
    return summaries


def _cheapest_supplier(quotes, request_items):
    summaries = _quote_summary(quotes, request_items)
    return summaries[0]["supplier"] if summaries and summaries[0]["total"] else None


def _get_supplier_for_user(user):
    """Return Supplier linked to this user account, or None."""
    return Supplier.objects.filter(user=user, is_active=True).first()


def _querystring(request, exclude=("page",)):
    q = request.GET.copy()
    for key in exclude:
        q.pop(key, None)
    return q.urlencode()


def _pagination_context(request, page_obj, paginator):
    return {
        "page_obj": page_obj,
        "page_range": smart_page_range(page_obj, paginator),
        "querystring": _querystring(request),
    }


# ═══════════════════════════════════════════════════════════
#  STORE MANAGER — Analytics & Purchase Requests
# ═══════════════════════════════════════════════════════════


@login_required
def analytics_view(request):
    """Biên độ tồn kho: bán chạy / ế / sắp hết + tạo đợt yêu cầu."""
    if not is_store_manager(request.user):
        messages.error(request, "Bạn không có quyền truy cập.")
        return redirect("admin:index")

    from apps.cart.models import OrderItem

    days = int(request.GET.get("days", 30))
    low_threshold = int(request.GET.get("low", 5))
    tag_filter = request.GET.get("tag", "")
    per_page = int(request.GET.get("per_page", 25))
    since = timezone.now() - timedelta(days=days)

    sales_qs = (
        OrderItem.objects.filter(
            order__payment_status="paid", order__created_at__gte=since
        )
        .values("variant_id")
        .annotate(sold=Sum("quantity"))
    )
    sales_map = {r["variant_id"]: r["sold"] for r in sales_qs if r["variant_id"]}

    variants = (
        ProductVariant.objects.filter(is_active=True)
        .select_related("product", "product__brand", "size", "color")
        .order_by("product__name", "size__order")
    )

    rows = []
    for v in variants:
        sold = sales_map.get(v.pk, 0)
        tag = "hot" if sold >= 10 else ("slow" if sold == 0 else "normal")
        rows.append(
            {
                "variant": v,
                "product": v.product.name,
                "brand": v.product.brand.name if v.product.brand else "",
                "size": v.size.name if v.size else "",
                "color": v.color.name if v.color else "Mặc định",
                "stock": v.stock,
                "sold": sold,
                "tag": tag,
                "low": v.stock <= low_threshold,
                "suggest_qty": _suggested_qty(v.stock, sold),
            }
        )

    rows.sort(key=lambda r: (-r["sold"], r["stock"]))

    hot_count = sum(1 for r in rows if r["tag"] == "hot")
    slow_count = sum(1 for r in rows if r["tag"] == "slow")
    low_count = sum(1 for r in rows if r["low"])
    total_all = len(rows)

    if tag_filter == "hot":
        rows = [r for r in rows if r["tag"] == "hot"]
    elif tag_filter == "slow":
        rows = [r for r in rows if r["tag"] == "slow"]
    elif tag_filter == "low":
        rows = [r for r in rows if r["low"]]

    page_obj, paginator = paginate_list(request, rows, per_page=per_page)

    context = {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "page_range": smart_page_range(page_obj, paginator),
        "querystring": _querystring(request),
        "days": days,
        "low_threshold": low_threshold,
        "tag_filter": tag_filter,
        "per_page": per_page,
        "hot_count": hot_count,
        "slow_count": slow_count,
        "low_count": low_count,
        "total": total_all,
        "suppliers": Supplier.objects.filter(is_active=True),
    }
    return render(request, "supply/analytics.html", context)


@login_required
def request_list(request):
    """Danh sách các đợt yêu cầu đặt hàng."""
    if not is_store_manager(request.user):
        return redirect("admin:index")

    qs = PurchaseRequest.objects.prefetch_related("items", "suppliers").order_by(
        "-created_at"
    )
    page_obj, paginator = paginate_queryset(request, qs, per_page=15)
    context = {"requests": page_obj.object_list}
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, "supply/request_list.html", context)


@login_required
def request_detail(request, pk):
    """Chi tiết 1 đợt yêu cầu."""
    if not is_store_manager(request.user):
        return redirect("admin:index")

    pr = get_object_or_404(PurchaseRequest.objects.prefetch_related("suppliers"), pk=pk)

    # Xử lý cộng tồn kho từ modal
    if request.method == "POST" and hasattr(pr, "inventory_check"):
        check = pr.inventory_check
        if check.status == InventoryCheck.Status.APPROVED:
            # Kiểm tra đã cộng tồn kho chưa
            if pr.items.filter(received_qty__gt=0).exists():
                messages.warning(
                    request, f"Phiếu kiểm kê {check.code} đã được cộng tồn kho rồi!"
                )
            else:
                from django.db import transaction

                with transaction.atomic():
                    for item in check.items.all():
                        if item.received_qty > 0:
                            adjust_stock(
                                variant=item.variant,
                                quantity=item.received_qty,
                                note=f"Nhập kho từ phiếu kiểm kê {check.code}",
                                actor=str(request.user),
                            )
                            # Update received_qty in PurchaseRequestItem
                            pr_item = pr.items.filter(variant=item.variant).first()
                            if pr_item:
                                pr_item.received_qty = item.received_qty
                                pr_item.save(update_fields=["received_qty"])

                    messages.success(
                        request,
                        f"✅ Đã cộng tồn kho thành công cho {check.items.count()} mặt hàng từ phiếu {check.code}!",
                    )

                    from apps.accounts.signals import create_log
                    create_log(
                        action="Cộng tồn kho",
                        target=f"Phiếu kiểm kê: {check.code}",
                        changes=f"Cộng kho thành công cho {check.items.count()} mặt hàng từ đợt {pr.code} (via Chi tiết đợt)",
                        user=request.user
                    )
            return redirect(supply_admin_url("request_detail", pk))

    items_qs = pr.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    )
    items_page, items_paginator = paginate_queryset(
        request, items_qs, per_page=20, page_param="items_page"
    )
    quotes = pr.quotes.select_related("supplier").prefetch_related("items")

    # Best price per variant (cheapest across all NCC quotes)
    best_price = {}
    for q in quotes:
        for qi in q.items.all():
            vid = qi.variant_id
            if vid not in best_price or qi.unit_price < best_price[vid]["price"]:
                best_price[vid] = {"price": qi.unit_price, "supplier": q.supplier}

    quote_summaries = _quote_summary(quotes, items_qs)
    recommended = _cheapest_supplier(quotes, items_qs)

    # Lấy thông tin phiếu kiểm kê nếu có
    inventory_check = None
    stock_added = False
    check_items = []
    if hasattr(pr, "inventory_check"):
        inventory_check = pr.inventory_check
        stock_added = pr.items.filter(received_qty__gt=0).exists()
        if inventory_check.status == InventoryCheck.Status.APPROVED and not stock_added:
            check_items = inventory_check.items.select_related(
                "variant", "variant__product", "variant__size", "variant__color"
            )

    context = {
        "pr": pr,
        "items": items_page.object_list,
        "items_page": items_page,
        "items_page_range": smart_page_range(items_page, items_paginator),
        "items_querystring": _querystring(request, exclude=("items_page",)),
        "quotes": quotes,
        "best_price": best_price,
        "quote_summaries": quote_summaries,
        "recommended": recommended,
        "suppliers": Supplier.objects.filter(is_active=True),
        "inventory_check": inventory_check,
        "stock_added": stock_added,
        "check_items": check_items,
    }
    return render(request, "supply/request_detail.html", context)


@login_required
def request_create(request):
    """Tạo đợt yêu cầu mới từ danh sách variant đã chọn."""
    if not is_store_manager(request.user):
        return redirect("admin:index")

    if request.method == "POST":
        title = request.POST.get("title", "Đợt thu mua bổ sung tồn kho")
        note = request.POST.get("note", "")
        deadline = request.POST.get("deadline") or None
        variant_ids = request.POST.getlist("variant_ids")
        supplier_ids = request.POST.getlist("supplier_ids")

        pr = PurchaseRequest.objects.create(
            title=title,
            note=note,
            deadline=deadline,
            status=PurchaseRequest.Status.DRAFT,
            created_by=request.user,
        )
        if supplier_ids:
            pr.suppliers.set(Supplier.objects.filter(pk__in=supplier_ids))

        for vid in variant_ids:
            v = ProductVariant.objects.filter(pk=vid, is_active=True).first()
            if v:
                raw = request.POST.get(f"qty_{vid}")
                if raw is not None:
                    try:
                        qty = int(raw)
                    except (ValueError, TypeError):
                        qty = _suggested_qty(v.stock)
                else:
                    qty = _suggested_qty(v.stock)
                PurchaseRequestItem.objects.create(
                    request=pr,
                    variant=v,
                    current_stock=v.stock,
                    requested_qty=max(1, qty),
                )

        # Mark sent if suppliers selected
        if supplier_ids:
            pr.status = PurchaseRequest.Status.SENT
            pr.save(update_fields=["status"])
            messages.success(
                request,
                f"Đã tạo và gửi đợt yêu cầu {pr.code} cho {len(supplier_ids)} NCC!",
            )
            from apps.accounts.signals import create_log
            create_log(
                action="Tạo yêu cầu đặt hàng",
                target=f"Đợt yêu cầu: {pr.code}",
                changes=f"Tiêu đề: {pr.title} | Gửi {len(supplier_ids)} NCC | {len(variant_ids)} sản phẩm",
                user=request.user
            )
        else:
            messages.success(request, f"Đã tạo đợt yêu cầu {pr.code} (bản nháp).")
            from apps.accounts.signals import create_log
            create_log(
                action="Tạo yêu cầu đặt hàng",
                target=f"Đợt yêu cầu: {pr.code}",
                changes=f"Tiêu đề: {pr.title} | Trạng thái: Bản nháp | {len(variant_ids)} sản phẩm",
                user=request.user
            )

        return redirect(supply_admin_url("request_detail", pr.pk))

    # Pre-populate from analytics selection
    variant_ids = request.GET.get("variants", "").split(",")
    variants = list(
        ProductVariant.objects.filter(
            pk__in=[v for v in variant_ids if v.strip().isdigit()], is_active=True
        ).select_related("product", "size", "color")
    )
    for v in variants:
        v.suggested_qty = _suggested_qty(v.stock)

    page_obj, paginator = paginate_list(request, variants, per_page=20)

    context = {
        "variants": page_obj.object_list,
        "all_variants": variants,
        "suppliers": Supplier.objects.filter(is_active=True),
    }
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, "supply/request_create.html", context)


@login_required
def export_csv(request, pk):
    """Tải file CSV mẫu gửi NCC."""
    if not is_store_manager(request.user):
        return redirect("admin:index")

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    response = _build_csv_response(pr)

    if pr.status == PurchaseRequest.Status.DRAFT:
        pr.status = PurchaseRequest.Status.SENT
        pr.save(update_fields=["status", "updated_at"])

    return response


@login_required
def supplier_export_csv(request, pr_pk):
    """NCC tải CSV mẫu của đợt được gửi."""
    supplier = _get_supplier_for_user(request.user)
    if not supplier:
        return redirect("admin:index")
    pr = get_object_or_404(PurchaseRequest, pk=pr_pk, suppliers=supplier)
    return _build_csv_response(pr)


@login_required
@require_POST
def send_to_suppliers(request, pk):
    """Gửi đợt nháp đến các NCC đã chọn."""
    if not is_store_manager(request.user):
        return redirect("admin:index")

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    supplier_ids = request.POST.getlist("supplier_ids")
    if supplier_ids:
        pr.suppliers.set(Supplier.objects.filter(pk__in=supplier_ids, is_active=True))
        if pr.status == PurchaseRequest.Status.DRAFT:
            pr.status = PurchaseRequest.Status.SENT
            pr.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Đã gửi đợt {pr.code} cho {len(supplier_ids)} NCC.")
    else:
        messages.error(request, "Vui lòng chọn ít nhất 1 nhà cung cấp.")
    return redirect(supply_admin_url("request_detail", pk))


@login_required
def approve_request(request, pk):
    """Cửa hàng trưởng duyệt NCC rẻ nhất và tự động tạo phiếu kiểm kê."""
    if not is_store_manager(request.user):
        return redirect("admin:index")

    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method == "POST":
        supplier_id = request.POST.get("supplier_id")
        if supplier_id == "auto":
            items = pr.items.all()
            quotes = pr.quotes.prefetch_related("items")
            supplier = _cheapest_supplier(quotes, items)
            if not supplier:
                messages.error(request, "Chưa có báo giá hợp lệ để tự chọn.")
                return redirect(supply_admin_url("request_detail", pk))
        else:
            supplier = get_object_or_404(Supplier, pk=supplier_id)

        # Cập nhật trạng thái Purchase Request
        pr.approved_supplier = supplier
        pr.approved_by = request.user
        pr.approved_at = timezone.now()
        pr.status = PurchaseRequest.Status.APPROVED
        pr.save(
            update_fields=[
                "approved_supplier",
                "approved_by",
                "approved_at",
                "status",
                "updated_at",
            ]
        )

        # Tự động tạo phiếu kiểm kê
        inventory_check = InventoryCheck.objects.create(
            purchase_request=pr,
            status=InventoryCheck.Status.PENDING,
        )

        # Lấy báo giá đã duyệt
        quote = (
            SupplierQuote.objects.filter(request=pr, supplier=supplier)
            .prefetch_related("items")
            .first()
        )

        if not quote:
            messages.warning(
                request,
                f"⚠️ Chưa có báo giá từ NCC {supplier.name}. "
                f"Đơn giá trong phiếu kiểm kê sẽ = 0. Vui lòng cập nhật thủ công nếu cần.",
            )

        # Tạo chi tiết kiểm kê từ items của purchase request và giá từ quote
        items_without_price = []
        for item in pr.items.select_related("variant").all():
            # Tìm giá từ quote
            unit_price = 0
            if quote:
                quote_item = quote.items.filter(variant=item.variant).first()
                if quote_item:
                    unit_price = quote_item.unit_price
                else:
                    items_without_price.append(str(item.variant))

            # Tạo item trong phiếu kiểm kê (chưa điền received_qty)
            InventoryCheckItem.objects.create(
                inventory_check=inventory_check,
                variant=item.variant,
                ordered_qty=item.requested_qty,
                received_qty=0,  # Để trống, sẽ điền khi kiểm kê
                unit_price=unit_price or 0,
            )

        if items_without_price:
            messages.warning(
                request,
                f"⚠️ {len(items_without_price)} mặt hàng chưa có giá trong báo giá: "
                f'{", ".join(items_without_price[:3])}{"..." if len(items_without_price) > 3 else ""}',
            )

        messages.success(
            request,
            f'✅ Đã duyệt NCC "{supplier.name}" cho đợt {pr.code} và tạo phiếu kiểm kê {inventory_check.code}! '
            f"Vui lòng thực hiện kiểm kê trước khi nhập hàng vào kho.",
        )

        from apps.accounts.signals import create_log
        create_log(
            action="Duyệt báo giá",
            target=f"Đợt yêu cầu: {pr.code}",
            changes=f"Duyệt NCC: {supplier.name} | Phiếu kiểm kê: {inventory_check.code}",
            user=request.user
        )

        # Redirect đến trang chi tiết phiếu kiểm kê
        return redirect(supply_admin_url("inventory_check_detail", inventory_check.pk))

    return redirect(supply_admin_url("request_detail", pk))


@login_required
def receive_goods(request, pk):
    """Chuyển hướng đến phiếu kiểm kê (đã được tạo khi duyệt báo giá)."""
    if not is_store_manager(request.user):
        return redirect("admin:index")

    pr = get_object_or_404(PurchaseRequest, pk=pk)

    # Kiểm tra xem đã có phiếu kiểm kê chưa
    if hasattr(pr, "inventory_check"):
        messages.info(
            request,
            f"Phiếu kiểm kê {pr.inventory_check.code} đã được tạo. "
            f"Vui lòng thực hiện kiểm kê để tiếp tục.",
        )
        return redirect(
            supply_admin_url("inventory_check_detail", pr.inventory_check.pk)
        )

    # Nếu chưa có phiếu kiểm kê, có thể là đơn hàng cũ chưa được duyệt theo quy trình mới
    # Hiển thị thông báo yêu cầu duyệt lại hoặc tạo phiếu kiểm kê thủ công
    messages.warning(
        request,
        f"Đơn hàng {pr.code} chưa có phiếu kiểm kê. "
        f"Vui lòng duyệt lại báo giá để tạo phiếu kiểm kê tự động.",
    )
    return redirect(supply_admin_url("request_detail", pk))


# ═══════════════════════════════════════════════════════════
#  INVENTORY CHECK — Kiểm kê hàng nhập
# ═══════════════════════════════════════════════════════════


@login_required
def inventory_check_list(request):
    """Danh sách phiếu kiểm kê - Quản lý kho và Admin."""
    if not (is_warehouse_manager(request.user) or request.user.is_superuser):
        messages.error(request, "Bạn không có quyền truy cập phiếu kiểm kê.")
        return redirect("admin:index")

    qs = InventoryCheck.objects.select_related(
        "purchase_request",
        "purchase_request__approved_supplier",
        "checker",
        "approved_by",
    ).order_by("-created_at")

    # Filter by status
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    page_obj, paginator = paginate_queryset(request, qs, per_page=15)

    # Đánh dấu từng phiếu kiểm kê đã cộng tồn kho hay chưa
    for check in page_obj.object_list:
        check.stock_added = check.purchase_request.items.filter(
            received_qty__gt=0
        ).exists()

    context = {
        "checks": page_obj.object_list,
        "status_choices": InventoryCheck.Status.choices,
        "status_filter": status_filter,
    }
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, "supply/inventory_check_list.html", context)


@login_required
def inventory_check_detail(request, pk):
    """Chi tiết phiếu kiểm kê - Quản lý kho và Admin."""
    if not (is_warehouse_manager(request.user) or request.user.is_superuser):
        messages.error(request, "Bạn không có quyền truy cập phiếu kiểm kê.")
        return redirect("admin:index")

    check = get_object_or_404(
        InventoryCheck.objects.select_related(
            "purchase_request",
            "purchase_request__approved_supplier",
            "checker",
            "approved_by",
        ),
        pk=pk,
    )

    # Xử lý cộng tồn kho
    if request.method == "POST" and is_store_manager(request.user):
        if check.status == InventoryCheck.Status.APPROVED:
            # Kiểm tra đã cộng tồn kho chưa
            pr = check.purchase_request
            if pr.items.filter(received_qty__gt=0).exists():
                messages.warning(
                    request, f"Phiếu {check.code} đã được cộng tồn kho rồi!"
                )
            else:
                from django.db import transaction

                with transaction.atomic():
                    for item in check.items.all():
                        if item.received_qty > 0:
                            adjust_stock(
                                variant=item.variant,
                                quantity=item.received_qty,
                                note=f"Nhập kho từ phiếu kiểm kê {check.code}",
                                actor=str(request.user),
                            )
                            # Update received_qty in PurchaseRequestItem
                            pr_item = pr.items.filter(variant=item.variant).first()
                            if pr_item:
                                pr_item.received_qty = item.received_qty
                                pr_item.save(update_fields=["received_qty"])

                    messages.success(
                        request,
                        f"✅ Đã cộng tồn kho thành công cho {check.items.count()} mặt hàng từ phiếu {check.code}!",
                    )
            return redirect(supply_admin_url("inventory_check_detail", pk))

    items_qs = check.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    )
    items_page, items_paginator = paginate_queryset(
        request, items_qs, per_page=20, page_param="items_page"
    )

    # Calculate statistics
    total_items = items_qs.count()
    matched_items = items_qs.filter(is_matched=True).count()
    mismatched_items = total_items - matched_items
    total_amount = sum(item.total_price for item in items_qs)

    # Kiểm tra đã cộng tồn kho chưa
    stock_added = check.purchase_request.items.filter(received_qty__gt=0).exists()

    context = {
        "check": check,
        "items": items_page.object_list,
        "items_page": items_page,
        "items_page_range": smart_page_range(items_page, items_paginator),
        "items_querystring": _querystring(request, exclude=("items_page",)),
        "total_items": total_items,
        "matched_items": matched_items,
        "mismatched_items": mismatched_items,
        "total_amount": total_amount,
        "stock_added": stock_added,
    }
    return render(request, "supply/inventory_check_detail.html", context)


@login_required
def perform_inventory_check(request, pk):
    """Thực hiện kiểm kê: nhập số lượng thực nhận - CHỈ Quản lý kho và Admin."""
    from .supply_permissions import is_warehouse_manager

    if not is_warehouse_manager(request.user):
        messages.error(request, "Bạn không có quyền thực hiện kiểm kê.")
        return redirect("admin:index")

    check = get_object_or_404(
        InventoryCheck,
        pk=pk,
        status__in=[
            InventoryCheck.Status.PENDING,
            InventoryCheck.Status.CHECKING,
            InventoryCheck.Status.COMPLETED,
        ],
    )

    if request.method == "POST":
        # Update status to checking if pending
        if check.status == InventoryCheck.Status.PENDING:
            check.status = InventoryCheck.Status.CHECKING
            check.checker = request.user
            check.save(update_fields=["status", "checker", "updated_at"])

        # Update items
        items = check.items.all()
        total_amount = 0

        for item in items:
            received_key = f"received_{item.pk}"
            price_key = f"price_{item.pk}"
            note_key = f"note_{item.pk}"

            if received_key in request.POST:
                try:
                    received_qty = int(request.POST.get(received_key, 0))
                except (ValueError, TypeError):
                    received_qty = 0

                try:
                    unit_price = int(float(request.POST.get(price_key, 0)))
                except (ValueError, TypeError):
                    unit_price = 0

                item.received_qty = received_qty
                item.unit_price = unit_price
                item.note = request.POST.get(note_key, "")
                item.save()

                total_amount += item.total_price

        # Update check
        check.total_amount = total_amount
        check.checked_at = timezone.now()
        check.status = InventoryCheck.Status.COMPLETED
        check.note = request.POST.get("note", "")
        check.save(
            update_fields=["total_amount", "checked_at", "status", "note", "updated_at"]
        )

        # Update purchase request status
        check.purchase_request.status = PurchaseRequest.Status.IN_CHECKING
        check.purchase_request.save(update_fields=["status", "updated_at"])

        messages.success(request, f"Đã hoàn thành kiểm kê phiếu {check.code}!")

        from apps.accounts.signals import create_log
        create_log(
            action="Kiểm kê hàng hóa",
            target=f"Phiếu kiểm kê: {check.code}",
            changes=f"Hoàn thành kiểm kê đợt {check.purchase_request.code} | Số tiền: {int(check.total_amount):,}₫",
            user=request.user
        )

        return redirect(supply_admin_url("inventory_check_detail", pk))

    items_qs = check.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    )
    items_page, items_paginator = paginate_queryset(request, items_qs, per_page=20)

    context = {
        "check": check,
        "items": items_page.object_list,
        "items_page": items_page,
        "items_page_range": smart_page_range(items_page, items_paginator),
        "items_querystring": _querystring(request),
    }
    return render(request, "supply/perform_inventory_check.html", context)


@login_required
def approve_inventory_check(request, pk):
    """Quản lý kho duyệt phiếu kiểm kê → tạo phiếu chi - CHỈ Quản lý kho và Admin."""
    if not (is_warehouse_manager(request.user) or request.user.is_superuser):
        messages.error(request, "Bạn không có quyền duyệt phiếu kiểm kê.")
        return redirect("admin:index")

    check = get_object_or_404(
        InventoryCheck, pk=pk, status=InventoryCheck.Status.COMPLETED
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            # 1. Tạo phiếu chi tiền cho NCC
            supplier = check.purchase_request.approved_supplier
            payment_voucher = PaymentVoucher.objects.create(
                inventory_check=check,
                supplier=supplier,
                amount=check.total_amount,
                status=PaymentVoucher.Status.PENDING,
                created_by=request.user,
            )

            # 2. Cập nhật trạng thái phiếu kiểm kê
            check.status = InventoryCheck.Status.APPROVED
            check.approved_by = request.user
            check.approved_at = timezone.now()
            check.save(
                update_fields=["status", "approved_by", "approved_at", "updated_at"]
            )

            # 3. Cập nhật trạng thái purchase request
            check.purchase_request.status = PurchaseRequest.Status.CHECKED
            check.purchase_request.save(update_fields=["status", "updated_at"])

            messages.success(
                request,
                f"✅ Đã duyệt phiếu kiểm kê {check.code} và tạo phiếu chi tiền {payment_voucher.code}! "
                f"Vui lòng cộng tồn kho thủ công từ phiếu kiểm kê.",
            )

            from apps.accounts.signals import create_log
            create_log(
                action="Duyệt phiếu kiểm kê",
                target=f"Phiếu kiểm kê: {check.code}",
                changes=f"Đã duyệt và tự động tạo phiếu chi {payment_voucher.code} | Số tiền: {int(payment_voucher.amount):,}₫",
                user=request.user
            )

            return redirect(
                supply_admin_url("payment_voucher_detail", payment_voucher.pk)
            )

        elif action == "reject":
            rejection_reason = request.POST.get("rejection_reason", "")
            if not rejection_reason:
                messages.error(request, "Vui lòng nhập lý do từ chối.")
                return redirect(supply_admin_url("approve_inventory_check", pk))

            check.status = InventoryCheck.Status.REJECTED
            check.rejection_reason = rejection_reason
            check.approved_by = request.user
            check.approved_at = timezone.now()
            check.save(
                update_fields=[
                    "status",
                    "rejection_reason",
                    "approved_by",
                    "approved_at",
                    "updated_at",
                ]
            )

            # Reset purchase request status
            check.purchase_request.status = PurchaseRequest.Status.APPROVED
            check.purchase_request.save(update_fields=["status", "updated_at"])

            from apps.accounts.signals import create_log
            create_log(
                action="Từ chối phiếu kiểm kê",
                target=f"Phiếu kiểm kê: {check.code}",
                changes=f"Lý do từ chối: {rejection_reason}",
                user=request.user
            )

            messages.warning(request, f"Đã từ chối phiếu kiểm kê {check.code}.")
            return redirect(supply_admin_url("inventory_check_detail", pk))

    items_qs = check.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    )

    # Calculate statistics
    total_items = items_qs.count()
    matched_items = items_qs.filter(is_matched=True).count()

    context = {
        "check": check,
        "items": items_qs,
        "total_amount": check.total_amount,
        "total_items": total_items,
        "matched_items": matched_items,
    }
    return render(request, "supply/approve_inventory_check.html", context)


# ═══════════════════════════════════════════════════════════
#  PAYMENT VOUCHER — Phiếu chi tiền NCC
# ═══════════════════════════════════════════════════════════


@login_required
def payment_voucher_list(request):
    """Danh sách phiếu chi tiền NCC."""
    if not is_store_manager(request.user):
        messages.error(request, "Bạn không có quyền truy cập.")
        return redirect("admin:index")

    qs = PaymentVoucher.objects.select_related(
        "supplier",
        "inventory_check",
        "inventory_check__purchase_request",
        "created_by",
        "paid_by",
    ).order_by("-created_at")

    # Filter by status
    status_filter = request.GET.get("status", "")
    if status_filter:
        qs = qs.filter(status=status_filter)

    page_obj, paginator = paginate_queryset(request, qs, per_page=15)

    # Calculate totals
    total_pending = (
        PaymentVoucher.objects.filter(status=PaymentVoucher.Status.PENDING).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    total_paid = (
        PaymentVoucher.objects.filter(status=PaymentVoucher.Status.PAID).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    context = {
        "vouchers": page_obj.object_list,
        "status_choices": PaymentVoucher.Status.choices,
        "status_filter": status_filter,
        "total_pending": total_pending,
        "total_paid": total_paid,
    }
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, "supply/payment_voucher_list.html", context)


@login_required
def payment_voucher_detail(request, pk):
    """Chi tiết phiếu chi tiền."""
    if not is_store_manager(request.user):
        messages.error(request, "Bạn không có quyền truy cập.")
        return redirect("admin:index")

    voucher = get_object_or_404(
        PaymentVoucher.objects.select_related(
            "supplier",
            "inventory_check",
            "inventory_check__purchase_request",
            "created_by",
            "paid_by",
        ),
        pk=pk,
    )

    items = voucher.inventory_check.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    )

    context = {
        "voucher": voucher,
        "items": items,
    }
    return render(request, "supply/payment_voucher_detail.html", context)


@login_required
def mark_payment_paid(request, pk):
    """Đánh dấu đã thanh toán cho NCC."""
    if not is_store_manager(request.user):
        messages.error(request, "Bạn không có quyền thanh toán.")
        return redirect("admin:index")

    voucher = get_object_or_404(
        PaymentVoucher, pk=pk, status=PaymentVoucher.Status.PENDING
    )

    if request.method == "POST":
        payment_method = request.POST.get("payment_method", "")
        payment_ref = request.POST.get("payment_ref", "")
        note = request.POST.get("note", "")

        voucher.status = PaymentVoucher.Status.PAID
        voucher.payment_method = payment_method
        voucher.payment_ref = payment_ref
        voucher.note = note
        voucher.paid_by = request.user
        voucher.paid_at = timezone.now()
        voucher.save(
            update_fields=[
                "status",
                "payment_method",
                "payment_ref",
                "note",
                "paid_by",
                "paid_at",
                "updated_at",
            ]
        )

        # Update purchase request to RECEIVED (final status)
        pr = voucher.inventory_check.purchase_request
        pr.status = PurchaseRequest.Status.RECEIVED
        pr.save(update_fields=["status", "updated_at"])

        messages.success(
            request,
            f"Đã thanh toán phiếu {voucher.code} cho NCC {voucher.supplier.name}!",
        )

        from apps.accounts.signals import create_log
        create_log(
            action="Thanh toán cho NCC",
            target=f"Phiếu chi: {voucher.code}",
            changes=f"Thanh toán {int(voucher.amount):,}₫ cho {voucher.supplier.name} | Phương thức: {payment_method} | Tham chiếu: {payment_ref}",
            user=request.user
        )

        return redirect(supply_admin_url("payment_voucher_detail", pk))

    context = {
        "voucher": voucher,
    }
    return render(request, "supply/mark_payment_paid.html", context)


@login_required
def add_stock_from_check(request, pk):
    """Kho cộng tồn kho từ phiếu kiểm kê đã được Cửa hàng trưởng duyệt."""
    if not is_warehouse_manager(request.user):
        messages.error(
            request, "Bạn không có quyền cộng tồn kho. Chức năng này thuộc Quản lý kho."
        )
        return redirect(supply_admin_url("inventory_check_list"))

    check = get_object_or_404(
        InventoryCheck, pk=pk, status=InventoryCheck.Status.APPROVED
    )
    # Check if already added stock
    pr = check.purchase_request
    if pr.items.filter(received_qty__gt=0).exists():
        messages.warning(request, f"Phiếu {check.code} đã được cộng tồn kho rồi!")
        return redirect(supply_admin_url("inventory_check_detail", pk))

    if request.method == "POST":
        from django.db import transaction

        with transaction.atomic():
            for item in check.items.all():
                if item.received_qty > 0:
                    adjust_stock(
                        variant=item.variant,
                        quantity=item.received_qty,
                        note=f"Nhập kho từ phiếu kiểm kê {check.code}",
                        actor=str(request.user),
                    )

                    # Update received_qty in PurchaseRequestItem
                    pr_item = pr.items.filter(variant=item.variant).first()
                    if pr_item:
                        pr_item.received_qty = item.received_qty
                        pr_item.save(update_fields=["received_qty"])

            messages.success(
                request,
                f"✅ Đã cộng tồn kho thành công cho {check.items.count()} mặt hàng từ phiếu {check.code}!",
            )

            from apps.accounts.signals import create_log
            create_log(
                action="Cộng tồn kho",
                target=f"Phiếu kiểm kê: {check.code}",
                changes=f"Cộng kho thành công cho {check.items.count()} mặt hàng từ đợt {pr.code}",
                user=request.user
            )

            return redirect(supply_admin_url("inventory_check_detail", pk))

    items = check.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    )

    context = {
        "check": check,
        "items": items,
    }
    return render(request, "supply/add_stock_from_check.html", context)


@login_required
def create_payment_from_check(request, pk):
    """Tạo phiếu chi tiền từ phiếu kiểm kê đã duyệt."""
    if not is_store_manager(request.user):
        messages.error(request, "Bạn không có quyền tạo phiếu chi.")
        return redirect("admin:index")

    check = get_object_or_404(
        InventoryCheck, pk=pk, status=InventoryCheck.Status.APPROVED
    )

    # Check if payment voucher already exists
    existing_voucher = PaymentVoucher.objects.filter(inventory_check=check).first()
    if existing_voucher:
        messages.warning(
            request,
            f"Phiếu chi {existing_voucher.code} đã được tạo cho phiếu kiểm kê này!",
        )
        return redirect(supply_admin_url("payment_voucher_detail", existing_voucher.pk))

    if request.method == "POST":
        payment_voucher = PaymentVoucher.objects.create(
            inventory_check=check,
            supplier=check.purchase_request.approved_supplier,
            amount=check.total_amount,
            status=PaymentVoucher.Status.PENDING,
            created_by=request.user,
        )

        messages.success(
            request,
            f"✅ Đã tạo phiếu chi tiền {payment_voucher.code} cho NCC {check.purchase_request.approved_supplier.name}!",
        )
        return redirect(supply_admin_url("payment_voucher_detail", payment_voucher.pk))

    context = {
        "check": check,
    }
    return render(request, "supply/create_payment_from_check.html", context)


# ═══════════════════════════════════════════════════════════
#  SUPPLIER PORTAL — NCC views
# ═══════════════════════════════════════════════════════════


@login_required
def supplier_portal(request):
    """NCC: hộp thư — danh sách đợt yêu cầu gửi đến mình."""
    supplier = _get_supplier_for_user(request.user)
    if not supplier:
        messages.error(
            request, "Tài khoản của bạn chưa được liên kết với nhà cung cấp."
        )
        return redirect("admin:index")

    requests_qs = (
        PurchaseRequest.objects.filter(
            suppliers=supplier,
            status__in=[
                PurchaseRequest.Status.SENT,
                PurchaseRequest.Status.QUOTED,
                PurchaseRequest.Status.APPROVED,
                PurchaseRequest.Status.RECEIVED,
            ],
        )
        .prefetch_related("items")
        .order_by("-created_at")
    )

    page_obj, paginator = paginate_queryset(request, requests_qs, per_page=12)

    submitted = set(
        SupplierQuote.objects.filter(
            supplier=supplier,
            request_id__in=[r.pk for r in page_obj.object_list],
        ).values_list("request_id", flat=True)
    )

    context = {
        "supplier": supplier,
        "requests": page_obj.object_list,
        "submitted": submitted,
    }
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, "supply/supplier_portal.html", context)


@login_required
def submit_quote(request, pr_pk):
    """NCC nộp hồ sơ báo giá (upload CSV)."""
    supplier = _get_supplier_for_user(request.user)
    if not supplier:
        return redirect("admin:index")

    pr = get_object_or_404(PurchaseRequest, pk=pr_pk, suppliers=supplier)

    if request.method == "POST":
        csv_file = request.FILES.get("csv_file")
        note = request.POST.get("note", "")

        if not csv_file:
            messages.error(request, "Vui lòng chọn file CSV.")
        else:
            quote, _ = SupplierQuote.objects.update_or_create(
                request=pr,
                supplier=supplier,
                defaults={"note": note, "csv_file": csv_file},
            )
            # Parse CSV → create SupplierQuoteItem rows
            try:
                # QUAN TRỌNG: update_or_create ở trên đã đọc hết file (để lưu vào
                # storage), khiến con trỏ file bị đẩy tới cuối (EOF).
                # Phải seek(0) để đọc lại từ đầu, nếu không reader sẽ rỗng.
                csv_file.seek(0)
                content = csv_file.read().decode("utf-8-sig")

                # Remove any stray BOM characters that might appear in the content
                content = content.replace("\ufeff", "").replace("\xef\xbb\xbf", "")

                # Split into lines and clean BOM from start of each line
                lines = content.splitlines()
                cleaned_lines = []
                for line in lines:
                    # Remove BOM from start of line
                    cleaned_line = line.lstrip("\ufeff").lstrip("\xef\xbb\xbf")
                    cleaned_lines.append(cleaned_line)

                # Rejoin with newlines
                content = "\n".join(cleaned_lines)

                reader = csv.DictReader(io.StringIO(content))
                quote.items.all().delete()
                errors = []
                success_count = 0
                skipped_variants = []
                # Build a map of valid variant IDs from the purchase request
                valid_variant_ids = set(pr.items.values_list("variant_id", flat=True))
                for row in reader:
                    try:
                        # Get Ma SP (already cleaned at file level)
                        raw_vid = str(row.get("Ma SP", "0")).strip()
                        # Debug: log if we can't parse the ID
                        if not raw_vid or raw_vid == "0" or not raw_vid.isdigit():
                            # Show all available keys for debugging
                            available_keys = list(row.keys())[:5]  # First 5 keys
                            skipped_variants.append(
                                f"Dòng có Mã SP không hợp lệ: '{raw_vid}' "
                                f"(các cột có: {', '.join(available_keys)})"
                            )
                            continue

                        vid = int(raw_vid)

                        # Check if variant ID is part of this purchase request
                        if vid not in valid_variant_ids:
                            skipped_variants.append(
                                f"ID {vid} không thuộc yêu cầu này (các ID hợp lệ: {', '.join(map(str, sorted(valid_variant_ids)))})"
                            )
                            continue

                        # Parse unit price - support multiple column names (Vietnamese with/without diacritics)
                        price_str = (
                            row.get("Don gia bao", "")
                            or row.get("Đơn giá báo", "")
                            or row.get("Don gia bao (NCC dien)", "")
                            or row.get("Đơn giá báo (NCC điền)", "")
                            or "0"
                        )

                        # Remove thousands separators and whitespace
                        price_str = (
                            str(price_str).strip().replace(",", "").replace(" ", "")
                        )

                        # Try to parse as number
                        try:
                            unit_price = float(price_str)
                        except ValueError:
                            unit_price = 0

                        avail_qty = int(
                            row.get("So luong NCC con", 0)
                            or row.get("Số lượng NCC còn", 0)
                            or 0
                        )
                        lead_days = int(
                            row.get("So ngay giao hang", 3)
                            or row.get("Số ngày giao hàng", 3)
                            or 3
                        )

                        v = ProductVariant.objects.filter(pk=vid).first()
                        if not v:
                            skipped_variants.append(
                                f"ID {vid} không tồn tại trong cơ sở dữ liệu"
                            )
                            continue

                        if unit_price <= 0:
                            skipped_variants.append(
                                f"{v.product.name} - Size {v.size.name if v.size else 'N/A'} "
                                f"(ID {vid}): Giá trong CSV = '{price_str}' → Bỏ qua"
                            )
                            continue

                        SupplierQuoteItem.objects.create(
                            quote=quote,
                            variant=v,
                            unit_price=int(unit_price),
                            available_qty=avail_qty,
                            lead_days=lead_days,
                        )
                        success_count += 1

                    except (ValueError, TypeError) as e:
                        errors.append(f"Dòng ID {row.get('Ma SP', '?')}: {str(e)}")
                        continue

                # Update request status
                if pr.status == PurchaseRequest.Status.SENT:
                    pr.status = PurchaseRequest.Status.QUOTED
                    pr.save(update_fields=["status", "updated_at"])

                # Show detailed feedback
                if success_count > 0:
                    messages.success(
                        request,
                        f"✅ Đã nộp báo giá! {success_count} mặt hàng có giá hợp lệ.",
                    )
                    from apps.accounts.signals import create_log
                    create_log(
                        action="NCC báo giá",
                        target=f"Đợt yêu cầu: {pr.code}",
                        changes=f"NCC: {supplier.name} | {success_count} sản phẩm có giá | Ghi chú: {note or 'Không có'}",
                        user=request.user,
                    )
                else:
                    # Show expected variant IDs if no items were saved
                    messages.error(
                        request,
                        f"❌ Không có mặt hàng nào được lưu! "
                        f'Các Mã SP hợp lệ cho đợt này: {", ".join(map(str, sorted(valid_variant_ids)))}',
                    )

                if skipped_variants:
                    skip_list = "<br>".join(skipped_variants[:5])
                    if len(skipped_variants) > 5:
                        skip_list += (
                            f"<br>... và {len(skipped_variants) - 5} mặt hàng khác"
                        )
                    messages.warning(
                        request,
                        f"⚠️ Bỏ qua {len(skipped_variants)} mặt hàng:<br>{skip_list}",
                        extra_tags="safe",
                    )

                if errors:
                    messages.error(
                        request, f"❌ {len(errors)} dòng bị lỗi khi parse CSV."
                    )
            except Exception as e:
                messages.error(request, f"Lỗi đọc file CSV: {e}")

        return redirect(supply_admin_url("bao_gia"))

    items_qs = pr.items.select_related(
        "variant", "variant__product", "variant__size", "variant__color"
    )
    items_page, items_paginator = paginate_queryset(request, items_qs, per_page=20)

    # Serialize all requested items for client-side CSV validation and mapping
    items_json_data = [
        {
            "variant_id": item.variant.pk,
            "name": item.variant.product.name,
            "size": item.variant.size.name if item.variant.size else "",
            "color": item.variant.color.name if item.variant.color else "",
            "sku": item.variant.sku or "",
            "requested_qty": item.requested_qty,
        }
        for item in items_qs
    ]
    items_json = json.dumps(items_json_data)

    context = {
        "pr": pr,
        "supplier": supplier,
        "items": items_page.object_list,
        "items_page": items_page,
        "items_page_range": smart_page_range(items_page, items_paginator),
        "items_querystring": _querystring(request),
        "items_json": items_json,
    }
    return render(request, "supply/submit_quote.html", context)


@login_required
def director_dashboard(request):
    """Trang Dashboard tài chính dành cho Tổng Giám Đốc."""
    if not is_director_or_general_director(request.user):
        messages.error(request, "Bạn không có quyền truy cập Dashboard này.")
        return redirect("admin:index")

    from decimal import Decimal

    now = timezone.now()
    year = int(request.GET.get("year", now.year))
    month = int(request.GET.get("month", now.month))

    # 1. Chi phí nhập hàng (Spent): sum of PaymentVoucher created in the month
    cost_qs = PaymentVoucher.objects.filter(
        created_at__year=year,
        created_at__month=month
    ).exclude(status=PaymentVoucher.Status.CANCELLED)
    total_cost = cost_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # 2. Doanh thu (Revenue): sum of Orders where payment is confirmed (payment_status=PAID)
    #    Filtered by created_at to avoid shifting revenue on later updates (e.g. shipping updates)
    rev_qs = Order.objects.filter(
        payment_status=Order.PaymentStatus.PAID,
        created_at__year=year,
        created_at__month=month,
    ).exclude(order_status=Order.OrderStatus.CANCELLED)
    total_revenue = rev_qs.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    # 3. Lợi nhuận (Profit) = Doanh thu - Chi phí
    profit = total_revenue - total_cost

    # 4. Tỷ lệ lợi nhuận = (Lợi nhuận / Chi phí) * 100%
    if total_cost > 0:
        margin = (profit / total_cost) * 100
    else:
        margin = 100.0 if profit > 0 else 0.0

    # Retrieve data for the chart: last 6 months (revenue and cost)
    labels_chart = []
    revenue_chart = []
    cost_chart = []
    
    from datetime import date
    current_date = date(year, month, 1)
    
    months_list = []
    temp_date = current_date
    for _ in range(6):
        months_list.append((temp_date.year, temp_date.month))
        if temp_date.month == 1:
            temp_date = date(temp_date.year - 1, 12, 1)
        else:
            temp_date = date(temp_date.year, temp_date.month - 1, 1)
            
    months_list.reverse()
    
    for y, m in months_list:
        labels_chart.append(f"{m}/{y}")
        r_sum = Order.objects.filter(
            payment_status=Order.PaymentStatus.PAID,
            created_at__year=y,
            created_at__month=m,
        ).exclude(order_status=Order.OrderStatus.CANCELLED).aggregate(total=Sum("total_amount"))["total"] or 0
        revenue_chart.append(int(r_sum))
        
        c_sum = PaymentVoucher.objects.filter(
            created_at__year=y,
            created_at__month=m
        ).exclude(status=PaymentVoucher.Status.CANCELLED).aggregate(total=Sum("amount"))["total"] or 0
        cost_chart.append(int(c_sum))

    years_choices = list(range(2025, now.year + 2))
    months_choices = list(range(1, 13))

    context = {
        "year": year,
        "month": month,
        "total_cost": total_cost,
        "total_revenue": total_revenue,
        "profit": profit,
        "margin": margin,
        "years_choices": years_choices,
        "months_choices": months_choices,
        "chart_labels": json.dumps(labels_chart),
        "chart_revenue": json.dumps(revenue_chart),
        "chart_cost": json.dumps(cost_chart),
    }
    return render(request, "supply/director_dashboard.html", context)


@login_required
def activity_log_view(request):
    """Trang Lịch sử hoạt động của nhân viên dành cho Giám Đốc/Tổng Giám Đốc."""
    if not is_director_or_general_director(request.user):
        messages.error(request, "Bạn không có quyền truy cập trang này.")
        return redirect("admin:index")

    qs = ActivityLog.objects.select_related("user").order_by("-created_at")

    q = request.GET.get("q", "")
    if q:
        qs = qs.filter(
            Q(username__icontains=q) |
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q)
        )

    action_filter = request.GET.get("action", "")
    if action_filter:
        qs = qs.filter(action=action_filter)

    user_filter = request.GET.get("user_id", "")
    if user_filter:
        qs = qs.filter(user_id=user_filter)

    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    # Danh sách hành động cố định — nhóm theo nghiệp vụ, không bị trùng lặp
    ACTION_CHOICES = [
        # Xác thực
        ("──── Xác thực ────", None),
        ("Đăng nhập", "Đăng nhập"),
        ("Đăng xuất", "Đăng xuất"),
        # Đơn hàng
        ("──── Đơn hàng ────", None),
        ("Tạo đơn hàng", "Tạo đơn hàng"),
        ("Cập nhật đơn hàng", "Cập nhật đơn hàng"),
        ("Hủy đơn hàng", "Hủy đơn hàng"),
        ("Xóa đơn hàng", "Xóa đơn hàng"),
        # Sản phẩm
        ("──── Sản phẩm ────", None),
        ("Thêm sản phẩm", "Thêm sản phẩm"),
        ("Sửa sản phẩm", "Sửa sản phẩm"),
        ("Xóa sản phẩm", "Xóa sản phẩm"),
        # Chuỗi cung ứng
        ("──── Chuỗi cung ứng ────", None),
        ("Tạo yêu cầu đặt hàng", "Tạo yêu cầu đặt hàng"),
        ("NCC báo giá", "NCC báo giá"),
        ("Duyệt báo giá", "Duyệt báo giá"),
        ("Thực hiện kiểm kê", "Thực hiện kiểm kê"),
        ("Duyệt phiếu kiểm kê", "Duyệt phiếu kiểm kê"),
        ("Từ chối phiếu kiểm kê", "Từ chối phiếu kiểm kê"),
        ("Nhập kho từ phiếu kiểm kê", "Nhập kho từ phiếu kiểm kê"),
        ("Thanh toán cho NCC", "Thanh toán cho NCC"),
        # Tồn kho
        ("──── Tồn kho ────", None),
        ("Cộng tồn kho", "Cộng tồn kho"),
        ("Trừ tồn kho", "Trừ tồn kho"),
        # Nhân sự / tài khoản
        ("──── Nhân sự ────", None),
        ("Thêm nhân viên", "Thêm nhân viên"),
        ("Sửa thông tin nhân viên", "Sửa thông tin nhân viên"),
        ("Sửa thông tin khách hàng", "Sửa thông tin khách hàng"),
        ("Xóa tài khoản", "Xóa tài khoản"),
    ]

    from django.contrib.auth.models import User
    employees = User.objects.filter(
        Q(is_staff=True) |
        Q(groups__name__in=["Cửa hàng trưởng", "Quản lý kho", "Giám Đốc", "Tổng Giám Đốc", "Giám đốc", "Tổng giám đốc"])
    ).distinct().order_by("username")

    page_obj, paginator = paginate_queryset(request, qs, per_page=20)

    context = {
        "logs": page_obj.object_list,
        "action_choices": ACTION_CHOICES,
        "employees": employees,
        "q": q,
        "action_filter": action_filter,
        "user_filter": int(user_filter) if user_filter else "",
        "start_date": start_date,
        "end_date": end_date,
    }
    context.update(_pagination_context(request, page_obj, paginator))
    return render(request, "supply/activity_log.html", context)

