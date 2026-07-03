# Template Examples - Inventory Check Flow

## Template cần tạo

Dưới đây là danh sách các template HTML cần tạo cho flow kiểm kê hàng:

### 1. Confirm Shipped Template
**File**: `apps/products/templates/supply/confirm_shipped.html`

Template này hiển thị form xác nhận NCC đã giao hàng.

```html
{% extends "admin/base_site.html" %}
{% load static %}

{% block content %}
<div class="container">
    <h1>Xác Nhận NCC Đã Giao Hàng</h1>

    <div class="card mb-3">
        <div class="card-body">
            <h5>Đợt yêu cầu: {{ pr.code }}</h5>
            <p><strong>NCC đã chọn:</strong> {{ pr.approved_supplier.name }}</p>
            <p><strong>Trạng thái:</strong> {{ pr.get_status_display }}</p>
        </div>
    </div>

    <h3>Danh sách hàng đặt:</h3>
    <table class="table">
        <thead>
            <tr>
                <th>Sản phẩm</th>
                <th>Size</th>
                <th>Màu</th>
                <th>SL yêu cầu</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td>{{ item.variant.product.name }}</td>
                <td>{{ item.variant.size.name }}</td>
                <td>{{ item.variant.color.name|default:"Mặc định" }}</td>
                <td>{{ item.requested_qty }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <form method="post">
        {% csrf_token %}
        <button type="submit" class="btn btn-primary">
            Xác nhận NCC đã giao hàng → Tạo phiếu kiểm kê
        </button>
        <a href="{% url 'supply:request_detail' pr.pk %}" class="btn btn-secondary">Quay lại</a>
    </form>
</div>
{% endblock %}
```

---

### 2. Inventory Check List Template
**File**: `apps/products/templates/supply/inventory_check_list.html`

```html
{% extends "admin/base_site.html" %}
{% load static %}

{% block content %}
<div class="container">
    <h1>Danh Sách Phiếu Kiểm Kê</h1>

    <!-- Filter -->
    <form method="get" class="mb-3">
        <select name="status" class="form-control d-inline-block w-auto">
            <option value="">-- Tất cả trạng thái --</option>
            {% for value, label in status_choices %}
            <option value="{{ value }}" {% if value == status_filter %}selected{% endif %}>
                {{ label }}
            </option>
            {% endfor %}
        </select>
        <button type="submit" class="btn btn-sm btn-primary">Lọc</button>
    </form>

    <table class="table table-striped">
        <thead>
            <tr>
                <th>Mã phiếu</th>
                <th>Đợt đặt hàng</th>
                <th>NCC</th>
                <th>Trạng thái</th>
                <th>Người kiểm</th>
                <th>Tổng tiền</th>
                <th>Ngày tạo</th>
                <th>Thao tác</th>
            </tr>
        </thead>
        <tbody>
            {% for check in checks %}
            <tr>
                <td><strong>{{ check.code }}</strong></td>
                <td>{{ check.purchase_request.code }}</td>
                <td>{{ check.purchase_request.approved_supplier.name }}</td>
                <td>
                    <span class="badge badge-{{ check.status }}">
                        {{ check.get_status_display }}
                    </span>
                </td>
                <td>{{ check.checker|default:"—" }}</td>
                <td><strong>{{ check.total_amount|floatformat:0 }}₫</strong></td>
                <td>{{ check.created_at|date:"d/m/Y H:i" }}</td>
                <td>
                    <a href="{% url 'supply:inventory_check_detail' check.pk %}" class="btn btn-sm btn-info">
                        Xem
                    </a>
                    {% if check.status == 'pending' or check.status == 'checking' %}
                    <a href="{% url 'supply:perform_inventory_check' check.pk %}" class="btn btn-sm btn-warning">
                        Kiểm kê
                    </a>
                    {% endif %}
                    {% if check.status == 'completed' %}
                    <a href="{% url 'supply:approve_inventory_check' check.pk %}" class="btn btn-sm btn-success">
                        Duyệt
                    </a>
                    {% endif %}
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="8" class="text-center">Chưa có phiếu kiểm kê nào</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <!-- Pagination -->
    {% if page_obj.has_other_pages %}
    <nav>
        <ul class="pagination">
            {% if page_obj.has_previous %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.previous_page_number }}&{{ querystring }}">
                    Trước
                </a>
            </li>
            {% endif %}

            {% for num in page_range %}
            <li class="page-item {% if num == page_obj.number %}active{% endif %}">
                <a class="page-link" href="?page={{ num }}&{{ querystring }}">{{ num }}</a>
            </li>
            {% endfor %}

            {% if page_obj.has_next %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.next_page_number }}&{{ querystring }}">
                    Sau
                </a>
            </li>
            {% endif %}
        </ul>
    </nav>
    {% endif %}
</div>
{% endblock %}
```

