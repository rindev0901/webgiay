# URL Flow Kiểm Kê Hàng

## Danh Sách URL Đã Tạo

### 1. Xác Nhận NCC Giao Hàng
**URL**: `/supply/requests/{pk}/receive/`
**View**: `receive_goods`
**Template**: `supply/confirm_shipped.html`
**Chức năng**: Xác nhận NCC đã giao hàng → Tạo phiếu kiểm kê tự động

---

### 2. Danh Sách Phiếu Kiểm Kê
**URL**: `/supply/inventory-checks/`
**View**: `inventory_check_list`
**Template**: `supply/inventory_check_list.html`
**Chức năng**: Xem tất cả phiếu kiểm kê, lọc theo trạng thái

---

### 3. Chi Tiết Phiếu Kiểm Kê
**URL**: `/supply/inventory-checks/{pk}/`
**View**: `inventory_check_detail`
**Template**: `supply/inventory_check_detail.html`
**Chức năng**: Xem chi tiết một phiếu kiểm kê, thống kê số lượng khớp/lệch

---

### 4. Thực Hiện Kiểm Kê
**URL**: `/supply/inventory-checks/{pk}/perform/`
**View**: `perform_inventory_check`
**Template**: `supply/perform_inventory_check.html`
**Chức năng**: Nhân viên kiểm kê nhập số lượng thực nhận

---

### 5. Duyệt Phiếu Kiểm Kê
**URL**: `/supply/inventory-checks/{pk}/approve/`
**View**: `approve_inventory_check`
**Template**: `supply/approve_inventory_check.html`
**Chức năng**: Cửa hàng trưởng duyệt → Cộng tồn kho + Tạo phiếu chi

---

### 6. Danh Sách Phiếu Chi Tiền
**URL**: `/supply/payment-vouchers/`
**View**: `payment_voucher_list`
**Template**: `supply/payment_voucher_list.html`
**Chức năng**: Xem tất cả phiếu chi, thống kê chờ/đã thanh toán

---

### 7. Chi Tiết Phiếu Chi
**URL**: `/supply/payment-vouchers/{pk}/`
**View**: `payment_voucher_detail`
**Template**: `supply/payment_voucher_detail.html`
**Chức năng**: Xem chi tiết phiếu chi, danh sách hàng đã mua

---

### 8. Thanh Toán NCC
**URL**: `/supply/payment-vouchers/{pk}/mark-paid/`
**View**: `mark_payment_paid`
**Template**: `supply/mark_payment_paid.html`
**Chức năng**: Cửa hàng trưởng xác nhận đã thanh toán → Hoàn thành flow

---

## Sidebar Menu (Đã Cập Nhật)

Menu bên trái đã được thêm 2 mục mới cho **Cửa hàng trưởng**:

```
Cửa hàng trưởng
├── 📊 Biên độ tồn kho
├── 📋 Yêu cầu đặt hàng
├── ✅ Phiếu kiểm kê          ← MỚI
└── 💰 Phiếu chi tiền          ← MỚI

Nhà cung cấp
└── 📥 Báo giá NCC
```

---

## Test Flow

### Bước 1: Chạy Migration
```bash
python manage.py migrate products
```

### Bước 2: Tạo Permission (Nếu Cần)
Vào Admin → Users → Chọn user → Permissions:
- `can_check_inventory`: Quyền kiểm kê hàng
- `can_approve_inventory`: Quyền duyệt phiếu kiểm kê

### Bước 3: Test Flow Hoàn Chỉnh

1. **Tạo Purchase Request**: `/supply/requests/create/`
2. **NCC báo giá**: `/supply/portal/{pr_pk}/quote/`
3. **Duyệt NCC**: `/supply/requests/{pk}/approve/`
4. **Xác nhận giao hàng**: `/supply/requests/{pk}/receive/` ← **MỚI**
   - Hệ thống tự tạo phiếu kiểm kê
5. **Kiểm kê hàng**: `/supply/inventory-checks/{pk}/perform/` ← **MỚI**
   - Nhập số lượng thực nhận
6. **Duyệt kiểm kê**: `/supply/inventory-checks/{pk}/approve/` ← **MỚI**
   - Cộng tồn kho
   - Tạo phiếu chi
7. **Thanh toán**: `/supply/payment-vouchers/{pk}/mark-paid/` ← **MỚI**
   - Hoàn thành

---

## Files Đã Tạo/Cập Nhật

### Models
- ✅ `supply_models.py`: Thêm `InventoryCheck`, `InventoryCheckItem`, `PaymentVoucher`
- ✅ `models.py`: Export các model mới
- ✅ Migration: `0006_add_inventory_check.py`

### Views
- ✅ `supply_views.py`: Thêm 7 views mới
- ✅ `supply_permissions.py`: Thêm helper `is_inventory_checker`, `can_view_inventory_check`, `can_view_payment_voucher`

### URLs
- ✅ `supply_urls.py`: Thêm 7 routes mới
- ✅ `supply_admin_paths.py`: Thêm path mappings

### Templates (8 files mới)
- ✅ `confirm_shipped.html`
- ✅ `inventory_check_list.html`
- ✅ `inventory_check_detail.html`
- ✅ `perform_inventory_check.html`
- ✅ `approve_inventory_check.html`
- ✅ `payment_voucher_list.html`
- ✅ `payment_voucher_detail.html`
- ✅ `mark_payment_paid.html`

### UI
- ✅ `layout.html`: Thêm 2 menu items
- ✅ `supply.css`: Thêm badge styles cho status mới

### Admin
- ✅ `admin.py`: Đăng ký 3 models mới với admin interface

### Documentation
- ✅ `HUONG_DAN_KIEM_KE.md`: Hướng dẫn đầy đủ
- ✅ `URL_KIEM_KE.md`: File này

---

## Tóm Tắt

✅ **8 Templates** đã tạo
✅ **7 Views** đã thêm
✅ **7 URLs** đã thêm
✅ **3 Models** mới (InventoryCheck, InventoryCheckItem, PaymentVoucher)
✅ **1 Migration** đã tạo
✅ **Sidebar Menu** đã cập nhật
✅ **CSS Badges** đã thêm cho các status mới
✅ **Admin Interface** đã đăng ký
✅ **Documentation** đầy đủ

---

## Truy Cập UI

1. **Đăng nhập** với tài khoản có quyền Store Manager
2. Truy cập: `http://localhost:8000/supply/`
3. Xem menu bên trái:
   - **Phiếu kiểm kê** → Danh sách phiếu kiểm kê
   - **Phiếu chi tiền** → Danh sách phiếu chi

Hoặc từ Purchase Request detail, click nút **"Nhận hàng vào kho"** để bắt đầu flow kiểm kê.

---

## Next Steps

1. Chạy migration: `python manage.py migrate`
2. Tạo user có quyền kiểm kê (nếu cần)
3. Test flow từ đầu đến cuối
4. Kiểm tra responsive trên mobile
5. Deploy lên production

Chúc mừng! Flow kiểm kê hàng đã hoàn tất! 🎉
