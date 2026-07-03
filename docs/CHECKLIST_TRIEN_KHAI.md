# ✅ Checklist Triển Khai: Quy Trình Nhập Hàng Mới

## 📋 Trước khi triển khai

- [ ] Đọc tài liệu `QUY_TRINH_NHAP_HANG_MOI.md`
- [ ] Đọc tài liệu `THAY_DOI_QUY_TRINH_NHAP_HANG.md`
- [ ] Backup database hiện tại
- [ ] Thông báo cho toàn bộ nhân viên về thay đổi quy trình

---

## 🔧 Triển khai

### 1. Kiểm tra code

- [x] File `supply_views.py` đã được cập nhật
- [x] File `supply_models.py` đã được cập nhật
- [x] Template `request_detail.html` đã được cập nhật
- [x] Template `approve_inventory_check.html` đã được cập nhật
- [x] Kiểm tra syntax Python (không có lỗi)

### 2. Kiểm tra dependencies

- [ ] Hàm `adjust_stock()` đã tồn tại trong `inventory.py`
- [ ] Model `InventoryCheck` đã có field `approved_by`, `approved_at`
- [ ] Model `PaymentVoucher` đã tồn tại và có đầy đủ field cần thiết

### 3. Deploy

- [ ] Pull code mới nhất về server
- [ ] Restart Django application
- [ ] Kiểm tra logs không có lỗi

---

## 🧪 Kiểm tra sau khi triển khai

### Test Case 1: Duyệt báo giá
- [ ] Tạo đợt yêu cầu đặt hàng mới
- [ ] Gửi yêu cầu cho NCC
- [ ] NCC nộp báo giá
- [ ] CHT duyệt báo giá
- [ ] **Kiểm tra:** Phiếu kiểm kê có được tạo tự động không?
- [ ] **Kiểm tra:** Các item trong phiếu kiểm kê có đúng số lượng và giá không?
- [ ] **Kiểm tra:** Có chuyển hướng đến trang chi tiết phiếu kiểm kê không?

### Test Case 2: Kiểm kê hàng
- [ ] Nhân viên vào phiếu kiểm kê
- [ ] Nhập số lượng thực nhận (khác với số lượng đặt)
- [ ] Hoàn thành kiểm kê
- [ ] **Kiểm tra:** Tổng tiền có được tính đúng không?
- [ ] **Kiểm tra:** Trạng thái chuyển sang "Hoàn thành"?

### Test Case 3: Duyệt phiếu kiểm kê
- [ ] CHT vào duyệt phiếu kiểm kê
- [ ] Nhấn "Duyệt phiếu kiểm kê"
- [ ] **Kiểm tra:** Phiếu chi tiền có được tạo không?
- [ ] **Kiểm tra:** Số tiền trong phiếu chi có đúng với tổng tiền phiếu kiểm kê không?
- [ ] **Kiểm tra:** Có chuyển hướng đến trang phiếu chi tiền không?
- [ ] **Kiểm tra quan trọng:** Tồn kho CHƯA thay đổi (vì phải nhập thủ công)

### Test Case 4: CHT cộng tồn kho thủ công
- [ ] CHT vào chi tiết phiếu kiểm kê đã duyệt
- [ ] Cộng tồn kho thủ công cho từng sản phẩm theo số lượng thực nhận
- [ ] **Kiểm tra:** Tồn kho có tăng đúng số lượng không?

### Test Case 5: Thanh toán NCC
- [ ] CHT vào phiếu chi tiền
- [ ] Nhập thông tin thanh toán
- [ ] Xác nhận đã thanh toán
- [ ] **Kiểm tra:** Trạng thái phiếu chi chuyển sang "Đã thanh toán"?
- [ ] **Kiểm tra:** Đợt đặt hàng chuyển sang "Đã nhận hàng & thanh toán"?

### Test Case 6: Từ chối phiếu kiểm kê
- [ ] Tạo một phiếu kiểm kê mới và hoàn thành kiểm kê
- [ ] CHT từ chối phiếu kiểm kê với lý do rõ ràng
- [ ] **Kiểm tra:** Tồn kho KHÔNG thay đổi
- [ ] **Kiểm tra:** KHÔNG tạo phiếu chi tiền
- [ ] **Kiểm tra:** Trạng thái đơn hàng quay về "Đã duyệt NCC"

