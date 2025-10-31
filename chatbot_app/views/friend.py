# chatbot_app/views/friend.py

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from ..models import UserFriendship, UserProfile, UserAttribute # UserProfile, UserAttribute 임포트

# ----------------------------------------------------
# 1. 친구 목록 및 받은 요청 조회 (GET /friends/)
# ----------------------------------------------------
@login_required
def friend_list_view(request):
    """
    현재 사용자의 친구 목록과 받은 요청 목록을 JSON 형태로 반환합니다.
    (friend_management.js의 loadFriendData()가 호출하는 함수)
    """
    current_user = request.user

    # 기본 프로필 사진 URL
    default_profile_pic_url = '/static/img/cute_pig.jpg' # 적절한 기본 이미지 경로로 변경하세요.

    # 1.1. 현재 친구 목록 (status=ACCEPTED) 검색
    # 내가 from_user이거나 to_user인 모든 수락된 관계를 찾습니다.
    # UserProfile 정보를 함께 가져오도록 select_related 추가
    accepted_friendships = UserFriendship.objects.filter(
        (Q(from_user=current_user) | Q(to_user=current_user)),
        status=UserFriendship.STATUS_ACCEPTED
    ).select_related('from_user__profile', 'to_user__profile')

    accepted_friends_list = []
    for friendship in accepted_friendships:
        friend_user = friendship.to_user if friendship.from_user == current_user else friendship.from_user
        
        # 친구의 프로필 정보 가져오기
        friend_profile = getattr(friend_user, 'profile', None)
        profile_picture_url = friend_profile.profile_picture.url if friend_profile and friend_profile.profile_picture else default_profile_pic_url
        status_message = friend_profile.status_message if friend_profile and friend_profile.status_message else ''
        chatbot_name = friend_profile.chatbot_name if friend_profile else ''

        # 친구의 UserAttribute 정보 가져오기
        friend_attributes = {
            attr.fact_type: attr.content
            for attr in UserAttribute.objects.filter(user=friend_user, fact_type__in=['나이', 'mbti', '성별'])
        }

        accepted_friends_list.append({
            'id': friendship.id,
            'username': friend_user.username,
            'profile_picture_url': profile_picture_url,
            'status_message': status_message,
            'chatbot_name': chatbot_name,
            'age': friend_attributes.get('나이', ''),
            'mbti': friend_attributes.get('mbti', ''),
            'gender': friend_attributes.get('성별', ''),
        })

    # 1.2. 받은 친구 요청 목록 (to_user=나 AND status=PENDING) 검색
    # 요청을 보낸 사용자의 프로필 정보도 함께 가져오도록 select_related 추가
    pending_requests = UserFriendship.objects.filter(
        to_user=current_user,
        status=UserFriendship.STATUS_PENDING
    ).select_related('from_user__profile')

    pending_requests_list = []
    for request_obj in pending_requests:
        sender_user = request_obj.from_user
        sender_profile = getattr(sender_user, 'profile', None)
        profile_picture_url = sender_profile.profile_picture.url if sender_profile and sender_profile.profile_picture else default_profile_pic_url
        status_message = sender_profile.status_message if sender_profile and sender_profile.status_message else ''
        chatbot_name = sender_profile.chatbot_name if sender_profile else ''

        # 요청을 보낸 사용자의 UserAttribute 정보 가져오기
        sender_attributes = {
            attr.fact_type: attr.content
            for attr in UserAttribute.objects.filter(user=sender_user, fact_type__in=['나이', 'mbti', '성별'])
        }

        pending_requests_list.append({
            'id': request_obj.id,
            'from_user': sender_user.username,
            'profile_picture_url': profile_picture_url,
            'status_message': status_message,
            'chatbot_name': chatbot_name,
            'age': sender_attributes.get('나이', ''),
            'mbti': sender_attributes.get('mbti', ''),
            'gender': sender_attributes.get('성별', ''),
        })

    return JsonResponse({
        'status': 'success',
        'accepted_friends': accepted_friends_list,
        'pending_requests': pending_requests_list,
    })

