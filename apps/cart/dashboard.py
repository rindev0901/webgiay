"""
dashboard.py — Data callbacks for Unfold admin dashboard.
"""
import json
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from .models import Order


# ── Helpers ──────────────────────────────────────────
def _vnd(value):
    try:
        v = int(value or 0)
        return f"{v:,}".replace(",", ".")
    except Exception:
        return "0"


def _pct_change(current, previous):
    """Return formatted % change string."""
    try:
        if previous == 0:
            return "+100%" if current > 0 else "0%"
        pct = (current - previous) / previous * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%"
    except Exception:
        return "—"


# ── Main callback ─────────────────────────────────────
def dashboard_callback(request, context):
    now = timezone.now()
    today = now.date()
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)

    paid_qs = Order.objects.filter(status=Order.Status.PAID)

    # ── KPI cards ────────────────────────────────────
    # Revenue this month
    rev_this = paid_qs.filter(
        created_at__date__gte=this_month_start
    ).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')

    rev_last = paid_qs.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lte=last_month_end,
    ).aggregate(s=Sum('total_amount'))['s'] or Decimal('0')

    # Orders this month
    orders_this = paid_qs.filter(created_at__date__gte=this_month_start).count()
    orders_last = paid_qs.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lte=last_month_end,
    ).count()

    # Orders today
    orders_today = paid_qs.filter(created_at__date=today).count()

    # Pending orders
    pending = Order.objects.filter(status=Order.Status.PENDING).count()

    # Total revenue all time
    total_rev = paid_qs.aggregate(s=Sum('total_amount'))['s'] or Decimal('0')

    # ── Revenue last 30 days (daily) ─────────────────
    days_30_start = today - timedelta(days=29)
    daily_rev = (
        paid_qs
        .filter(created_at__date__gte=days_30_start)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('total_amount'), cnt=Count('id'))
        .order_by('day')
    )
    # Build full 30-day range (fill zeros)
    daily_map = {r['day']: (int(r['total']), r['cnt']) for r in daily_rev}
    labels_30d = []
    rev_30d = []
    orders_30d = []
    for i in range(30):
        d = days_30_start + timedelta(days=i)
        labels_30d.append(d.strftime("%d/%m"))
        rev, cnt = daily_map.get(d, (0, 0))
        rev_30d.append(rev // 1000)   # show in nghìn ₫
        orders_30d.append(cnt)

    # ── Revenue last 12 months ───────────────────────
    months_12_start = (today.replace(day=1) - timedelta(days=365)).replace(day=1)
    monthly_rev = (
        paid_qs
        .filter(created_at__date__gte=months_12_start)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Sum('total_amount'), cnt=Count('id'))
        .order_by('month')
    )
    monthly_map = {r['month'].date().replace(day=1): (int(r['total']), r['cnt']) for r in monthly_rev}
    labels_12m = []
    rev_12m = []
    orders_12m = []
    cur = months_12_start
    for _ in range(12):
        labels_12m.append(cur.strftime("%m/%Y"))
        rev, cnt = monthly_map.get(cur, (0, 0))
        rev_12m.append(rev // 1000)
        orders_12m.append(cnt)
        # next month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

    # ── Order status breakdown ────────────────────────
    status_data = (
        Order.objects
        .values('status')
        .annotate(cnt=Count('id'))
        .order_by('status')
    )
    status_labels = []
    status_counts = []
    status_colors = {
        'pending': '#f59e0b',
        'paid': '#22c55e',
        'failed': '#ef4444',
        'cancelled': '#6b7280',
    }
    status_display = {
        'pending': 'Chờ TT',
        'paid': 'Đã TT',
        'failed': 'Thất bại',
        'cancelled': 'Đã huỷ',
    }
    for s in status_data:
        status_labels.append(status_display.get(s['status'], s['status']))
        status_counts.append(s['cnt'])
    status_bg = [status_colors.get(s['status'], '#999') for s in status_data]

    # ── Top products ─────────────────────────────────
    from django.apps import apps
    OrderItem = apps.get_model('cart', 'OrderItem')
    top_products = (
        OrderItem.objects
        .filter(order__status=Order.Status.PAID)
        .values('product_name')
        .annotate(qty=Sum('quantity'), rev=Sum('price'))
        .order_by('-qty')[:8]
    )
    tp_labels = [p['product_name'][:20] for p in top_products]
    tp_qty    = [p['qty'] for p in top_products]

    # ── Recent orders ─────────────────────────────────
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:8]

    # ── Update context ────────────────────────────────
    context.update({
        # KPI
        "kpi": {
            "rev_this_month":    _vnd(rev_this),
            "rev_last_month":    _vnd(rev_last),
            "rev_change":        _pct_change(int(rev_this), int(rev_last)),
            "rev_positive":      rev_this >= rev_last,
            "orders_this_month": orders_this,
            "orders_last_month": orders_last,
            "orders_change":     _pct_change(orders_this, orders_last),
            "orders_positive":   orders_this >= orders_last,
            "orders_today":      orders_today,
            "pending":           pending,
            "total_rev":         _vnd(total_rev),
        },

        # Charts — 30 days
        "chart_revenue_30d": json.dumps({
            "labels": labels_30d,
            "datasets": [
                {
                    "label": "Doanh thu (nghìn ₫)",
                    "data": rev_30d,
                    "backgroundColor": "rgba(139,0,0,0.15)",
                    "borderColor": "#8b0000",
                    "borderWidth": 2,
                    "fill": True,
                    "type": "line",
                    "tension": 0.4,
                }
            ]
        }),

        "chart_orders_30d": json.dumps({
            "labels": labels_30d,
            "datasets": [
                {
                    "label": "Đơn hàng",
                    "data": orders_30d,
                    "backgroundColor": "#8b0000",
                }
            ]
        }),

        # Charts — 12 months
        "chart_revenue_12m": json.dumps({
            "labels": labels_12m,
            "datasets": [
                {
                    "label": "Doanh thu (nghìn ₫)",
                    "data": rev_12m,
                    "backgroundColor": "#8b0000",
                },
                {
                    "label": "Đơn hàng",
                    "data": orders_12m,
                    "borderColor": "#f59e0b",
                    "type": "line",
                    "borderWidth": 2,
                },
            ]
        }),

        # Pie — order status
        "chart_status": json.dumps({
            "labels": status_labels,
            "datasets": [
                {
                    "data": status_counts,
                    "backgroundColor": status_bg,
                }
            ]
        }),

        # Top products bar
        "chart_top_products": json.dumps({
            "labels": tp_labels,
            "datasets": [
                {
                    "label": "Số lượng bán",
                    "data": tp_qty,
                    "backgroundColor": "#8b0000",
                }
            ]
        }),

        # Recent orders table
        "recent_orders": recent_orders,
    })

    return context
