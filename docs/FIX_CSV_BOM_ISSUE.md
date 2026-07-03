# Fix: CSV BOM Character Issue

## Vấn Đề

**Triệu chứng**: File CSV có giá hợp lệ nhưng hệ thống báo "0/3 mặt hàng có giá"

**File CSV mẫu**:
```csv
Ma SP,Ten san pham,...
81,Converse Chuck Taylor 801,...,4000,...
66,Puma Dunk 496,...,3000,...
178,Jordan Old Skool 371,...,10900,...
```

**Nguyên nhân**:
- Ký tự **BOM (Byte Order Mark)** `` xuất hiện ở đầu **MỖI DÒNG**, không chỉ đầu file
- BOM trong giá trị: `81` thay vì `81`
- Khi parse: `int('81')` → **ValueError** → skip dòng

## Root Cause Analysis

### BOM là gì?
- **BOM (Byte Order Mark)**: Ký tự đặc biệt `U+FEFF` ở đầu file UTF-8
- Thường gặp khi export CSV từ Excel trên Windows
- Trong UTF-8: `\ufeff` hoặc bytes `\xef\xbb\xbf`

### Tại sao xuất hiện ở mỗi dòng?
1. Excel export CSV với BOM ở đầu file
2. Khi copy-paste hoặc edit file, BOM có thể bị nhân bản
3. Một số editor/tool không xử lý BOM đúng cách
4. Kết quả: BOM xuất hiện ở đầu nhiều dòng, không chỉ dòng đầu

## Cách Khắc Phục

### 1. Backend: Clean BOM ở cả file và từng dòng

**File**: `apps/products/supply_views.py`

```python
# Step 1: Decode with utf-8-sig (removes BOM from start of file)
content = csv_file.read().decode('utf-8-sig')

# Step 2: Remove any stray BOM characters in the content
content = content.replace('\ufeff', '').replace('\xef\xbb\xbf', '')

reader = csv.DictReader(io.StringIO(content))

# Step 3: Clean BOM from individual values
for row in reader:
    # Remove BOM from Mã SP value
    raw_vid = str(row.get('Ma SP', '0')).strip()
    raw_vid = raw_vid.lstrip('\ufeff').lstrip('\xef\xbb\xbf')

    # Validate before parsing
    if not raw_vid or not raw_vid.isdigit():
        skipped_variants.append(
            f"Dòng có Mã SP không hợp lệ: '{row.get('Ma SP', '')}' "
            f"(sau khi clean: '{raw_vid}')"
        )
        continue

    vid = int(raw_vid)
```

### 2. Debug Logging

Thêm logging để hiển thị giá trị trước và sau khi clean:

```python
if not raw_vid or not raw_vid.isdigit():
    skipped_variants.append(
        f"Dòng có Mã SP không hợp lệ: '{row.get('Ma SP', '')}' "
        f"(sau khi clean: '{raw_vid}')"
    )
```

## Testing

### Test Case 1: File CSV có BOM ở đầu file
```csv
Ma SP,Don gia bao
81,4000
66,3000
178,10900
```
**Expected**: ✅ 3/3 mặt hàng (BOM đầu file được xử lý bởi utf-8-sig)

### Test Case 2: File CSV có BOM ở mỗi dòng (như trường hợp này)
```csv
Ma SP,Don gia bao
81,4000
66,3000
178,10900
```
**Expected**: ✅ 3/3 mặt hàng (BOM mỗi dòng được clean bằng replace + lstrip)

### Test Case 3: File CSV clean (không có BOM)
```csv
Ma SP,Don gia bao
81,4000
66,3000
178,10900
```
**Expected**: ✅ 3/3 mặt hàng (hoạt động bình thường)

## Prevention - Hướng Dẫn Người Dùng

### Cách tạo file CSV đúng

