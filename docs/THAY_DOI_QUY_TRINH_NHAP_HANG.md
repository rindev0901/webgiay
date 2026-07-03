# Tóm tắt thay đổi: Quy trình nhập hàng từ NCC

## 📝 Mô tả thay đổi

Cập nhật quy trình nhập hàng để đảm bảo kiểm soát chặt chẽ hơn:
- **Trước:** CHT duyệt báo giá → CHT xác nhận giao hàng → Tạo phiếu kiểm kê → Kiểm kê → Duyệt kiểm kê → Nhập kho thủ công
- **Sau:** CHT duyệt báo giá → **Tự động tạo phiếu kiểm kê** → Kiểm kê → Duyệt kiểm kê → **Tự động tạo phiếu chi** → **CHT nhập kho thủ công**

---

## 🔧 Các file đã thay đổi

### 1. `apps/products/supply_views.py`

#### `approve_request()` - Duyệt báo giá
**Thay đổi:**
- Sau khi duyệt NCC, tự động tạo phiếu kiểm kê (`InventoryCheck`)
- Tạo sẵn các `InventoryCheckItem` với:
  - `ordered_qty`: Số lượng đã đặt
  - `received_qty`: 0 (sẽ điền khi kiểm kê)
  - `unit_price`: Lấy từ báo giá đã duyệt
- Chuyển hướng đến trang chi tiết phiếu kiểm kê thay vì quay lại danh sách

**Code:**
```python
# Tự động tạo phiếu kiểm kê
inventory_check = InventoryCheck.objects.create(
    purchase_request=pr,
    status=InventoryCheck.Status.PENDING,
)

# Tạo chi tiết từ báo giá đã duyệt
quote = SupplierQuote.objects.filter(
    request=pr, supplier=supplier
).prefetch_related('items').first()

for item in pr.items.select_related('variant').all():
    unit_price = 0
    if quote:
        quote_item = quote.items.filter(variant=item.variant).first()
        if quote_item:
            unit_price = quote_item.unit_price

    InventoryCheckItem.objects.create(
        inventory_check=inventory_check,
        variant=item.variant,
        ordered_qty=item.requested_qty,
        received_qty=0,
        unit_price=unit_price or 0,
    )
```

#### `approve_inventory_check()` - Duyệt phiếu kiểm kê
**Thay đổi:**
- Khi duyệt phiếu kiểm kê, **tự động tạo phiếu chi tiền** (`PaymentVoucher`) cho NCC
- **KHÔNG tự động cộng tồn kho** - CHT sẽ cộng thủ công sau khi kiểm tra kỹ

**Code:**
```python
if action == 'approve':
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
    check.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    # 3. Cập nhật trạng thái purchase request
    check.purchase_request.status = PurchaseRequest.Status.CHECKED
    check.purchase_request.save(update_fields=['status', 'updated_at'])
```

**Lưu ý:** CHT cần cộng tồn kho thủ công từ phiếu kiểm kê chi tiết để đảm bảo kiểm soát chặt chẽ.

#### `receive_goods()` - Nhận hàng vào kho (Deprecated)
**Thay đổi:**
- Hàm này không còn tạo phiếu kiểm kê nữa (đã được tạo ở `approve_request`)
- Chỉ chuyển hướng đến phiếu kiểm kê nếu đã tồn tại
- Hiển thị thông báo yêu cầu duyệt lại báo giá nếu chưa có phiếu kiểm kê

---

### 2. `apps/products/supply_models.py`

**Thay đổi:**
- Thêm comment cho các trạng thái để làm rõ quy trình:
  - `APPROVED`: Phiếu kiểm kê được tạo tự động
  - `SHIPPED`: Deprecated - không dùng nữa
  - `CHECKED`: Đã duyệt phiếu kiểm kê, đã cộng kho

---

### 3. `templates/supply/request_detail.html`

**Thay đổi:**
- Xóa nút "Nhận hàng vào kho" cho trạng thái `approved`
- Thêm nút "Xem Phiếu Kiểm Kê" khi phiếu kiểm kê đã được tạo

**Code:**
```django
{% if pr.inventory_check %}
<a href="{% supply_url 'inventory_check_detail' pr.inventory_check.pk %}" class="btn-blue">
    <i class="fas fa-clipboard-check"></i> Xem Phiếu Kiểm Kê
</a>
{% endif %}
```

---

### 4. `templates/supply/approve_inventory_check.html`

**Thay đổi:**
- Cập nhật thông báo để phản ánh đúng hành vi:
  - "Tự động tạo phiếu chi tiền cho NCC"
  - "CHT sẽ cộng tồn kho thủ công từ phiếu kiểm kê chi tiết"
- Cập nhật mô tả nút duyệt: "Xác nhận phiếu kiểm kê hợp lệ và tự động tạo phiếu chi tiền cho NCC. CHT sẽ cộng tồn kho thủ công sau."

---

## 📊 Sơ đồ quy trình

### Quy trình cũ:
```
Duyệt báo giá → Xác nhận giao hàng → Tạo phiếu kiểm kê → Kiểm kê → Duyệt kiểm kê → Nhập kho thủ công → Tạo phiếu chi thủ công
```

### Quy trình mới:
```
Duyệt báo giá ──┐
                ├─→ Tự động tạo phiếu kiểm kê
                │
Kiểm kê ────────┘

Duyệt kiểm kê ──┐
                ├─→ Tự động tạo phiếu chi tiền
                │
CHT nhập kho ───┤ (Thủ công)
                │
Thanh toán ─────┘
```

---

## ✅ Lợi ích

1. **Giảm thiểu sai sót:** Không thể bỏ qua bước kiểm kê
2. **Tự động hóa hợp lý:** Tự động tạo phiếu chi, CHT chủ động nhập kho
3. **Kiểm soát chặt chẽ:** CHT quyết định khi nào cộng tồn kho sau khi duyệt phiếu kiểm kê
4. **Truy xuất nguồn gốc:** Mỗi giao dịch có đầy đủ phiếu kiểm kê và phiếu chi

---

## ⚠️ Lưu ý khi triển khai

1. **Đơn hàng cũ:** Các đơn hàng có trạng thái `APPROVED` từ trước bản cập nhật sẽ không có phiếu kiểm kê. CHT cần:
   - Kiểm tra lại và duyệt lại báo giá để tạo phiếu kiểm kê
   - Hoặc xử lý thủ công cho các đơn hàng đã hoàn thành

2. **Migration:** Không cần tạo migration mới vì chỉ thay đổi logic, không thay đổi schema

3. **Quyền hạn:** Đảm bảo:
   - CHT có quyền: `can_approve_purchase`, `can_approve_inventory`
   - Nhân viên kiểm kê có quyền: `can_check_inventory`

---

## 🧪 Kiểm tra

Để kiểm tra quy trình mới:

1. Tạo đợt yêu cầu đặt hàng mới
2. Gửi cho NCC và đợi báo giá
3. Duyệt báo giá → Kiểm tra phiếu kiểm kê có được tạo tự động không
4. Thực hiện kiểm kê → Nhập số lượng thực nhận
5. Duyệt phiếu kiểm kê → Kiểm tra:
   - Tồn kho có được cộng đúng không
   - Phiếu chi tiền có được tạo không
   - Có ghi nhận `StockMovement` không (nếu có bảng này)

---

*Cập nhật: {{ current_date }}*