---

### 3. Perform Inventory Check Template
**File**: `apps/products/templates/supply/perform_inventory_check.html`

```html
{% extends "admin/base_site.html" %}
{% load static %}

{% block content %}
<div class="container">
    <h1>Kiểm Kê Hàng - {{ check.code }}</h1>

    <div class="card mb-3">
        <div class="card-body">
            <p><strong>Đợt đặt hàng:</strong> {{ check.purchase_request.code }}</p>
            <p><strong>NCC:</strong> {{ check.purchase_request.approved_supplier.name }}</p>
            <p><strong>Trạng thái:</strong> {{ check.get_status_display }}</p>
        </div>
    </div>

    <form method="post">
        {% csrf_token %}

        <table class="table">
            <thead>
                <tr>
                    <th>Sản phẩm</th>
                    <th>Size</th>
                    <th>Màu</th>
                    <th>SL đặt</th>
                    <th>SL thực nhận <span style="color:red;">*</span></th>
                    <th>Đơn giá</th>
                    <th>Ghi chú</th>
                </tr>
            </thead>
            <tbody>
                {% for item in items %}
                <tr>
                    <td>{{ item.variant.product.name }}</td>
                    <td>{{ item.variant.size.name }}</td>
                    <td>{{ item.variant.color.name|default:"Mặc định" }}</td>
                    <td><strong>{{ item.ordered_qty }}</strong></td>
                    <td>
                        <input type="number"
                               name="received_{{ item.pk }}"
                               value="{{ item.received_qty }}"
                               min="0"
                               class="form-control"
                               required>
                    </td>
                    <td>{{ item.unit_price|floatformat:0 }}₫</td>
                    <td>
                        <input type="text"
                               name="note_{{ item.pk }}"
                               value="{{ item.note }}"
                               class="form-control"
                               placeholder="Ghi chú nếu có lệch">
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="form-group">
            <label>Ghi chú chung:</label>
            <textarea name="note" class="form-control" rows="3">{{ check.note }}</textarea>
        </div>

        <button type="submit" class="btn btn-success">
            Hoàn thành kiểm kê
        </button>
        <a href="{% url 'supply:inventory_check_list' %}" class="btn btn-secondary">Quay lại</a>
    </form>
</div>

<style>
tr td:nth-child(5) input[type="number"] {
    width: 100px;
}
</style>
{% endblock %}
```

---

### 4. Approve Inventory Check Template
**File**: `apps/products/templates/supply/approve_inventory_check.html`

