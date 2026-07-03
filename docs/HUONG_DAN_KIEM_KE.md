# Hướng Dẫn Flow Kiểm Kê Hàng

## Tổng Quan

Flow kiểm kê hàng được thiết kế để kiểm soát chặt chẽ quá trình nhập hàng từ nhà cung cấp (NCC), đảm bảo số lượng thực nhận khớp với đơn hàng trước khi cộng tồn kho và thanh toán cho NCC.

## Các Vai Trò

1. **Cửa hàng trưởng (Store Manager)**: Tạo yêu cầu đặt hàng, duyệt NCC, duyệt phiếu kiểm kê, thanh toán
2. **Nhà cung cấp (Supplier)**: Nhận yêu cầu, báo giá, giao hàng
3. **Nhân viên kiểm kê (Inventory Checker)**: Kiểm tra hàng thực tế, nhập số lượng vào phiếu kiểm kê

## Flow Hoàn Chỉnh

### Bước 1: Cửa hàng trưởng tạo Purchase Request

**Trạng thái**: `DRAFT` → `SENT`

1. Truy cập: `/supply/` (Biên độ tồn kho)
2. Xem phân tích sản phẩm bán chạy/ế/sắp hết
3. Chọn các variant cần đặt hàng
4. Chọn các NCC để gửi yêu cầu
5. Tạo đợt yêu cầu → Status: `SENT`

**URL**:
- Analytics: `/supply/`
- Tạo request: `/supply/requests/create/`

---

### Bước 2: NCC nhận yêu cầu và báo giá

**Trạng thái**: `SENT` → `QUOTED`

1. NCC đăng nhập vào hệ thống
2. Truy cập: `/supply/portal/` (Hộp thư NCC)
3. Xem các đợt yêu cầu được gửi đến
4. Tải file CSV mẫu
5. Điền giá và số lượng có thể cung cấp
6. Upload file CSV báo giá
7. Hệ thống tự động parse và lưu báo giá

**URL**:
- Portal NCC: `/supply/portal/`
- Nộp báo giá: `/supply/portal/{pr_pk}/quote/`

---

### Bước 3: Cửa hàng trưởng duyệt NCC

**Trạng thái**: `QUOTED` → `APPROVED`

1. Xem chi tiết Purchase Request
2. So sánh báo giá từ các NCC
3. Hệ thống gợi ý NCC rẻ nhất
4. Chọn NCC và duyệt
5. Status chuyển sang `APPROVED`

**URL**:
- Chi tiết request: `/supply/requests/{pk}/`
- Duyệt NCC: `/supply/requests/{pk}/approve/`

---

### Bước 4: NCC giao hàng

**Trạng thái**: `APPROVED` → `SHIPPED`

1. NCC giao hàng đến kho
2. Cửa hàng trưởng xác nhận đã nhận hàng
3. Truy cập: `/supply/requests/{pk}/receive/`
4. Nhấn "Xác nhận NCC đã giao hàng"
5. **Hệ thống tự động tạo Phiếu Kiểm Kê (InventoryCheck)**
6. Status chuyển sang `SHIPPED`

**Phiếu kiểm kê được tạo với:**
- Status: `PENDING`
- Items: Copy từ PurchaseRequestItem
- Giá: Lấy từ SupplierQuote đã duyệt
- `received_qty`: 0 (chờ kiểm kê)

**URL**: `/supply/requests/{pk}/receive/`

---

### Bước 5: Nhân viên kiểm kê thực hiện kiểm kê

**Trạng thái**: `PENDING` → `CHECKING` → `COMPLETED`

**Purchase Request**: `SHIPPED` → `IN_CHECKING`

1. Truy cập danh sách phiếu kiểm kê: `/supply/inventory-checks/`
2. Chọn phiếu cần kiểm (Status: `PENDING`)
3. Truy cập: `/supply/inventory-checks/{pk}/perform/`
4. Kiểm tra từng mặt hàng thực tế
5. Nhập số lượng thực nhận vào form
6. Thêm ghi chú nếu có sai lệch
7. Có thể upload ảnh kiểm tra (optional)
8. Hoàn thành → Status: `COMPLETED`

**Hệ thống tự động:**
- Tính `is_matched` (khớp nếu `received_qty == ordered_qty`)
- Tính `total_price = received_qty × unit_price`
- Tính tổng tiền phiếu kiểm kê

**URL**:
- Danh sách: `/supply/inventory-checks/`
- Thực hiện kiểm: `/supply/inventory-checks/{pk}/perform/`

---

### Bước 6: Cửa hàng trưởng duyệt phiếu kiểm kê

**Trạng thái**: `COMPLETED` → `APPROVED` hoặc `REJECTED`