# ----------------------------------------------------
# 2. 친구 요청 보내기 (POST /friends/request/)
# ----------------------------------------------------
@login_required
def send_friend_request(request):
    if request.method == 'POST':
        target_username = request.POST.get('target_username')
        
        if not target_username:
            return JsonResponse({'status': 'error', 'message': '사용자 이름을 입력해 주세요.'}, status=400)

        from_user = request.user
        
        # 1. 수신자 (Target User) 유효성 검사
        try:
            to_user = User.objects.get(username=target_username)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': f'사용자 "{target_username}"를 찾을 수 없습니다.'}, status=404)

        if from_user == to_user:
            return JsonResponse({'status': 'error', 'message': '자기 자신에게 친구 신청을 할 수 없습니다.'})
        
        # 2. 기존 관계 확인 (A->B 또는 B->A로 이미 요청/친구 관계가 있는지 확인)
        existing_relationship = UserFriendship.objects.filter(
            Q(from_user=from_user, to_user=to_user) | Q(from_user=to_user, to_user=from_user)
        ).first()

        if existing_relationship:
            if existing_relationship.status == UserFriendship.STATUS_ACCEPTED:
                return JsonResponse({'status': 'info', 'message': f'"{to_user.username}"님은 이미 친구입니다.'})
            elif existing_relationship.status == UserFriendship.STATUS_PENDING:
                if existing_relationship.from_user == from_user:
                    return JsonResponse({'status': 'info', 'message': '이미 친구 요청을 보낸 상태입니다.'})
                else: # 상대방이 나에게 요청을 보낸 상태 (B->A)
                    return JsonResponse({'status': 'info', 'message': f'"{to_user.username}"님의 친구 요청이 도착해 있습니다. 받은 요청 목록에서 수락해 주세요.'})


        # 3. 새로운 친구 요청 생성 (A -> B)
        try:
            UserFriendship.objects.create(
                from_user=from_user,
                to_user=to_user,
                status=UserFriendship.STATUS_PENDING
            )
            return JsonResponse({'status': 'success', 'message': f'"{to_user.username}"님에게 친구 요청을 보냈습니다.'})
        except IntegrityError:
            return JsonResponse({'status': 'error', 'message': '친구 요청 처리 중 알 수 없는 오류가 발생했습니다.'}, status=500)
            
    return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'}, status=400)

# ----------------------------------------------------
# 3. 친구 요청 수락하기 (POST /friends/accept/<int:request_id>/)
# ----------------------------------------------------
@login_required
def accept_friend_request(request, request_id):
    if request.method == 'POST':
        friend_request = get_object_or_404(UserFriendship, id=request_id)
        current_user = request.user

        if friend_request.to_user != current_user:
            return JsonResponse({'status': 'error', 'message': '권한이 없습니다. 이 요청은 당신에게 온 것이 아닙니다.'}, status=403)
        
        if friend_request.status != UserFriendship.STATUS_PENDING:
            return JsonResponse({'status': 'info', 'message': '이미 처리되었거나 유효하지 않은 요청입니다.'})

        try:
            friend_request.status = UserFriendship.STATUS_ACCEPTED
            friend_request.save()
            
            sender_username = friend_request.from_user.username
            return JsonResponse({'status': 'success', 'message': f'"{sender_username}"님과 친구가 되었습니다! 이제 쪽지를 주고받을 수 있습니다.'})
        
        except Exception as e:  # ← 이 부분 추가!
            return JsonResponse({'status': 'error', 'message': f'친구 요청 처리 중 오류가 발생했습니다: {str(e)}'}, status=500)

    return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'}, status=400)

