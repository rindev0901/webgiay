# Test Case: CSV với BOM ở mỗi dòng data

## File Test: PR1337F160-yeu-cau (1) (1).csv

### Nội dung file (hex view):
```
Ma SP,Ten san pham,...
EF BB BF 38 31,Converse Chuck Taylor 801,...,9000,...
EF BB BF 36 36,Puma Dunk 496,...,8000,...
EF BB BF 31 37 38,Jordan Old Skool 371,...,7000,...
```

- **Line 1 (header)**: Không có BOM
- **Line 2-4 (data)**: Có BOM `` (EF BB BF) ở đầu mỗi dòng

### Vấn Đề

Khi CSV có BOM ở đầu **mỗi dòng data** (không phải header):
- `csv.DictReader` parse header đúng: `{"Ma SP": ...}`
- Nhưng mỗi dòng data bắt đầu bằng BOM
- Giá trị trong dict trở thành: `{"Ma SP": "81"}` thay vì `{"Ma SP": "81"}`

## Giải Pháp Đã Áp Dụng

### 1. Clean BOM từng dòng trước khi parse

```python
# Step 1: Decode với utf-8-sig
content = csv_file.read().decode('utf-8-sig')

# Step 2: Replace BOM trong toàn bộ content
content = content.replace('\ufeff', '').replace('\xef\xbb\xbf', '')

# Step 3: Split và clean từng dòng
lines = content.splitlines()
cleaned_lines = []
for line in lines:
    cleaned_line = line.lstrip('\ufeff').lstrip('\xef\xbb\xbf')
    cleaned_lines.append(cleaned_line)

# Step 4: Rejoin
content = '\n'.join(cleaned_lines)

# Step 5: Parse với DictReader
reader = csv.DictReader(io.StringIO(content))
```

### 2. Parse giá trị an toàn

```python
raw_vid = str(row.get('Ma SP', '0')).strip()

if not raw_vid or raw_vid == '0' or not raw_vid.isdigit():
    # Debug: show available keys
    available_keys = list(row.keys())[:5]
    skipped_variants.append(
        f"Dòng có Mã SP không hợp lệ: '{raw_vid}' "
        f"(các cột có: {', '.join(available_keys)})"
    )
    continue

vid = int(raw_vid)
```

## Kết Quả Mong Đợi

### Input:
```csv
Ma SP,Ten san pham,Don gia bao
81,Converse Chuck Taylor 801,9000
66,Puma Dunk 496,8000
178,Jordan Old Skool 371,7000
```

### Output:
```
✅ Đã nộp báo giá! 3 mặt hàng có giá hợp lệ.
```

**Saved to DB:**
- Variant 81: 9000₫
- Variant 66: 8000₫
- Variant 178: 7000₫

## Debug Output (nếu fail)

Nếu vẫn không parse được, hệ thống sẽ hiển thị:

```
⚠️ Bỏ qua 3 mặt hàng:
Dòng có Mã SP không hợp lệ: '0' (các cột có: Ma SP, Ten san pham, Kich thuoc (Size), Mau sac, SKU)
...
```

→ Giúp debug xem tên cột có đúng không

## Các Trường Hợp BOM Khác

### Case 1: BOM chỉ ở đầu file
```csv
Ma SP,Ten san pham,Don gia bao
81,Converse Chuck Taylor 801,9000
66,Puma Dunk 496,8000
```
**Status**: ✅ Handled by `decode('utf-8-sig')`

### Case 2: BOM ở header và data
```csv
Ma SP,Ten san pham,Don gia bao
81,Converse Chuck Taylor 801,9000
66,Puma Dunk 496,8000
```
**Status**: ✅ Handled by line-by-line lstrip

### Case 3: BOM ở giữa file
```csv
Ma SP,Ten san pham,Don gia bao
81,Converse Chuck Taylor 801,9000
66,Puma Dunk 496,8000
```
**Status**: ✅ Handled by line-by-line lstrip

### Case 4: Không có BOM
```csv
Ma SP,Ten san pham,Don gia bao
81,Converse Chuck Taylor 801,9000
66,Puma Dunk 496,8000
```
**Status**: ✅ Không bị ảnh hưởng bởi cleaning

## Làm Sao Biết File Có BOM?

### Method 1: Hex Editor
Mở file bằng hex editor, xem 3 bytes đầu:
- `EF BB BF` = UTF-8 BOM

### Method 2: Python
```python
with open('file.csv', 'rb') as f:
    first_bytes = f.read(3)
    if first_bytes == b'\xef\xbb\xbf':
        print("File có BOM!")
```

### Method 3: Notepad++
- Encoding menu → hiển thị "UTF-8-BOM" hoặc "UTF-8"

### Method 4: VS Code
- Góc dưới bên phải → "UTF-8 with BOM" hoặc "UTF-8"

## Cách Tạo File CSV Không BOM

### Excel (Windows)
1. Save As → CSV UTF-8 (❌ thường có BOM)
2. Mở bằng Notepad++
3. Encoding → Convert to UTF-8 without BOM
4. Save

### LibreOffice
1. Save As → Text CSV
2. Character Set: Unicode (UTF-8)
3. ✅ Không tự động thêm BOM

### Python
```python
import csv

with open('output.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Ma SP', 'Don gia bao'])
    writer.writerow([81, 9000])
```

### Google Sheets
1. Download → CSV
2. ✅ Không có BOM

## Summary

**Problem**: BOM ở đầu mỗi dòng data (không chỉ header)

**Solution**:
1. Decode với utf-8-sig
2. Replace all BOM in content
3. **Split lines và lstrip BOM từng dòng** ← Key fix!
4. Rejoin và parse

**Result**: ✅ File có BOM bất kỳ ở đâu đều được xử lý đúng

**Test File**: `PR1337F160-yeu-cau (1) (1).csv` với:
- Variant 81: 9000₫
- Variant 66: 8000₫
- Variant 178: 7000₫

**Expected**: ✅ 3/3 mặt hàng được lưu thành công