**Purchase Request**: `IN_CHECKING` → `CHECKED`

#### Trường hợp Duyệt (APPROVE):

1. Xem chi tiết phiếu kiểm kê
2. Kiểm tra số lượng, giá cả, các mục lệch
3. Truy cập: `/supply/inventory-checks/{pk}/approve/`
4. Chọn "Duyệt phiếu kiểm kê"

**Hệ thống tự động:**
- **Cộng tồn kho** cho từng variant (gọi `adjust_stock`)
- Tạo `StockMovement` với type = `IN`
- Cập nhật `received_qty` trong `PurchaseRequestItem`
- **Tạo Phiếu Chi Tiền (PaymentVoucher)**
  - Status: `PENDING`
  - Amount: Tổng tiền từ phiếu kiểm kê
  - Supplier: NCC đã duyệt
- InventoryCheck status → `APPROVED`
- PurchaseRequest status → `CHECKED`

#### Trường hợp Từ chối (REJECT):

1. Nhập lý do từ chối
2. Phiếu kiểm kê → Status: `REJECTED`
3. PurchaseRequest → Status quay lại `APPROVED`
4. Có thể tạo phiếu kiểm kê mới hoặc yêu cầu NCC giao lại

**URL**: `/supply/inventory-checks/{pk}/approve/`

---

### Bước 7: Thanh toán cho NCC

**Trạng thái PaymentVoucher**: `PENDING` → `PAID`

**Purchase Request**: `CHECKED` → `RECEIVED` (Hoàn thành)

1. Truy cập danh sách phiếu chi: `/supply/payment-vouchers/`
2. Xem chi tiết phiếu chi: `/supply/payment-vouchers/{pk}/`
3. Kiểm tra thông tin NCC, số tiền
4. Thực hiện thanh toán (chuyển khoản, tiền mặt, v.v.)
5. Truy cập: `/supply/payment-vouchers/{pk}/mark-paid/`
6. Nhập thông tin thanh toán:
   - Phương thức thanh toán
   - Mã tham chiếu (transaction ID)
   - Ghi chú
7. Xác nhận → Status: `PAID`

**Hệ thống tự động:**
- PaymentVoucher status → `PAID`
- Ghi nhận người thanh toán và thời gian
- **PurchaseRequest status → `RECEIVED` (Hoàn thành toàn bộ flow)**

**URL**:
- Danh sách: `/supply/payment-vouchers/`
- Chi tiết: `/supply/payment-vouchers/{pk}/`
- Thanh toán: `/supply/payment-vouchers/{pk}/mark-paid/`

---

## Sơ Đồ Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. CỬA HÀNG TRƯỞNG: Tạo Purchase Request                          │
│     → Chọn sản phẩm cần đặt                                         │
│     → Chọn NCC gửi yêu cầu                                          │
│     Status: DRAFT → SENT                                            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. NHÀ CUNG CẤP: Báo giá                                           │
│     → Tải CSV mẫu                                                   │
│     → Điền giá + số lượng                                           │
│     → Upload CSV                                                    │
│     Status: SENT → QUOTED                                           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. CỬA HÀNG TRƯỞNG: Duyệt NCC                                      │
│     → So sánh báo giá                                               │
│     → Chọn NCC tốt nhất                                             │
│     Status: QUOTED → APPROVED                                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. NCC GIAO HÀNG + Xác nhận                                        │
│     → NCC giao hàng đến kho                                         │
│     → Cửa hàng trưởng xác nhận                                      │
│     → HỆ THỐNG TỰ ĐỘNG TẠO PHIẾU KIỂM KÊ                           │
│     Status: APPROVED → SHIPPED                                      │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. NHÂN VIÊN KIỂM KÊ: Kiểm tra hàng                                │
│     → Kiểm tra từng mặt hàng thực tế                                │
│     → Nhập số lượng thực nhận                                       │
│     → Ghi chú nếu có lệch                                           │
│     InventoryCheck: PENDING → CHECKING → COMPLETED                  │
│     PurchaseRequest: SHIPPED → IN_CHECKING                          │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. CỬA HÀNG TRƯỞNG: Duyệt phiếu kiểm kê                            │
│     → Xem kết quả kiểm kê                                           │
│     → Duyệt HOẶC Từ chối                                            │
│                                                                     │
│     NẾU DUYỆT:                                                      │
│     ✓ CỘNG TỒN KHO (adjust_stock)                                   │
│     ✓ TẠO PHIẾU CHI TIỀN                                            │
│     InventoryCheck: COMPLETED → APPROVED                            │
│     PurchaseRequest: IN_CHECKING → CHECKED                          │
│                                                                     │
│     NẾU TỪ CHỐI:                                                    │
│     ✗ Nhập lý do từ chối                                            │
│     ✗ PurchaseRequest quay lại APPROVED                             │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  7. CỬA HÀNG TRƯỞNG: Thanh toán cho NCC                             │
│     → Xem phiếu chi                                                 │
│     → Thực hiện thanh toán                                          │
│     → Nhập thông tin thanh toán                                     │
│     PaymentVoucher: PENDING → PAID                                  │
│     PurchaseRequest: CHECKED → RECEIVED ✓ HOÀN THÀNH                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Trạng Thái Chi Tiết