```html
{% extends "admin/base_site.html" %}
{% load static %}

{% block content %}
<div class="container">
    <h1>Duyệt Phiếu Kiểm Kê - {{ check.code }}</h1>

    <div class="card mb-3">
        <div class="card-body">
            <p><strong>Đợt đặt hàng:</strong> {{ check.purchase_request.code }}</p>
            <p><strong>NCC:</strong> {{ check.purchase_request.approved_supplier.name }}</p>
            <p><strong>Người kiểm:</strong> {{ check.checker }}</p>
            <p><strong>Thời gian kiểm:</strong> {{ check.checked_at|date:"d/m/Y H:i" }}</p>
            <p><strong>Ghi chú:</strong> {{ check.note|default:"—" }}</p>
        </div>
    </div>

    <h3>Chi tiết kiểm kê:</h3>
    <table class="table">
        <thead>
            <tr>
                <th>Sản phẩm</th>
                <th>Size</th>
                <th>SL đặt</th>
                <th>SL nhận</th>
                <th>Khớp?</th>
                <th>Đơn giá</th>
                <th>Thành tiền</th>
                <th>Ghi chú</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr class="{% if not item.is_matched %}table-warning{% endif %}">
                <td>{{ item.variant.product.name }}</td>
                <td>{{ item.variant.size.name }}</td>
                <td>{{ item.ordered_qty }}</td>
                <td><strong>{{ item.received_qty }}</strong></td>
                <td>
                    {% if item.is_matched %}
                    <span class="badge badge-success">✓ Khớp</span>
                    {% else %}
                    <span class="badge badge-danger">✗ Lệch</span>
                    {% endif %}
                </td>
                <td>{{ item.unit_price|floatformat:0 }}₫</td>
                <td><strong>{{ item.total_price|floatformat:0 }}₫</strong></td>
                <td>{{ item.note|default:"—" }}</td>
            </tr>
            {% endfor %}
        </tbody>
        <tfoot>
            <tr>
                <th colspan="6" class="text-right">TỔNG CỘNG:</th>
                <th><strong>{{ total_amount|floatformat:0 }}₫</strong></th>
                <th></th>
            </tr>
        </tfoot>
    </table>

    <div class="alert alert-info">
        <strong>Lưu ý:</strong> Khi duyệt phiếu này:
        <ul>
            <li>Hệ thống sẽ <strong>cộng tồn kho</strong> theo số lượng thực nhận</li>
            <li>Tạo <strong>phiếu chi tiền</strong> cho NCC với số tiền: <strong>{{ total_amount|floatformat:0 }}₫</strong></li>
            <li>Bạn có thể xem và thanh toán phiếu chi sau khi duyệt</li>
        </ul>
    </div>

    <!-- Approve Form -->
    <form method="post" class="d-inline">
        {% csrf_token %}
        <input type="hidden" name="action" value="approve">
        <button type="submit" class="btn btn-success btn-lg"
                onclick="return confirm('Xác nhận duyệt phiếu kiểm kê?\n\n- Cộng tồn kho theo số lượng thực nhận\n- Tạo phiếu chi tiền cho NCC')">
            ✓ Duyệt Phiếu Kiểm Kê
        </button>
    </form>

    <!-- Reject Form -->
    <button type="button" class="btn btn-danger btn-lg" data-toggle="modal" data-target="#rejectModal">
        ✗ Từ Chối
    </button>

    <a href="{% url 'supply:inventory_check_detail' check.pk %}" class="btn btn-secondary">Quay lại</a>
</div>

<!-- Reject Modal -->
<div class="modal fade" id="rejectModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <form method="post">
                {% csrf_token %}
                <input type="hidden" name="action" value="reject">

                <div class="modal-header">
                    <h5 class="modal-title">Từ Chối Phiếu Kiểm Kê</h5>
                    <button type="button" class="close" data-dismiss="modal">&times;</button>
                </div>

                <div class="modal-body">
                    <div class="form-group">
                        <label>Lý do từ chối: <span style="color:red;">*</span></label>
                        <textarea name="rejection_reason"
                                  class="form-control"
                                  rows="4"
                                  required
                                  placeholder="Nhập lý do từ chối..."></textarea>
                    </div>
                </div>

                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-dismiss="modal">Hủy</button>
                    <button type="submit" class="btn btn-danger">Xác nhận từ chối</button>
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}
```

---

### 5. Payment Voucher List Template
**File**: `apps/products/templates/supply/payment_voucher_list.html`