#### Option 1: Sử dụng file từ hệ thống (Khuyến nghị)
```
1. Nhấn "Tải CSV mẫu" từ trang báo giá
2. Mở bằng Excel hoặc LibreOffice
3. Điền giá
4. Save (giữ nguyên định dạng CSV UTF-8)
5. Upload
```

#### Option 2: Tạo file mới
```
1. Tạo file .csv bằng Notepad hoặc VS Code
2. Encoding: UTF-8 WITHOUT BOM
3. Không dùng Excel để tạo file mới (dễ thêm BOM)
```

#### Option 3: Clean BOM từ file Excel
```
1. Mở file CSV bằng Notepad++
2. Encoding → Convert to UTF-8 without BOM
3. Save
4. Upload
```

### ⚠️ Tránh các thao tác gây BOM

❌ **Không nên**:
- Copy-paste dữ liệu từ Excel sang Excel khác
- Mở CSV bằng Excel rồi Save lại nhiều lần
- Edit CSV bằng Notepad trên Windows (có thể thêm BOM)

✅ **Nên**:
- Luôn dùng file CSV mẫu từ hệ thống
- Chỉ sửa cột "Don gia bao" và các cột NCC điền
- KHÔNG sửa cột "Ma SP"

## Technical Details

### BOM Representations

| Format | Hex | Unicode | Python String |
|--------|-----|---------|---------------|
| UTF-8 BOM | EF BB BF | U+FEFF | `\ufeff` |
| UTF-8 BOM (bytes) | \xef\xbb\xbf | U+FEFF | `b'\xef\xbb\xbf'` |

### Python Handling

```python
# Method 1: decode with 'utf-8-sig' (removes leading BOM)
content = file.read().decode('utf-8-sig')

# Method 2: Manual replacement (removes all BOM)
content = content.replace('\ufeff', '')
content = content.replace('\xef\xbb\xbf', '')

# Method 3: lstrip on individual strings
value = value.lstrip('\ufeff').lstrip('\xef\xbb\xbf')
```

### Why Both Methods?

1. **utf-8-sig**: Removes BOM from **start of file** only
2. **replace()**: Removes BOM from **anywhere** in content
3. **lstrip()**: Removes BOM from **start of each value**

We use all three to be thorough!

## Related Issues

### Similar Symptoms
- "Không đọc được file CSV"
- "Tất cả dòng bị skip"
- "ValueError when parsing ID"
- "Invalid column name" (if BOM in header)

### When to Suspect BOM Issue?
- File export từ Excel trên Windows
- Dòng đầu tiên bị skip nhưng các dòng sau OK
- TẤT CẢ dòng bị skip
- Error message: `'81' cannot be converted to int`

## Rollout

### ✅ Completed
1. Add comprehensive BOM cleaning in submit_quote()
2. Clean at file level (replace)
3. Clean at value level (lstrip)
4. Add debug logging for invalid IDs
5. Update documentation

### 🔄 Recommended Next Steps
1. Add BOM detection warning in UI
2. Show "File có ký tự BOM" warning before processing
3. Auto-clean BOM in JavaScript preview
4. Add tooltip: "Nếu file từ Excel, hãy kiểm tra encoding"

## Summary

**Problem**: BOM characters `` in CSV values prevent ID parsing

**Solution**:
1. Decode with `utf-8-sig` (removes leading BOM)
2. Replace all BOM in content
3. Strip BOM from individual values
4. Add validation and logging

**Impact**:
- ✅ Handles CSV from Excel on Windows
- ✅ Handles BOM at file start
- ✅ Handles BOM at line start
- ✅ Clear error messages for debugging

**Status**: ✅ FIXED

---

**Test với file CSV thực tế**:
- File: `PR1337F160-yeu-cau.csv`
- Variant IDs: 81, 66, 178 (có BOM prefix: `81`, `66`, `178`)
- Prices: 4000, 3000, 10900
- **Result**: ✅ Đã fix, giờ parse được hết
