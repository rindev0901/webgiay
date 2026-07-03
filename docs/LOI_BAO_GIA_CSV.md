# Hướng Dẫn Xử Lý Lỗi "0/3 mặt hàng có giá"

## Nguyên Nhân

Lỗi này xảy ra khi **Mã SP (variant ID)** trong file CSV không khớp với Mã SP trong đợt yêu cầu (Purchase Request).

### Ví dụ:

**Đợt yêu cầu PR-001 có các Mã SP:**
- 10, 15, 20

**File CSV bạn upload có các Mã SP:**
- 81, 66, 178

→ **Kết quả**: Hệ thống bỏ qua tất cả 3 dòng vì không khớp → "0/3 mặt hàng có giá"

## Cách Khắc Phục

### Bước 1: Kiểm Tra Mã SP Hợp Lệ

Khi upload CSV bị lỗi, hệ thống sẽ hiển thị thông báo lỗi bao gồm:
```
❌ Không có mặt hàng nào được lưu!
Các Mã SP hợp lệ cho đợt này: 10, 15, 20
```

### Bước 2: Tải Lại File CSV Đúng

**QUAN TRỌNG**: Luôn tải file CSV mẫu từ **đúng đợt yêu cầu** bạn muốn báo giá!

1. Vào trang nộp báo giá cho đợt cụ thể
2. Nhấn nút **"Tải CSV mẫu"**
3. File CSV sẽ chứa đúng các Mã SP của đợt đó

### Bước 3: Điền Giá Và Upload

1. Mở file CSV vừa tải
2. Điền giá vào cột **"Don gia bao"**
3. Điền số lượng còn vào cột **"So luong NCC con"** (optional)
4. Điền số ngày giao hàng vào cột **"So ngay giao hang"** (optional)
5. Upload lại file

## Lưu Ý Quan Trọng

### ⚠️ KHÔNG chỉnh sửa cột "Ma SP"

- Cột **"Ma SP"** là ID nội bộ của hệ thống
- KHÔNG được thay đổi hoặc xóa các giá trị trong cột này
- Chỉ điền giá và thông tin khác

### ⚠️ Mỗi đợt yêu cầu có file CSV riêng

- Mỗi Purchase Request có danh sách sản phẩm khác nhau
- File CSV của PR-001 không dùng được cho PR-002
- Luôn tải file CSV từ trang báo giá của đợt hiện tại

### ⚠️ Kiểm tra trước khi upload

Hệ thống sẽ hiển thị bảng kiểm tra với các thông tin:
- **Khớp & Hợp lệ**: Số mặt hàng có Mã SP đúng và có giá
- **Chưa Có Báo Giá**: Số mặt hàng trong yêu cầu nhưng chưa có trong CSV
- **Số Dòng Lỗi**: Số dòng có Mã SP không hợp lệ hoặc không khớp

Chỉ nhấn **"Gửi Hồ Sơ Báo Giá"** khi:
- ✅ Không có dòng lỗi (màu đỏ)
- ✅ Có ít nhất 1 mặt hàng khớp & hợp lệ (màu xanh)

## Ví Dụ File CSV Đúng

```csv
Ma SP,Ten san pham,Kich thuoc (Size),Mau sac,SKU,Ton kho hien tai,So luong yeu cau,Don gia bao,So luong NCC con,So ngay giao hang,Ghi chu
10,Nike Air Max,42,Đỏ,NIKE-AM-42-RED,5,20,850000,50,7,
15,Adidas Superstar,40,Trắng,ADIDAS-SS-40-WHT,3,15,750000,30,5,
20,Vans Old Skool,39,Đen,VANS-OS-39-BLK,0,25,650000,100,3,
```

**Giải thích**:
- Cột "Ma SP": Không được sửa (10, 15, 20)
- Cột "Don gia bao": NCC điền giá (850000, 750000, 650000)
- Cột "So luong NCC con": NCC điền số lượng còn (50, 30, 100)
- Cột "So ngay giao hang": NCC điền thời gian giao (7, 5, 3 ngày)

## Tổng Kết

### ✅ Quy Trình Đúng:
1. Vào trang báo giá của đợt cụ thể
2. Tải CSV mẫu từ trang đó
3. Điền giá (KHÔNG sửa Mã SP)
4. Kiểm tra trước khi upload
5. Chỉ gửi khi không có lỗi

### ❌ Nguyên Nhân Lỗi Thường Gặp:
- Tải CSV từ đợt khác
- Sửa/xóa cột "Ma SP"
- Copy-paste sai dữ liệu
- Upload nhầm file

---

**Hỗ trợ**: Nếu vẫn gặp lỗi sau khi làm theo hướng dẫn, vui lòng liên hệ quản trị viên và cung cấp:
1. Mã đợt yêu cầu (PR-XXXXXXXX)
2. File CSV bạn đang upload
3. Screenshot thông báo lỗi