### PurchaseRequest Status

| Status | Mô tả | Hành động tiếp theo |
|--------|-------|---------------------|
| `DRAFT` | Bản nháp, chưa gửi NCC | Gửi cho NCC |
| `SENT` | Đã gửi cho NCC | NCC báo giá |
| `QUOTED` | NCC đã báo giá | Cửa hàng trưởng duyệt NCC |
| `APPROVED` | Đã duyệt NCC | NCC giao hàng |
| `SHIPPED` | NCC đã giao hàng | Tạo phiếu kiểm kê |
| `IN_CHECKING` | Đang kiểm kê | Nhân viên hoàn thành kiểm kê |
| `CHECKED` | Đã kiểm kê và duyệt | Thanh toán cho NCC |
| `RECEIVED` | Đã thanh toán (Hoàn thành) | - |
| `CANCELLED` | Đã hủy | - |

### InventoryCheck Status

| Status | Mô tả | Hành động tiếp theo |
|--------|-------|---------------------|
| `PENDING` | Chờ kiểm tra | Nhân viên bắt đầu kiểm |
| `CHECKING` | Đang kiểm | Nhân viên hoàn thành |
| `COMPLETED` | Hoàn thành kiểm kê | Cửa hàng trưởng duyệt |
| `APPROVED` | Đã duyệt (cộng tồn kho) | Thanh toán NCC |
| `REJECTED` | Từ chối | Kiểm lại hoặc trả hàng |

### PaymentVoucher Status

| Status | Mô tả |
|--------|-------|
| `PENDING` | Chờ thanh toán |
| `PAID` | Đã thanh toán |
| `CANCELLED` | Đã hủy |

---

## Quyền Hạn (Permissions)

### Custom Permissions

```python
# PurchaseRequest
- 'products.can_approve_purchase'  # Duyệt đặt hàng
- 'products.can_receive_goods'     # Nhận hàng

# InventoryCheck
- 'products.can_check_inventory'   # Kiểm kê hàng
- 'products.can_approve_inventory' # Duyệt phiếu kiểm kê
```

### Vai trò mặc định

- **Superuser/Staff**: Có tất cả quyền
- **Store Manager**: Quyền quản lý toàn bộ flow
- **Inventory Checker**: Chỉ quyền kiểm kê (`can_check_inventory`)
- **Supplier User**: Chỉ xem portal NCC và báo giá

---

## Models Chính

### 1. InventoryCheck

**Phiếu kiểm kê hàng nhập từ NCC**

```python
- code: Mã phiếu (IC12345678)
- purchase_request: OneToOne với PurchaseRequest
- status: pending/checking/completed/approved/rejected
- checker: Người kiểm kê
- approved_by: Người duyệt
- total_amount: Tổng tiền thanh toán
- note: Ghi chú
- rejection_reason: Lý do từ chối (nếu reject)
```

### 2. InventoryCheckItem

**Chi tiết từng mặt hàng trong phiếu kiểm kê**

```python
- inventory_check: ForeignKey
- variant: ProductVariant
- ordered_qty: Số lượng đặt hàng
- received_qty: Số lượng thực nhận
- unit_price: Đơn giá
- total_price: Thành tiền (auto calculated)
- is_matched: Khớp đơn hàng? (auto calculated)
- note: Ghi chú
- image: Ảnh kiểm tra (optional)
```

### 3. PaymentVoucher

**Phiếu chi tiền cho NCC**

```python
- code: Mã phiếu chi (PV12345678)
- inventory_check: OneToOne với InventoryCheck
- supplier: NCC nhận tiền
- amount: Số tiền
- status: pending/paid/cancelled
- payment_method: Phương thức thanh toán
- payment_ref: Mã tham chiếu
- paid_by: Người thanh toán
- paid_at: Thời gian thanh toán
```

---

## Tính Năng Nổi Bật

### 1. Tự động tính toán

- ✓ Thành tiền = `received_qty × unit_price`
- ✓ Khớp đơn = `received_qty == ordered_qty`
- ✓ Tổng tiền phiếu kiểm kê
- ✓ Tổng tiền chờ thanh toán, đã thanh toán

### 2. Kiểm soát chặt chẽ

