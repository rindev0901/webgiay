"""
Management command: seed_variants
----------------------------------
1. Tạo đầy đủ các Size giày phổ biến (35 → 46)
2. Với mỗi sản phẩm, tạo variants: mỗi màu × mỗi size
   - stock ngẫu nhiên 0-15 (một số size sẽ hết hàng để demo)
   - price kế thừa từ product.final_price

Cách dùng:
    python manage.py seed_variants                  # toàn bộ sản phẩm
    python manage.py seed_variants --product-id 5   # chỉ 1 sản phẩm
    python manage.py seed_variants --clear          # xóa variants cũ trước
"""
import random
from django.core.management.base import BaseCommand
from apps.products.models import Product, Color, Size, ProductVariant


# Danh sách size giày phổ biến: (name, order)
SIZES = [
    ("35",   0),
    ("35.5", 1),
    ("36",   2),
    ("36.5", 3),
    ("37",   4),
    ("37.5", 5),
    ("38",   6),
    ("38.5", 7),
    ("39",   8),
    ("39.5", 9),
    ("40",  10),
    ("40.5",11),
    ("41",  12),
    ("41.5",13),
    ("42",  14),
    ("42.5",15),
    ("43",  16),
    ("44",  17),
    ("45",  18),
    ("46",  19),
]

# Mỗi loại sản phẩm hiển thị range size hợp lý
# key: từ khóa trong tên sản phẩm (lowercase), value: (size_from, size_to)
BRAND_SIZE_RANGE = {
    "women": ("35", "40"),
    "nữ":    ("35", "40"),
    "gs":    ("35", "39"),   # Grade School
    "kid":   ("35", "38"),
    "men":   ("39", "46"),
    "nam":   ("39", "46"),
}
DEFAULT_SIZE_RANGE = ("35.5", "43")   # range mặc định nếu không match


def get_size_range(product_name: str):
    name_lower = product_name.lower()
    for keyword, rng in BRAND_SIZE_RANGE.items():
        if keyword in name_lower:
            return rng
    return DEFAULT_SIZE_RANGE


class Command(BaseCommand):
    help = "Seed Size master data và tạo ProductVariant cho tất cả sản phẩm"

    def add_arguments(self, parser):
        parser.add_argument(
            "--product-id", type=int, default=None,
            help="Chỉ seed variant cho 1 sản phẩm cụ thể"
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Xóa toàn bộ variants trước khi seed"
        )
        parser.add_argument(
            "--sizes-only", action="store_true",
            help="Chỉ tạo Size master data, không tạo variants"
        )

    def handle(self, *args, **options):
        # ── Step 1: Seed Size master data ──
        self.stdout.write("📐 Seeding Size master data...")
        created_sizes = 0
        for name, order in SIZES:
            _, created = Size.objects.get_or_create(
                name=name,
                defaults={"order": order}
            )
            if created:
                created_sizes += 1
            else:
                # Cập nhật order nếu đã tồn tại
                Size.objects.filter(name=name).update(order=order)

        self.stdout.write(self.style.SUCCESS(
            f"  ✓ {created_sizes} size mới / {len(SIZES)} tổng"
        ))

        if options["sizes_only"]:
            return

        # ── Step 2: Clear nếu được yêu cầu ──
        if options["clear"]:
            count = ProductVariant.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f"  🗑  Đã xóa {count} variants cũ"))

        # ── Step 3: Lấy data ──
        all_sizes = {s.name: s for s in Size.objects.all()}
        all_colors = list(Color.objects.all())

        if not all_colors:
            self.stdout.write(self.style.ERROR("❌ Chưa có màu sắc nào trong DB!"))
            return

        # ── Step 4: Chọn sản phẩm cần seed ──
        if options["product_id"]:
            products = Product.objects.filter(pk=options["product_id"])
            if not products.exists():
                self.stdout.write(self.style.ERROR(f"❌ Không tìm thấy sản phẩm ID={options['product_id']}"))
                return
        else:
            products = Product.objects.filter(is_active=True)

        self.stdout.write(f"🛍  Seeding variants cho {products.count()} sản phẩm...")

        total_created = 0
        total_skipped = 0

        for product in products:
            size_from, size_to = get_size_range(product.name)
            size_names = [s[0] for s in SIZES]

            # Lấy index range
            try:
                idx_from = size_names.index(size_from)
                idx_to   = size_names.index(size_to)
            except ValueError:
                idx_from, idx_to = 0, len(size_names) - 1

            product_sizes = [
                all_sizes[s[0]]
                for s in SIZES[idx_from:idx_to + 1]
                if s[0] in all_sizes
            ]

            # Chọn 1-2 màu ngẫu nhiên cho sản phẩm (realistic hơn)
            num_colors = random.randint(1, min(3, len(all_colors)))
            product_colors = random.sample(all_colors, num_colors)

            base_price = product.final_price

            for color in product_colors:
                for size in product_sizes:
                    # Stock: 70% có hàng, 30% hết
                    stock = random.randint(1, 15) if random.random() > 0.25 else 0

                    try:
                        _, created = ProductVariant.objects.get_or_create(
                            product=product,
                            size=size,
                            color=color,
                            defaults={
                                "stock": stock,
                                "price": base_price,
                                "is_active": True,
                            }
                        )
                        if created:
                            total_created += 1
                        else:
                            total_skipped += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f"  ⚠ Skip {product.name} - {size.name} - {color.name}: {e}")
                        )

            self.stdout.write(f"  ✓ {product.name[:50]}: {len(product_colors)} màu × {len(product_sizes)} size")

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Hoàn thành: {total_created} variants mới, {total_skipped} đã tồn tại"
        ))