### Test Case 7: Đơn hàng cũ (Backward Compatibility)
- [ ] Tìm một đơn hàng cũ có trạng thái "Đã duyệt NCC" từ trước bản cập nhật
- [ ] Vào chi tiết đơn hàng
- [ ] **Kiểm tra:** Có hiển thị thông báo yêu cầu duyệt lại không?
- [ ] Nhấn "Xem Phiếu Kiểm Kê" (nếu có)
- [ ] **Kiểm tra:** Có chuyển đúng đến phiếu kiểm kê không?

---

## 📊 Kiểm tra Database

### Kiểm tra PaymentVoucher
```sql
-- Xem các phiếu chi vừa tạo
SELECT
    pv.code,
    pv.amount,
    pv.status,
    s.name AS supplier,
    ic.code AS inventory_check_code
FROM products_paymentvoucher pv
JOIN products_supplier s ON pv.supplier_id = s.id
JOIN products_inventorycheck ic ON pv.inventory_check_id = ic.id
ORDER BY pv.created_at DESC
LIMIT 10;
```

### Kiểm tra InventoryCheck
```sql
-- Xem các phiếu kiểm kê mới nhất
SELECT
    ic.code,
    ic.status,
    pr.code AS purchase_request_code,
    ic.total_amount,
    ic.created_at
FROM products_inventorycheck ic
JOIN products_purchaserequest pr ON ic.purchase_request_id = pr.id
ORDER BY ic.created_at DESC
LIMIT 10;
```

---

## 👥 Đào tạo nhân viên

### Cửa hàng trưởng (CHT)
- [ ] Hướng dẫn quy trình duyệt báo giá mới
- [ ] Giải thích về việc phiếu kiểm kê được tạo tự động
- [ ] Hướng dẫn duyệt phiếu kiểm kê
- [ ] **Quan trọng:** Giải thích rõ phiếu chi được tạo tự động nhưng PHẢI cộng tồn kho thủ công
- [ ] Hướng dẫn cách cộng tồn kho thủ công từ phiếu kiểm kê
- [ ] Hướng dẫn thanh toán cho NCC

### Nhân viên kiểm kê
- [ ] Hướng dẫn cách vào phiếu kiểm kê
- [ ] Hướng dẫn nhập số lượng thực nhận
- [ ] Giải thích tầm quan trọng của việc nhập đúng số lượng
- [ ] Hướng dẫn ghi chú khi có sai lệch

---

## 📝 Tài liệu

- [ ] Cập nhật hướng dẫn sử dụng cho nhân viên
- [ ] Cập nhật FAQ về quy trình nhập hàng
- [ ] Tạo video hướng dẫn (nếu cần)
- [ ] Thông báo chính thức về thay đổi quy trình

---

## 🔍 Giám sát sau triển khai

### Tuần đầu tiên
- [ ] Theo dõi logs hàng ngày
- [ ] Kiểm tra tất cả phiếu kiểm kê được tạo
- [ ] Kiểm tra CHT đã cộng tồn kho thủ công đúng cách chưa
- [ ] Kiểm tra phiếu chi tiền có được tạo đúng không
- [ ] Thu thập feedback từ nhân viên về quy trình cộng tồn kho thủ công

### Tháng đầu tiên
- [ ] Tổng hợp các vấn đề phát sinh
- [ ] Điều chỉnh quy trình nếu cần
- [ ] Đào tạo bổ sung cho nhân viên
- [ ] Cập nhật tài liệu dựa trên feedback

---

## 🚨 Rollback Plan (Nếu cần)

Trong trường hợp gặp vấn đề nghiêm trọng:

1. [ ] Backup database hiện tại
2. [ ] Restore code version cũ
3. [ ] Restore database từ backup trước khi triển khai
4. [ ] Restart application
5. [ ] Thông báo cho nhân viên
6. [ ] Phân tích nguyên nhân và lập kế hoạch sửa lỗi

---

## ✅ Hoàn thành

- [ ] Tất cả test case đã pass
- [ ] Nhân viên đã được đào tạo
- [ ] Tài liệu đã được cập nhật
- [ ] Không có lỗi nghiêm trọng trong tuần đầu
- [ ] **Quy trình mới đã chính thức áp dụng!** 🎉

---

*Ngày triển khai: _______________*
*Người thực hiện: _______________*
*Người kiểm tra: _______________*
