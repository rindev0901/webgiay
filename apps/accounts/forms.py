from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_classes = 'w-full border rounded px-3 py-2'
        self.fields['username'].widget.attrs.update({'class': base_classes})
        self.fields['email'].widget.attrs.update({'class': base_classes})
        self.fields['password1'].widget.attrs.update({'class': base_classes})
        self.fields['password2'].widget.attrs.update({'class': base_classes})

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'w-full border rounded px-3 py-2'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'w-full border rounded px-3 py-2'}))
