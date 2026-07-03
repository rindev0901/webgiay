# 📦 Hướng dẫn Cộng tồn kho từ Phiếu Kiểm Kê

## 🎯 Vị trí: Trang Chi tiết Đợt Yêu Cầu Đặt Hàng

### Quy trình hoàn chỉnh:

```
1. CHT duyệt báo giá
   ↓
   ✅ Tự động tạo phiếu kiểm kê

2. Nhân viên kiểm kê
   ↓
   📝 Nhập số lượng thực nhận

3. CHT duyệt phiếu kiểm kê
   ↓
   ✅ Tự động tạo phiếu chi tiền

4. CHT vào trang "Chi tiết Đợt Yêu Cầu"
   ↓
   🖱️  Nhấn nút "Cộng tồn kho"
   ↓
   📋 Modal hiển thị danh sách sản phẩm
   ↓
   ✅ Xác nhận cộng tồn kho
```

---

## 📱 Giao diện

### Khi phiếu kiểm kê chưa duyệt:
```
┌─────────────────────────────────────────┐
│  Đợt thu mua PR8A0AABF9                 │
│  Trạng thái: Đã duyệt NCC               │
│                                         │
│  [ 📋 Xem Phiếu Kiểm Kê ]               │
└─────────────────────────────────────────┘
```

### Khi phiếu kiểm kê đã duyệt (chưa cộng kho):
```
┌─────────────────────────────────────────┐
│  Đợt thu mua PR8A0AABF9                 │
│  Trạng thái: Đã kiểm kê                 │
│                                         │
│  [ 📦 Cộng tồn kho ]  [ 💰 Xem phiếu chi ]│
└─────────────────────────────────────────┘
```

### Sau khi đã cộng tồn kho:
```
┌─────────────────────────────────────────┐
│  Đợt thu mua PR8A0AABF9                 │
│  Trạng thái: Đã kiểm kê                 │
│                                         │
│  [ ✅ Đã cộng tồn kho ]  [ 💰 Xem phiếu chi ]│
└─────────────────────────────────────────┘
```

---

## 🖱️ Modal cộng tồn kho

Khi nhấn nút **"Cộng tồn kho"**, modal hiển thị:

```
┌─────────────────────────────────────────────────┐
│  📦 Cộng tồn kho từ phiếu ICA83D60BB            │
│                                                 │
│  ⚠️ Hành động này sẽ cộng số lượng thực nhận    │
│     vào tồn kho. Không thể hoàn tác.           │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │ Sản phẩm      │ Size │ Tồn │ +SL │ Sau │   │
│  ├───────────────┼──────┼─────┼─────┼─────┤   │
│  │ Puma Stan 243 │ 35.5 │  5  │ +9  │ 14  │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│               [ Hủy ]  [ ✅ Xác nhận ]          │
└─────────────────────────────────────────────────┘
```

---

## ✨ Tính năng

### 1. Hiển thị thông minh
- ✅ Nút "Cộng tồn kho" chỉ hiển thị khi:
  - Phiếu kiểm kê đã được duyệt
  - Chưa cộng tồn kho lần nào
  - CHT đang xem trang

### 2. Xác nhận trực quan
Modal hiển thị:
- Tên sản phẩm, size, màu
- Tồn kho hiện tại
- Số lượng sẽ cộng (+X)
- Tồn kho sau khi cộng

### 3. Bảo vệ dữ liệu
- ❌ Không thể cộng tồn kho 2 lần
- ⚠️  Yêu cầu xác nhận trước khi thực hiện
- ✅ Ghi nhận lịch sử thay đổi tồn kho

### 4. Feedback rõ ràng
- Thông báo thành công: "✅ Đã cộng tồn kho thành công cho X mặt hàng"
- Thông báo lỗi: "Phiếu đã được cộng tồn kho rồi!"
- Nút chuyển thành "✅ Đã cộng tồn kho" sau khi hoàn tất

---

## 🔧 Kỹ thuật

### File đã thay đổi:

#### 1. `apps/products/supply_views.py`

**Hàm `request_detail()`:**
```python
def request_detail(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)

    # Xử lý POST để cộng tồn kho
    if request.method == 'POST' and hasattr(pr, 'inventory_check'):
        check = pr.inventory_check
        if check.status == 'approved':
            if not pr.items.filter(received_qty__gt=0).exists():
                # Cộng tồn kho
                for item in check.items.all():
                    adjust_stock(
                        variant=item.variant,
                        quantity=item.received_qty,
                        note=f'Nhập kho từ phiếu {check.code}',
                        actor=str(request.user),
                    )
                messages.success('Đã cộng tồn kho thành công!')

    # Lấy dữ liệu cho modal
    inventory_check = pr.inventory_check if hasattr(pr, 'inventory_check') else None
    stock_added = pr.items.filter(received_qty__gt=0).exists()
    check_items = inventory_check.items.all() if inventory_check and not stock_added else []

    context = {
        'inventory_check': inventory_check,
        'stock_added': stock_added,
        'check_items': check_items,
        ...
    }
```

