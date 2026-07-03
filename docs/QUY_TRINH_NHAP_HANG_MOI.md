# Quy trình nhập hàng từ NCC (Sau cập nhật)

## 📋 Tổng quan quy trình mới

Quy trình nhập hàng từ nhà cung cấp (NCC) đã được cải tiến để đảm bảo kiểm soát chặt chẽ hơn:

1. ✅ **CHT duyệt báo giá** → Tự động tạo phiếu kiểm kê
2. 📦 **Nhân viên kiểm kê** → Kiểm tra và nhập số lượng thực nhận
3. ✅ **CHT duyệt phiếu kiểm kê** → Tự động tạo phiếu chi tiền
4. 📥 **CHT cộng tồn kho** → Nhấn nút "Cộng tồn kho" trong chi tiết phiếu kiểm kê
5. 💰 **CHT thanh toán** → Xác nhận đã chi tiền cho NCC

---

## 🔄 Chi tiết từng bước

### Bước 1: CHT duyệt báo giá từ NCC

**Vai trò:** Cửa hàng trưởng (CHT)

**Hành động:**
1. Xem các báo giá từ NCC trong chi tiết đợt đặt hàng
2. So sánh giá và chọn NCC phù hợp
3. Nhấn **"Duyệt NCC tốt nhất"**

**Kết quả:**
- ✅ NCC được chọn và đợt đặt hàng chuyển sang trạng thái "Đã duyệt NCC"
- 📋 **Hệ thống tự động tạo phiếu kiểm kê** với:
  - Danh sách sản phẩm cần kiểm
  - Số lượng đã đặt
  - Đơn giá từ báo giá đã duyệt
- ⚠️ **Lưu ý:** Hàng chưa được cộng vào kho, phải đợi duyệt phiếu kiểm kê

---

### Bước 2: Nhân viên thực hiện kiểm kê

**Vai trò:** Nhân viên có quyền kiểm kê

**Hành động:**
1. Vào **"Phiếu kiểm kê"** → Chọn phiếu cần kiểm (trạng thái "Chờ kiểm tra")
2. Nhấn **"Thực hiện kiểm kê"**
3. Nhập số lượng thực nhận cho từng sản phẩm
4. Ghi chú nếu có sai lệch
5. Nhấn **"Hoàn thành kiểm kê"**

**Kết quả:**
- ✅ Phiếu kiểm kê chuyển sang trạng thái "Hoàn thành"
- 📊 Hệ thống tính tổng tiền cần thanh toán cho NCC
- ⏳ Chờ CHT duyệt phiếu kiểm kê

---

### Bước 3: CHT duyệt phiếu kiểm kê

**Vai trò:** Cửa hàng trưởng (CHT)

**Hành động:**
1. Vào **"Phiếu kiểm kê"** → Chọn phiếu "Hoàn thành"
2. Xem chi tiết: số lượng đặt vs thực nhận, tổng tiền
3. Nhấn **"Duyệt phiếu kiểm kê"**

**Kết quả tự động:**
- ✅ Phiếu kiểm kê được duyệt
- 💰 **Tự động tạo phiếu chi tiền** cho NCC
- 🔄 Đợt đặt hàng chuyển sang "Đã kiểm kê"
- ⚠️ **Lưu ý:** Hàng CHƯA được cộng vào kho, CHT cần cộng thủ công

---

### Bước 4: CHT cộng tồn kho

**Vai trò:** Cửa hàng trưởng (CHT)

**Hành động:**
1. Vào chi tiết phiếu kiểm kê đã duyệt
2. Nhấn nút **"Cộng tồn kho"** (trên đầu trang)
3. Một popup hiện ra với danh sách sản phẩm và số lượng
4. Xem lại: Tồn hiện tại → SL nhận → Tồn sau cộng
5. Nhấn **"Xác nhận cộng tồn kho"**

