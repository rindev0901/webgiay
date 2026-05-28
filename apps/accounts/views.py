from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm
from apps.cart.services import merge_session_cart_into_user_cart


def register_view(request):
    if request.user.is_authenticated:
        return redirect('products:product_list')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            merge_session_cart_into_user_cart(user, request.session)
            messages.success(request, 'Đăng ký thành công.')
            return redirect('products:product_list')
    else:
        form = RegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('products:product_list')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            merge_session_cart_into_user_cart(user, request.session)
            messages.success(request, 'Đăng nhập thành công.')
            next_url = request.POST.get('next') or request.GET.get('next') or 'products:product_list'
            return redirect(next_url)
    else:
        form = LoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Đã đăng xuất.')
    return redirect('products:product_list')