- ✓ Chỉ cộng tồn kho sau khi duyệt phiếu kiểm kê
- ✓ Chỉ tạo phiếu chi sau khi duyệt kiểm kê
- ✓ Chỉ đánh dấu hoàn thành sau khi thanh toán
- ✓ Không cho tạo phiếu kiểm kê thủ công (chỉ từ flow)

### 3. Truy vết đầy đủ

- ✓ Ai kiểm kê, ai duyệt, ai thanh toán
- ✓ Thời gian từng bước
- ✓ Lịch sử tồn kho chi tiết
- ✓ Ghi chú và lý do từ chối

### 4. Báo cáo & Thống kê

- ✓ Tổng tiền chờ thanh toán
- ✓ Tổng tiền đã thanh toán
- ✓ Tỷ lệ khớp đơn hàng
- ✓ Số lượng lệch (ordered vs received)

---

## Lưu Ý Quan Trọng

### ⚠️ Flow bắt buộc

- **KHÔNG THỂ** cộng tồn kho trước khi kiểm kê
- **KHÔNG THỂ** thanh toán trước khi duyệt phiếu kiểm kê
- **KHÔNG THỂ** bỏ qua bất kỳ bước nào

### ⚠️ Rollback

- Nếu từ chối phiếu kiểm kê → PurchaseRequest quay lại `APPROVED`
- Có thể tạo phiếu kiểm kê mới hoặc yêu cầu NCC giao lại
- Tồn kho chỉ cộng khi duyệt, nên từ chối không ảnh hưởng

### ⚠️ Permission

- Tách biệt vai trò kiểm kê và duyệt
- Nhân viên kiểm kê không được tự duyệt phiếu của mình
- Chỉ cửa hàng trưởng mới thanh toán

---

## Migration

Chạy lệnh sau để tạo bảng mới:

```bash
python manage.py migrate products
```

Migration sẽ:
- Cập nhật PurchaseRequest.Status (thêm SHIPPED, IN_CHECKING, CHECKED)
- Tạo bảng InventoryCheck
- Tạo bảng InventoryCheckItem
- Tạo bảng PaymentVoucher
- Thêm permissions mới

---

## Ví Dụ Thực Tế

### Scenario: Đặt hàng 100 đôi giày từ NCC A

1. **Tạo PR**: Cửa hàng trưởng tạo đợt yêu cầu 100 đôi Nike Air Max
2. **Báo giá**: NCC A báo giá 800,000₫/đôi
3. **Duyệt**: Chọn NCC A
4. **Giao hàng**: NCC A giao hàng, xác nhận → Tạo phiếu kiểm kê
5. **Kiểm kê**: Nhân viên kiểm đếm thực tế chỉ nhận được 98 đôi
   - ordered_qty: 100
   - received_qty: 98
   - is_matched: False
   - note: "Thiếu 2 đôi size 42"
6. **Duyệt**: Cửa hàng trưởng duyệt với 98 đôi
   - Cộng tồn kho: +98 đôi
   - Tạo phiếu chi: 98 × 800,000 = 78,400,000₫
7. **Thanh toán**: Chuyển khoản 78,400,000₫ cho NCC A
   - Ghi nhận payment_ref
   - PR status → RECEIVED (Hoàn thành)

---

## API Endpoints Summary

| Chức năng | URL | Method | Permission |
|-----------|-----|--------|------------|
| Danh sách phiếu kiểm kê | `/supply/inventory-checks/` | GET | Store Manager hoặc Checker |
| Chi tiết phiếu kiểm kê | `/supply/inventory-checks/{pk}/` | GET | Store Manager hoặc Checker |
| Thực hiện kiểm kê | `/supply/inventory-checks/{pk}/perform/` | GET/POST | Checker |
| Duyệt phiếu kiểm kê | `/supply/inventory-checks/{pk}/approve/` | GET/POST | Store Manager |
| Danh sách phiếu chi | `/supply/payment-vouchers/` | GET | Store Manager |
| Chi tiết phiếu chi | `/supply/payment-vouchers/{pk}/` | GET | Store Manager |
| Thanh toán | `/supply/payment-vouchers/{pk}/mark-paid/` | GET/POST | Store Manager |

---

## Kết Luận

Flow kiểm kê hàng giúp:

✅ **Kiểm soát chặt chẽ** quá trình nhập hàng
✅ **Tránh sai sót** số lượng và giá cả
✅ **Truy vết đầy đủ** mọi thao tác
✅ **Tự động hóa** cộng tồn kho và thanh toán
✅ **Phân quyền rõ ràng** giữa các vai trò

Hệ thống đảm bảo tính toàn vẹn dữ liệu và minh bạch trong toàn bộ quy trình từ đặt hàng đến thanh toán.
