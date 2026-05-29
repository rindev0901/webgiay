from django import forms


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        label='Họ và tên',
        max_length=120,
        widget=forms.TextInput(attrs={'class': 'input', 'placeholder': 'Nguyễn Văn A'}),
    )
    phone = forms.CharField(
        label='Số điện thoại',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'input', 'placeholder': '09xxxxxxxx'}),
    )
    email = forms.EmailField(
        label='Email',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'input', 'placeholder': 'you@example.com'}),
    )
    address = forms.CharField(
        label='Địa chỉ giao hàng',
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'input', 'placeholder': 'Số nhà, đường, phường/xã, quận/huyện, tỉnh/thành'}),
    )
    note = forms.CharField(
        label='Ghi chú',
        required=False,
        widget=forms.Textarea(attrs={'class': 'input', 'rows': 4, 'placeholder': 'Ví dụ: giao giờ hành chính...'}),
    )

    province = forms.CharField(
        label='Tỉnh/Thành',
        required=False,
        widget=forms.Select(choices=[('', 'Chọn Tỉnh/Thành')], attrs={'class': 'input', 'id': 'province_select'})
    )

    district = forms.CharField(
        label='Quận/Huyện',
        required=False,
        widget=forms.Select(choices=[('', 'Chọn Quận/Huyện')], attrs={'class': 'input', 'id': 'district_select'})
    )

    ward = forms.CharField(
        label='Phường/Xã',
        required=False,
        widget=forms.Select(choices=[('', 'Chọn Phường/Xã')], attrs={'class': 'input', 'id': 'ward_select'})
    )
