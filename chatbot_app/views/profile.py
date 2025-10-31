from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..forms import UserProfileForm

@login_required
def edit_profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, '프로필이 성공적으로 업데이트되었습니다.')
            return redirect('edit_profile') # 또는 다른 페이지로 리디렉션
        else:
            messages.error(request, '프로필 업데이트 중 오류가 발생했습니다.')
    else:
        form = UserProfileForm(instance=request.user.profile)
    return render(request, 'edit_profile.html', {'form': form})
