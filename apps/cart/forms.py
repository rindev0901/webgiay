from django import forms


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        label='Họ và tên',
        max_length=120,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded', 'placeholder': 'Nguyễn Văn A'}),
    )
    phone = forms.CharField(
        label='Số điện thoại',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded', 'placeholder': '09xxxxxxxx'}),
    )
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'w-full px-3 py-2 border rounded', 'placeholder': 'you@example.com'}),
    )
    address = forms.CharField(
        label='Địa chỉ giao hàng',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded', 'placeholder': 'Số nhà, đường, phường/xã, quận/huyện, tỉnh/thành'}),
    )
    note = forms.CharField(
        label='Ghi chú',
        required=False,
        widget=forms.Textarea(attrs={'class': 'w-full px-3 py-2 border rounded', 'rows': 4, 'placeholder': 'Ví dụ: giao giờ hành chính...'}),
    )
