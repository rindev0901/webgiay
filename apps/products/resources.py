from import_export import resources
from .models import Category, Brand, Product, ProductVariant, Size

class CategoryResource(resources.ModelResource):
    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'is_active')

class BrandResource(resources.ModelResource):
    class Meta:
        model = Brand
        fields = ('id', 'name', 'slug', 'description', 'is_active')

class ProductResource(resources.ModelResource):
    class Meta:
        model = Product
        fields = ('id', 'category', 'brand', 'name', 'slug', 'price', 'discount_price', 'is_active')

class SizeResource(resources.ModelResource):
    class Meta:
        model = Size
        fields = ('id', 'name', 'order')