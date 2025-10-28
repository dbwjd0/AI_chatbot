from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

def signup_view(request):
    """사용자 회원가입을 처리하고, 성공 시 자동으로 로그인하여 랜딩 페이지로 이동시킵니다."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # 회원가입 후 바로 로그인
            return redirect('landing')  # 랜딩 페이지로 리디렉션
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    """사용자 로그인을 처리하고, 성공 시 랜딩 페이지로 이동시킵니다."""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('landing') # 랜딩 페이지로 리디렉션
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    """사용자를 로그아웃시키고 로그인 페이지로 이동시킵니다."""
    logout(request)
    return redirect('login')