#### 2. `templates/supply/request_detail.html`

**Nút cộng tồn kho:**
```django
{% if inventory_check.status == 'approved' %}
    {% if not stock_added %}
    <button onclick="document.getElementById('addStockModal').style.display='flex'">
        📦 Cộng tồn kho
    </button>
    {% else %}
    <span class="badge">✅ Đã cộng tồn kho</span>
    {% endif %}
{% endif %}
```

**Modal:**
```django
<div id="addStockModal" style="display:none">
    <h3>📦 Cộng tồn kho từ phiếu {{ inventory_check.code }}</h3>

    <table>
        {% for item in check_items %}
        <tr>
            <td>{{ item.variant.product.name }}</td>
            <td>{{ item.variant.stock }}</td>
            <td>+{{ item.received_qty }}</td>
            <td>{{ item.variant.stock|add:item.received_qty }}</td>
        </tr>
        {% endfor %}
    </table>

    <form method="post">
        {% csrf_token %}
        <button type="submit">Xác nhận</button>
    </form>
</div>
```

#### 3. `templates/supply/inventory_check_detail.html`

Đã **XÓA** nút "Cộng tồn kho" khỏi trang chi tiết phiếu kiểm kê.
CHT chỉ cộng tồn kho từ trang chi tiết đợt yêu cầu.

---

## 📋 Checklist sử dụng

### Cho CHT:

- [ ] Vào trang "Yêu cầu đặt hàng"
- [ ] Chọn đợt đã có phiếu kiểm kê được duyệt
- [ ] Kiểm tra trạng thái = "Đã kiểm kê"
- [ ] Nhấn nút "Cộng tồn kho"
- [ ] Kiểm tra danh sách sản phẩm trong modal
- [ ] Xác nhận số lượng đúng
- [ ] Nhấn "Xác nhận cộng tồn kho"
- [ ] Đợi thông báo thành công
- [ ] Kiểm tra nút đã chuyển thành "✅ Đã cộng tồn kho"
- [ ] (Tùy chọn) Vào trang sản phẩm kiểm tra tồn kho đã tăng

---

## ⚠️ Lưu ý quan trọng

1. **Chỉ cộng được 1 lần:**
   - Sau khi cộng tồn kho, nút sẽ biến mất
   - Hệ thống kiểm tra `received_qty > 0` để tránh cộng lại

2. **Phải duyệt phiếu kiểm kê trước:**
   - Nút chỉ hiển thị khi trạng thái = "Đã duyệt"
   - Đảm bảo số liệu đã được xác nhận

3. **Không thể hoàn tác:**
   - Sau khi cộng, chỉ có thể điều chỉnh bằng phiếu điều chỉnh riêng
   - Vì vậy cần kiểm tra kỹ trước khi xác nhận

4. **Vị trí duy nhất:**
   - CHỈ cộng tồn kho từ trang "Chi tiết Đợt Yêu Cầu"
   - KHÔNG cộng từ trang "Chi tiết Phiếu Kiểm Kê"

---

## 🧪 Test Cases

### Test 1: Hiển thị nút đúng lúc
- Tạo đơn hàng → Duyệt báo giá → Kiểm kê → Duyệt kiểm kê
- Vào trang chi tiết đợt yêu cầu
- **Kiểm tra:** Có nút "Cộng tồn kho" không?

### Test 2: Modal hiển thị đúng
- Nhấn "Cộng tồn kho"
- **Kiểm tra:** Modal hiển thị với đầy đủ thông tin?
- **Kiểm tra:** Số lượng "Tồn sau cộng" = "Tồn hiện tại" + "SL nhận"?

### Test 3: Cộng tồn kho thành công
- Nhấn "Xác nhận cộng tồn kho"
- **Kiểm tra:** Thông báo thành công?
- **Kiểm tra:** Tồn kho tăng đúng?
- **Kiểm tra:** Nút chuyển thành "✅ Đã cộng tồn kho"?

### Test 4: Không thể cộng lại
- Thử refresh và nhấn lại
- **Kiểm tra:** Không còn nút "Cộng tồn kho"?
- **Kiểm tra:** Chỉ hiển thị "✅ Đã cộng tồn kho"?

---

**Ngày cập nhật:** 2026-07-03
**Trạng thái:** ✅ Hoàn thành