```html
{% extends "admin/base_site.html" %}
{% load static %}

{% block content %}
<div class="container">
    <h1>Danh Sách Phiếu Chi Tiền NCC</h1>

    <div class="row mb-3">
        <div class="col-md-6">
            <div class="card bg-warning text-white">
                <div class="card-body">
                    <h5>Chờ thanh toán</h5>
                    <h2>{{ total_pending|floatformat:0 }}₫</h2>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card bg-success text-white">
                <div class="card-body">
                    <h5>Đã thanh toán</h5>
                    <h2>{{ total_paid|floatformat:0 }}₫</h2>
                </div>
            </div>
        </div>
    </div>

    <!-- Filter -->
    <form method="get" class="mb-3">
        <select name="status" class="form-control d-inline-block w-auto">
            <option value="">-- Tất cả trạng thái --</option>
            {% for value, label in status_choices %}
            <option value="{{ value }}" {% if value == status_filter %}selected{% endif %}>
                {{ label }}
            </option>
            {% endfor %}
        </select>
        <button type="submit" class="btn btn-sm btn-primary">Lọc</button>
    </form>

    <table class="table table-striped">
        <thead>
            <tr>
                <th>Mã phiếu</th>
                <th>NCC</th>
                <th>Phiếu kiểm kê</th>
                <th>Số tiền</th>
                <th>Trạng thái</th>
                <th>PT thanh toán</th>
                <th>Người thanh toán</th>
                <th>Ngày tạo</th>
                <th>Thao tác</th>
            </tr>
        </thead>
        <tbody>
            {% for voucher in vouchers %}
            <tr>
                <td><strong>{{ voucher.code }}</strong></td>
                <td>{{ voucher.supplier.name }}</td>
                <td>{{ voucher.inventory_check.code }}</td>
                <td><strong>{{ voucher.amount|floatformat:0 }}₫</strong></td>
                <td>
                    <span class="badge badge-{{ voucher.status }}">
                        {{ voucher.get_status_display }}
                    </span>
                </td>
                <td>{{ voucher.payment_method|default:"—" }}</td>
                <td>{{ voucher.paid_by|default:"—" }}</td>
                <td>{{ voucher.created_at|date:"d/m/Y" }}</td>
                <td>
                    <a href="{% url 'supply:payment_voucher_detail' voucher.pk %}"
                       class="btn btn-sm btn-info">
                        Xem
                    </a>
                    {% if voucher.status == 'pending' %}
                    <a href="{% url 'supply:mark_payment_paid' voucher.pk %}"
                       class="btn btn-sm btn-success">
                        Thanh toán
                    </a>
                    {% endif %}
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="9" class="text-center">Chưa có phiếu chi nào</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <!-- Pagination -->
    {% if page_obj.has_other_pages %}
    <nav>
        <ul class="pagination">
            {% if page_obj.has_previous %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.previous_page_number }}&{{ querystring }}">
                    Trước
                </a>
            </li>
            {% endif %}

            {% for num in page_range %}
            <li class="page-item {% if num == page_obj.number %}active{% endif %}">
                <a class="page-link" href="?page={{ num }}&{{ querystring }}">{{ num }}</a>
            </li>
            {% endfor %}

            {% if page_obj.has_next %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.next_page_number }}&{{ querystring }}">
                    Sau
                </a>
            </li>
            {% endif %}
        </ul>
    </nav>
    {% endif %}
</div>
{% endblock %}
```

---

### 6. Mark Payment Paid Template
**File**: `apps/products/templates/supply/mark_payment_paid.html`

