
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.translation import get_language
from ..models import UserAttribute, UserActivity, UserRelationship, UserSchedule
from ..services import lang_util

@login_required
def view_personal_info(request):
    """
    사용자의 개인정보를 조회하는 뷰
    """
    user = request.user
    # .values()에 템플릿에서 필요한 필드(pk 포함)를 명시적으로 포함
    attributes = list(UserAttribute.objects.filter(user=user).values('pk', 'fact_type', 'content'))
    activities = list(UserActivity.objects.filter(user=user).values('pk', 'activity_date', 'memo'))
    relationships = list(UserRelationship.objects.filter(user=user).values('pk', 'name', 'relationship_type'))
    schedules = list(UserSchedule.objects.filter(user=user).values('pk', 'date', 'content'))

    user_language = get_language()
    if user_language != 'ko':
        # 속성 번역
        if attributes:
            fact_types = lang_util.translate_from_korean_batch([a['fact_type'] for a in attributes], user_language)
            contents = lang_util.translate_from_korean_batch([a['content'] for a in attributes], user_language)
            for i, a in enumerate(attributes):
                a['fact_type'] = fact_types[i]
                a['content'] = contents[i]

        # 활동 번역
        if activities:
            memos = lang_util.translate_from_korean_batch([a['memo'] for a in activities], user_language)
            for i, a in enumerate(activities):
                a['memo'] = memos[i]

        # 인간관계 번역
        if relationships:
            names = lang_util.translate_from_korean_batch([r['name'] for r in relationships], user_language)
            rel_types = lang_util.translate_from_korean_batch([r['relationship_type'] for r in relationships], user_language)
            for i, r in enumerate(relationships):
                r['name'] = names[i]
                r['relationship_type'] = rel_types[i]

        # 일정 번역
        if schedules:
            schedule_contents = lang_util.translate_from_korean_batch([s['content'] for s in schedules], user_language)
            for i, s in enumerate(schedules):
                s['content'] = schedule_contents[i]

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
    messages.success(request, _('속성 정보가 삭제되었습니다.'))
    return redirect('view_personal_info')

@login_required
def delete_user_activity(request, pk):
    activity = get_object_or_404(UserActivity, pk=pk, user=request.user)
    activity.delete()
    messages.success(request, _('활동 정보가 삭제되었습니다.'))
    return redirect('view_personal_info')

@login_required
def delete_user_relationship(request, pk):
    relationship = get_object_or_404(UserRelationship, pk=pk, user=request.user)
    relationship.delete()
    messages.success(request, _('인간관계 정보가 삭제되었습니다.'))
    return redirect('view_personal_info')

@login_required
def delete_user_schedule(request, pk):
    schedule = get_object_or_404(UserSchedule, pk=pk, user=request.user)
    schedule.delete()
    messages.success(request, _('일정 정보가 삭제되었습니다.'))
    return redirect('view_personal_info')
