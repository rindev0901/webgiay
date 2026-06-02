# Hướng dẫn sử dụng tính năng Nhập kho hàng

## Tổng quan

Tính năng nhập kho cho phép quản trị viên nhập hàng vào kho một cách dễ dàng, với đầy đủ lịch sử và theo dõi.

## Các tính năng chính

### 1. Nhập kho thủ công qua giao diện Admin

**Cách truy cập:**
1. Đăng nhập vào Admin: `http://localhost:8000/admin/`
2. Vào mục **Sản phẩm** (Products)
3. Nhấn nút **"Nhập kho hàng"** (màu xanh lá) ở góc phải trên

**Quy trình nhập kho:**

#### Bước 1: Chọn sản phẩm
- Chọn sản phẩm cần nhập kho từ dropdown
- Hệ thống sẽ load tất cả biến thể (size/màu) của sản phẩm đó

#### Bước 2: Nhập số lượng
- Xem tồn kho hiện tại của từng biến thể
- Nhập số lượng cần nhập cho mỗi biến thể
- Có thể nhập cho nhiều biến thể cùng lúc

#### Bước 3: Thêm ghi chú (tùy chọn)
- Ví dụ: "Nhập hàng từ NCC ABC - Lô 12/2024"
- Ghi chú sẽ được lưu vào lịch sử

#### Bước 4: Xác nhận
- Nhấn **"Xác nhận nhập kho"**
- Hệ thống sẽ:
  - Cập nhật số lượng tồn kho
  - Tạo bản ghi StockMovement
  - Hiển thị thông báo thành công

### 2. Nhập kho nhanh từ danh sách biến thể

**Cách truy cập:**
1. Vào **Products** > **Biến thể sản phẩm**
2. Chọn các biến thể cần nhập kho (tick checkbox)
3. Chọn action: **"Nhập kho nhanh (+10 đôi)"**
4. Click **Go**

Mỗi biến thể được chọn sẽ được cộng thêm 10 đôi.

### 3. Xem lịch sử nhập kho

**Cách xem:**
1. Vào **Lịch sử tồn kho** (StockMovement)
2. Filter theo:
   - Loại: "Nhập kho" (IN)
   - Thời gian
   - Sản phẩm/Biến thể
   - Người thực hiện

**Thông tin hiển thị:**
- Thời gian nhập
- Sản phẩm + biến thể (size/màu)
- Số lượng nhập
- Tồn trước/sau
- Mã đơn hàng (nếu có)
- Người thực hiện
- Ghi chú

### 4. Điều chỉnh tồn kho

**Cách 1: Từ admin Biến thể**
1. Vào biến thể cần điều chỉnh
2. Xem tab **"Lịch sử tồn kho"** 
3. Sửa trực tiếp field **stock**
4. Lưu lại → Hệ thống tự tạo movement

**Cách 2: Dùng code**
```python
from apps.products.inventory import adjust_stock
from apps.products.models import ProductVariant

variant = ProductVariant.objects.get(id=1)

# Nhập thêm 50 đôi
adjust_stock(
    variant=variant,
    quantity=50,
    note='Nhập hàng lô mới từ NCC XYZ',
    actor='admin'
)

# Xuất 20 đôi (số âm)
adjust_stock(
    variant=variant,
    quantity=-20,
    note='Điều chỉnh hàng lỗi',
    actor='admin'
)
```

## Các loại movement (Loại xuất nhập)

| Loại | Mã | Mô tả |
|------|-----|-------|
| Nhập kho | `IN` | Nhập hàng vào kho |
| Xuất kho (bán) | `OUT` | Trừ kho khi bán hàng |
| Điều chỉnh | `ADJUST` | Điều chỉnh thủ công (kiểm kê, hàng lỗi) |
| Trả hàng | `RETURN` | Hoàn hàng khi khách trả/hủy đơn |
| Hủy giữ hàng | `CANCEL` | Hủy đặt giữ hàng |

## Báo cáo tồn kho

### Xem tổng tồn theo sản phẩm
1. Vào **Products**
2. Cột **"Tồn kho"** hiển thị tổng của tất cả biến thể

### Xem chi tiết theo biến thể
1. Vào **Biến thể sản phẩm** (ProductVariant)
2. Cột **"Tồn kho"** có badge màu:
   - 🟢 Xanh: Còn hàng (> 3)
   - 🟡 Vàng: Sắp hết (1-3)
   - 🔴 Đỏ: Hết hàng (0)

### Lọc hàng sắp hết
1. Vào **Biến thể sản phẩm**
2. Filter: `stock__lte=3` (≤ 3)
3. Click **Filter**

## Quy trình tự động

### Khi khách đặt hàng và thanh toán (PAID)
```python
# Tự động trừ tồn kho
from apps.products.inventory import deduct_stock

deduct_stock(order, actor='system')
```

### Khi khách hủy đơn (CANCELLED)
```python
# Tự động hoàn tồn kho
from apps.products.inventory import restore_stock

restore_stock(order, actor='system')
```

### Kiểm tra tồn kho trước checkout
```python
from apps.products.inventory import check_stock

errors = check_stock(cart_items)
if errors:
    # Hiển thị lỗi: không đủ hàng
    for err in errors:
        print(f"{err['product']}: còn {err['available']}, yêu cầu {err['requested']}")
```

## Tips & Best Practices

### 1. Ghi chú rõ ràng
- Luôn ghi chú khi nhập kho: nguồn hàng, số lô, ngày nhập
- Ví dụ: "Nhập từ NCC ABC - Invoice #12345 - Ngày 01/12/2024"

### 2. Kiểm tra trước khi nhập
- Đối chiếu với phiếu nhập kho giấy
- Kiểm tra số lượng thực tế

### 3. Backup định kỳ
- Export lịch sử StockMovement định kỳ
- Sao lưu dữ liệu database

### 4. Phân quyền
- Chỉ cho phép admin/staff nhập kho
- Sử dụng decorator `@staff_member_required`

### 5. Theo dõi thường xuyên
- Xem báo cáo hàng sắp hết hàng tuần
- Kiểm kê định kỳ (tháng/quý)

## Xử lý sự cố

### Lỗi: Tồn kho âm
- Nguyên nhân: Bán quá số lượng tồn
- Giải pháp: Dùng `adjust_stock` để điều chỉnh về 0 hoặc số dương

### Lỗi: Movement không khớp
- Nguyên nhân: Sửa trực tiếp stock mà không qua inventory service
- Giải pháp: Luôn dùng `adjust_stock()` để có lịch sử đầy đủ

### Lỗi: Race condition khi bán nhiều đơn cùng lúc
- Giải pháp: Hệ thống đã dùng `select_for_update()` để lock row khi cập nhật

## API Reference

Xem chi tiết tại: `apps/products/inventory.py`

Các hàm chính:
- `adjust_stock(variant, quantity, note, actor)` - Điều chỉnh tồn kho
- `deduct_stock(order, actor)` - Trừ kho khi bán
- `restore_stock(order, actor)` - Hoàn kho khi hủy
- `check_stock(cart_items)` - Kiểm tra trước checkout

## Liên hệ

Nếu có vấn đề hoặc câu hỏi, vui lòng liên hệ đội phát triển.
