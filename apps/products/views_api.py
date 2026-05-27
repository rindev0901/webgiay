from rest_framework import viewsets, filters
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Product, Category, Brand
from .serializers import ProductSerializer, CategorySerializer, BrandSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_active=True)\
        .select_related('category', 'brand')\
        .prefetch_related('variants', 'images')
    
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug', 'brand__slug', 'featured']
    search_fields = ['name', 'description', 'brand__name', 'category__name']
    ordering_fields = ['price', 'created_at', 'discount_price']
    ordering = ['-created_at']


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'