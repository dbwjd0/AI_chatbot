
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import UserAttribute, UserActivity, UserRelationship, UserSchedule

@login_required
def view_personal_info(request):
    """
    사용자의 개인정보를 조회하는 뷰
    """
    user = request.user
    attributes = UserAttribute.objects.filter(user=user)
    activities = UserActivity.objects.filter(user=user)
    relationships = UserRelationship.objects.filter(user=user)
    schedules = UserSchedule.objects.filter(user=user)

    context = {
        'attributes': attributes,
        'activities': activities,
        'relationships': relationships,
        'schedules': schedules,
    }
    return render(request, 'personal_info.html', context)

@login_required
def delete_user_attribute(request, pk):
    attribute = get_object_or_404(UserAttribute, pk=pk, user=request.user)
    attribute.delete()
    messages.success(request, '속성 정보가 삭제되었습니다.')
    return redirect('view_personal_info')

@login_required
def delete_user_activity(request, pk):
    activity = get_object_or_404(UserActivity, pk=pk, user=request.user)
    activity.delete()
    messages.success(request, '활동 정보가 삭제되었습니다.')
    return redirect('view_personal_info')

@login_required
def delete_user_relationship(request, pk):
    relationship = get_object_or_404(UserRelationship, pk=pk, user=request.user)
    relationship.delete()
    messages.success(request, '인간관계 정보가 삭제되었습니다.')
    return redirect('view_personal_info')

@login_required
def delete_user_schedule(request, pk):
    schedule = get_object_or_404(UserSchedule, pk=pk, user=request.user)
    schedule.delete()
    messages.success(request, '일정 정보가 삭제되었습니다.')
    return redirect('view_personal_info')