**Kết quả:**
- 📦 Hàng được cộng vào kho theo số lượng thực nhận
- ✅ Tồn kho cập nhật chính xác
- 📝 Hệ thống ghi nhận lịch sử thay đổi tồn kho
- ✅ Nút "Cộng tồn kho" chuyển thành badge "Đã cộng tồn kho"

---

### Bước 5: CHT thanh toán cho NCC

**Vai trò:** Cửa hàng trưởng (CHT)

**Hành động:**
1. Vào **"Phiếu chi tiền NCC"**
2. Chọn phiếu cần thanh toán (trạng thái "Chờ thanh toán")
3. Nhập thông tin:
   - Phương thức thanh toán (Chuyển khoản, Tiền mặt...)
   - Mã tham chiếu (nếu có)
   - Ghi chú
4. Nhấn **"Xác nhận đã thanh toán"**

**Kết quả:**
- ✅ Phiếu chi chuyển sang "Đã thanh toán"
- ✅ Đợt đặt hàng hoàn thành (trạng thái "Đã nhận hàng & thanh toán")

---

## 🔐 Phân quyền

| Vai trò | Quyền hạn |
|---------|-----------|
| **Cửa hàng trưởng (CHT)** | - Duyệt báo giá<br>- Duyệt phiếu kiểm kê<br>- Thanh toán cho NCC |
| **Nhân viên kiểm kê** | - Thực hiện kiểm kê hàng<br>- Cập nhật số lượng thực nhận |
| **Nhà cung cấp (NCC)** | - Xem yêu cầu đặt hàng<br>- Nộp báo giá |

---

## 🎯 Lợi ích của quy trình mới

✅ **Kiểm soát chặt chẽ hơn:**
- Phải kiểm kê và duyệt mới được tạo phiếu chi
- CHT chủ động cộng tồn kho khi đã chắc chắn
- Tránh nhập sai hàng hoặc sai số lượng

✅ **Tự động hóa phù hợp:**
- Tự động tạo phiếu kiểm kê khi duyệt báo giá
- Tự động tạo phiếu chi khi duyệt phiếu kiểm kê
- CHT linh hoạt trong việc cộng tồn kho

✅ **Truy xuất nguồn gốc:**
- Mỗi giao dịch có phiếu kiểm kê và phiếu chi tương ứng
- Dễ dàng đối chiếu và báo cáo

---

## ⚠️ Lưu ý quan trọng

1. **Không thể bỏ qua bước kiểm kê:** Phải kiểm kê và duyệt phiếu kiểm kê mới có thể tạo phiếu chi tiền

2. **Phiếu chi được tạo tự động:** Khi duyệt phiếu kiểm kê, hệ thống sẽ tự động tạo phiếu chi tiền cho NCC

3. **Cộng tồn kho qua giao diện:** CHT cần nhấn nút "Cộng tồn kho" trong chi tiết phiếu kiểm kê đã duyệt để cộng hàng vào kho

4. **Không thể sửa sau khi duyệt:** Sau khi duyệt phiếu kiểm kê, không thể chỉnh sửa. Nếu sai sót, cần tạo phiếu điều chỉnh riêng.

5. **Không thể cộng kho 2 lần:** Sau khi cộng tồn kho, hệ thống sẽ không cho phép cộng lại để tránh sai sót

4. **Quy trình cũ:** Các đơn hàng cũ (trước bản cập nhật) có thể chưa có phiếu kiểm kê. CHT cần duyệt lại báo giá để tạo phiếu kiểm kê tự động.

---

## 📱 Truy cập nhanh

- **Biên độ tồn kho:** `/supply/`
- **Đợt yêu cầu đặt hàng:** `/supply/requests/`
- **Phiếu kiểm kê:** `/supply/inventory-checks/`
- **Phiếu chi tiền NCC:** `/supply/payment-vouchers/`

---

*Cập nhật lần cuối: {{ current_date }}*