```html
{% extends "admin/base_site.html" %}
{% load static %}

{% block content %}
<div class="container">
    <h1>Thanh Toán Cho NCC - {{ voucher.code }}</h1>

    <div class="card mb-3">
        <div class="card-body">
            <h3>Thông tin phiếu chi</h3>
            <p><strong>Mã phiếu:</strong> {{ voucher.code }}</p>
            <p><strong>NCC:</strong> {{ voucher.supplier.name }}</p>
            <p><strong>Phiếu kiểm kê:</strong> {{ voucher.inventory_check.code }}</p>
            <p><strong>Đợt đặt hàng:</strong> {{ voucher.inventory_check.purchase_request.code }}</p>
            <p><strong>Số tiền:</strong> <span style="font-size:24px; color:#16a34a; font-weight:700;">
                {{ voucher.amount|floatformat:0 }}₫
            </span></p>
        </div>
    </div>

    <h3>Thông tin thanh toán</h3>
    <form method="post">
        {% csrf_token %}

        <div class="form-group">
            <label>Phương thức thanh toán: <span style="color:red;">*</span></label>
            <select name="payment_method" class="form-control" required>
                <option value="">-- Chọn phương thức --</option>
                <option value="Chuyển khoản">Chuyển khoản</option>
                <option value="Tiền mặt">Tiền mặt</option>
                <option value="Séc">Séc</option>
                <option value="Khác">Khác</option>
            </select>
        </div>

        <div class="form-group">
            <label>Mã tham chiếu (Transaction ID):</label>
            <input type="text" name="payment_ref" class="form-control"
                   placeholder="Nhập mã giao dịch (nếu chuyển khoản)">
        </div>

        <div class="form-group">
            <label>Ghi chú:</label>
            <textarea name="note" class="form-control" rows="3"
                      placeholder="Ghi chú thêm về giao dịch..."></textarea>
        </div>

        <div class="alert alert-warning">
            <strong>Lưu ý:</strong> Sau khi xác nhận thanh toán, phiếu chi sẽ được đánh dấu là "Đã thanh toán"
            và đợt đặt hàng sẽ hoàn thành.
        </div>

        <button type="submit" class="btn btn-success btn-lg"
                onclick="return confirm('Xác nhận đã thanh toán {{ voucher.amount|floatformat:0 }}₫ cho NCC {{ voucher.supplier.name }}?')">
            ✓ Xác Nhận Đã Thanh Toán
        </button>
        <a href="{% url 'supply:payment_voucher_detail' voucher.pk %}" class="btn btn-secondary">Quay lại</a>
    </form>
</div>
{% endblock %}
```

---

## Lưu Ý Khi Tạo Template

### 1. Extends từ base template
Tất cả template đều extends từ `admin/base_site.html` để giữ UI nhất quán với Django admin.

### 2. CSRF Token
Luôn thêm `{% csrf_token %}` trong mọi form POST.

### 3. Bootstrap Classes
Sử dụng Bootstrap 4/5 classes cho styling:
- `btn btn-primary`, `btn btn-success`, `btn-danger`
- `table table-striped`
- `card`, `card-body`
- `badge badge-success`, `badge-warning`

### 4. Template Tags cần load
```django
{% load static %}
{% load humanize %}  # Nếu cần format số
```

### 5. URL reverse
```django
{% url 'supply:inventory_check_detail' check.pk %}
```

### 6. Format tiền tệ
```django
{{ amount|floatformat:0 }}₫
```

### 7. Conditional rendering
```django
{% if check.status == 'pending' %}
    <button>Kiểm kê</button>
{% elif check.status == 'completed' %}
    <button>Duyệt</button>
{% endif %}
```

---

## Tích Hợp Sidebar (Optional)

Nếu bạn muốn thêm menu vào sidebar admin, cập nhật `config/admin_sidebar.py`:

```python
{
    'label': 'Kiểm kê hàng',
    'icon': 'fas fa-clipboard-check',
    'url': '/supply/inventory-checks/',
    'permission': 'products.can_check_inventory',
},
{
    'label': 'Phiếu chi NCC',
    'icon': 'fas fa-money-bill',
    'url': '/supply/payment-vouchers/',
    'permission': 'products.can_approve_inventory',
},
```

---

## Testing Checklist

- [ ] Tạo Purchase Request và duyệt NCC
- [ ] Xác nhận NCC giao hàng → Tạo phiếu kiểm kê
- [ ] Thực hiện kiểm kê (nhập số lượng khác với đơn đặt)
- [ ] Duyệt phiếu kiểm kê → Kiểm tra tồn kho đã cộng
- [ ] Kiểm tra phiếu chi được tạo với số tiền đúng
- [ ] Thanh toán phiếu chi → Đợt đặt hàng RECEIVED
- [ ] Test từ chối phiếu kiểm kê
- [ ] Test permissions (checker không được duyệt)
