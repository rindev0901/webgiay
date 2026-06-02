"""Forms for product inventory management"""
from django import forms
from .models import ProductVariant


class BulkStockInForm(forms.Form):
    """Form để nhập kho hàng loạt cho nhiều biến thể"""
    
    product = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        label='Sản phẩm',
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'product-select'})
    )
    
    note = forms.CharField(
        label='Ghi chú',
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ví dụ: Nhập hàng từ nhà cung cấp ABC'
        })
    )
    
    def __init__(self, *args, **kwargs):
        from .models import Product
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True).order_by('name')


class VariantStockInlineForm(forms.Form):
    """Form inline cho từng biến thể trong quá trình nhập kho"""
    
    variant_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField(
        label='Số lượng nhập',
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'style': 'width: 100px;'
        })
    )