# ----------------------------------------------------
# 4. 친구 요청 거절하기 (POST /friends/reject/<int:request_id>/)
# ----------------------------------------------------
@login_required
def reject_friend_request(request, request_id):
    if request.method == 'POST':
        friend_request = get_object_or_404(UserFriendship, id=request_id)
        current_user = request.user

        if friend_request.to_user != current_user:
            return JsonResponse({'status': 'error', 'message': '권한이 없습니다. 이 요청은 당신에게 온 것이 아닙니다.'}, status=403)
        
        if friend_request.status != UserFriendship.STATUS_PENDING:
            return JsonResponse({'status': 'info', 'message': '이미 처리되었거나 유효하지 않은 요청입니다.'})

        try:
            sender_username = friend_request.from_user.username  # 💡 delete() 전에 username 저장
            friend_request.delete()
            return JsonResponse({'status': 'success', 'message': f'"{sender_username}"님의 친구 요청을 거절했습니다.'})
        
        except Exception as e:  # 👈 이 부분이 필수입니다!
            return JsonResponse({'status': 'error', 'message': f'친구 요청 거절 중 오류가 발생했습니다: {str(e)}'}, status=500)

    return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'}, status=400)

# ----------------------------------------------------
# 5. 친구 삭제하기 (POST /friends/delete/<int:friendship_id>/)
# ----------------------------------------------------
@login_required
def delete_friend(request, friendship_id):
    if request.method == 'POST':
        # 친구 관계 객체 가져오기
        friendship = get_object_or_404(UserFriendship, id=friendship_id)
        current_user = request.user

        # 권한 확인 (현재 사용자가 친구 관계의 양쪽 중 하나인지)
        if not (friendship.from_user == current_user or friendship.to_user == current_user):
            return JsonResponse({'status': 'error', 'message': '권한이 없습니다. 이 친구 관계를 삭제할 수 없습니다.'}, status=403)
        
        # 친구 관계 삭제
        try:
            friendship.delete()
            return JsonResponse({'status': 'success', 'message': '친구 관계가 삭제되었습니다.'})
        except Exception:
            return JsonResponse({'status': 'error', 'message': '친구 삭제 처리 중 오류가 발생했습니다.'}, status=500)
            
    return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'}, status=400)

# ----------------------------------------------------
# 6. 사용자 검색 (GET /friends/search/?query=<username_query>)
# ----------------------------------------------------
@login_required
def search_users(request):
    if request.method == 'GET':
        query = request.GET.get('query', '')
        current_user = request.user

        if not query:
            return JsonResponse({'status': 'success', 'users': []})

        # 현재 사용자를 제외하고, 쿼리에 사용자 이름이 포함된 사용자 검색
        # 대소문자 구분 없이 검색 (icontains)
        found_users = User.objects.filter(
            username__icontains=query
        ).exclude(id=current_user.id).values('id', 'username')

        # 이미 친구이거나 요청을 보냈거나 받은 사용자 필터링
        # 1. 내가 요청을 보낸 경우 (from_user=current_user, to_user=found_user, status=PENDING)
        # 2. 내가 요청을 받은 경우 (from_user=found_user, to_user=current_user, status=PENDING)
        # 3. 이미 친구인 경우 (status=ACCEPTED)
        existing_relationships = UserFriendship.objects.filter(
            Q(from_user=current_user, to_user__in=found_users.values('id')) |
            Q(to_user=current_user, from_user__in=found_users.values('id'))
        )

        existing_users_ids = set()
        for rel in existing_relationships:
            if rel.from_user.id == current_user.id:
                existing_users_ids.add(rel.to_user.id)
            else:
                existing_users_ids.add(rel.from_user.id)

        search_results = []
        for user in found_users:
            is_friend = False
            has_pending_request_from_me = False
            has_pending_request_to_me = False

            # 관계 상태 확인
            rel = existing_relationships.filter(
                Q(from_user=current_user, to_user=user['id']) |
                Q(from_user=user['id'], to_user=current_user)
            ).first()

            if rel:
                if rel.status == UserFriendship.STATUS_ACCEPTED:
                    is_friend = True
                elif rel.status == UserFriendship.STATUS_PENDING:
                    if rel.from_user.id == current_user.id:
                        has_pending_request_from_me = True
                    else:
                        has_pending_request_to_me = True

            search_results.append({
                'id': user['id'],
                'username': user['username'],
                'is_friend': is_friend,
                'has_pending_request_from_me': has_pending_request_from_me,
                'has_pending_request_to_me': has_pending_request_to_me,
            })

        return JsonResponse({'status': 'success', 'users': search_results})

    return JsonResponse({'status': 'error', 'message': '잘못된 접근입니다.'}, status=400)