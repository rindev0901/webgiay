# Fix: CSV Quote Validation - "0/3 mặt hàng có giá"

## Vấn Đề

**Triệu chứng**: NCC upload file CSV với giá báo hợp lệ (4.000₫, 3.000₫, 10.900₫), nhưng hệ thống hiển thị "0/3 mặt hàng có giá".

**Nguyên nhân gốc rễ**:
- Client-side validation (JavaScript) chỉ kiểm tra cấu trúc CSV và giá trị hợp lệ
- Backend validation không kiểm tra Mã SP có thuộc Purchase Request hay không
- CSV chứa Mã SP (81, 66, 178) không khớp với các Mã SP trong Purchase Request

## Cách Khắc Phục

### 1. Backend Validation Enhancement

**File**: `d:\Workspace\webgiay\apps\products\supply_views.py`

**Thay đổi trong hàm `submit_quote()`**:

```python
# Build a map of valid variant IDs from the purchase request
valid_variant_ids = set(pr.items.values_list('variant_id', flat=True))

for row in reader:
    try:
        vid = int(row.get('Ma SP', 0))

        # ✅ NEW: Check if variant ID is part of this purchase request
        if vid not in valid_variant_ids:
            skipped_variants.append(
                f"ID {vid} không thuộc yêu cầu này "
                f"(các ID hợp lệ: {', '.join(map(str, sorted(valid_variant_ids)))})"
            )
            continue

        # ... rest of validation
```

**Kết quả**:
- Bây giờ backend sẽ kiểm tra Mã SP có thuộc Purchase Request không
- Nếu không khớp → skip và hiển thị thông báo chi tiết
- Hiển thị danh sách Mã SP hợp lệ trong thông báo lỗi

### 2. Improved Error Messages

**Trước**:
```
⚠️ Bỏ qua 3 mặt hàng: ID 81 không tồn tại, ID 66 không tồn tại, ID 178 không tồn tại
```

**Sau**:
```
❌ Không có mặt hàng nào được lưu!
Các Mã SP hợp lệ cho đợt này: 10, 15, 20

⚠️ Bỏ qua 3 mặt hàng:
ID 81 không thuộc yêu cầu này (các ID hợp lệ: 10, 15, 20)
ID 66 không thuộc yêu cầu này (các ID hợp lệ: 10, 15, 20)
ID 178 không thuộc yêu cầu này (các ID hợp lệ: 10, 15, 20)
```

### 3. Documentation

Tạo file hướng dẫn cho người dùng:
- `docs/LOI_BAO_GIA_CSV.md`: Giải thích lỗi và cách khắc phục
- Hướng dẫn NCC tải đúng file CSV từ đúng đợt yêu cầu
- Cảnh báo KHÔNG sửa cột "Ma SP"

## Nguyên Nhân Lỗi Thường Gặp

### 1. Tải CSV từ sai đợt yêu cầu
```
❌ Tải CSV từ PR-001 nhưng upload vào PR-002
✅ Luôn tải CSV từ trang báo giá của đúng đợt
```

### 2. Chỉnh sửa cột "Ma SP"
```
❌ NCC thay đổi Mã SP để khớp với sản phẩm họ có
✅ KHÔNG được sửa cột "Ma SP", chỉ báo giá cho các SP trong yêu cầu
```

### 3. Copy-paste sai
```
❌ Copy data từ file Excel khác vào CSV
✅ Luôn dùng file CSV mẫu từ hệ thống
```

## Testing Checklist

### Test Case 1: CSV với Mã SP đúng
```csv
Ma SP,Don gia bao
10,850000
15,750000
20,650000
```
**Expected**: ✅ 3/3 mặt hàng có giá

### Test Case 2: CSV với Mã SP sai
```csv
Ma SP,Don gia bao
81,4000
66,3000
178,10900
```
**Expected**: ❌ 0/3 mặt hàng có giá + Thông báo lỗi với danh sách Mã SP hợp lệ

### Test Case 3: CSV trộn lẫn
```csv
Ma SP,Don gia bao
10,850000
81,4000
15,750000
```
**Expected**: ✅ 2/3 mặt hàng có giá + ⚠️ Bỏ qua ID 81

### Test Case 4: CSV thiếu giá
```csv
Ma SP,Don gia bao
10,850000
15,
20,650000
```
**Expected**: ✅ 2/3 mặt hàng có giá + ⚠️ Bỏ qua ID 15 (không có giá)

## Flow Validation

### Client-side (JavaScript)
```javascript
// Check 1: Mã SP có trong requestedMap?
if (!requestedMap[variantId]) {
    status = 'error';
    message = 'Mã SP không thuộc yêu cầu';
}

// Check 2: Giá có hợp lệ?
if (isNaN(unitPrice) || unitPrice <= 0) {
    status = 'error';
    message = 'Đơn giá báo trống hoặc không hợp lệ';
}
```

### Backend (Python)
```python
# Check 1: Mã SP có trong Purchase Request?
if vid not in valid_variant_ids:
    skipped_variants.append(...)
    continue

# Check 2: Variant có tồn tại trong DB?
v = ProductVariant.objects.filter(pk=vid).first()
if not v:
    skipped_variants.append(...)
    continue

# Check 3: Giá có hợp lệ?
if unit_price <= 0:
    skipped_variants.append(...)
    continue

# ✅ All checks passed → Save
SupplierQuoteItem.objects.create(...)
```

## Rollout Plan

### Phase 1: Backend Fix (Immediate)
- ✅ Add validation in `submit_quote()`
- ✅ Improve error messages
- ✅ Show valid variant IDs in error

### Phase 2: Documentation (Immediate)
- ✅ Create `LOI_BAO_GIA_CSV.md`
- ✅ Create `FIX_CSV_VALIDATION.md`
- Share with support team

### Phase 3: User Communication (Next)
- Send email to all suppliers
- Add warning banner on quote submission page
- Add tooltip on "Tải CSV mẫu" button

### Phase 4: UI Enhancement (Future)
- Show expected Mã SP list on quote page
- Add real-time CSV validation before upload
- Show preview of CSV data before submit

## Related Files

```
d:\Workspace\webgiay\apps\products\supply_views.py
  └─ submit_quote() function (line ~900-1000)

d:\Workspace\webgiay\templates\supply\submit_quote.html
  └─ Client-side CSV validation (JavaScript)

d:\Workspace\webgiay\docs\LOI_BAO_GIA_CSV.md
  └─ User documentation (NEW)

d:\Workspace\webgiay\docs\HUONG_DAN_KIEM_KE.md
  └─ Complete flow documentation
```

## Summary

**Root Cause**: Backend không validate Mã SP có thuộc Purchase Request

**Solution**:
1. Add validation `vid not in valid_variant_ids`
2. Show helpful error with valid IDs
3. Document the issue for users

**Impact**:
- ✅ Prevent wrong CSV upload
- ✅ Clear error messages
- ✅ Faster troubleshooting
- ✅ Better user experience

**Status**: ✅ FIXED
