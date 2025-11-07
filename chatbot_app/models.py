from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext as gt
import uuid

# Create your models here.

class UserProfile(models.Model):
    """
    사용자 프로필을 저장하는 모델
    - user: Django의 기본 User 모델과 1:1 관계
    - affinity_score: AI '아이'와의 호감도 점수
    - memory: 사용자에 대한 정보를 JSON 형태로 저장 (예: {"facts": ["사용자는 고양이를 좋아한다"], "name": "홍길동"})
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    nickname = models.CharField(max_length=100, null=True, blank=True, help_text=_("사용자 닉네임"))
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True, default='profile_pics/cute_pig.jpg', help_text=_("사용자 프로필 사진"))
    is_onboarding_complete = models.BooleanField(default=False, help_text=_("사용자 초기 설정(온보딩) 완료 여부"))
    affinity_score = models.IntegerField(default=0, help_text=_("AI '아이'와의 호감도 점수"))
    memory = models.JSONField(default=dict, help_text=_("사용자에 대한 기억 저장소"))
    chatbot_name = models.CharField(max_length=100, default=_('아이'), help_text=_("사용자가 지정한 챗봇 이름"))
    persona_preference = models.CharField(max_length=100, default=_('친근한'), help_text=_("챗봇의 스타일"))
    status_message = models.CharField(max_length=255, null=True, blank=True, help_text=_("사용자 상태 메시지"))

    def __str__(self):
        return _("{nickname}의 프로필").format(nickname=self.nickname or self.user.username)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
        """%s""" % _("User가 생성될 때 자동으로 UserProfile을 생성합니다.")
        if created:
            UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
        """%s""" % _("User가 저장될 때 UserProfile도 함께 저장합니다.")
        try:
            instance.profile.save()
        except UserProfile.DoesNotExist:
            # admin 등에서 profile이 없는 user를 다룰 때를 대비
            UserProfile.objects.create(user=instance)

class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True, help_text=_("메시지에 첨부된 이미지 파일"))
    is_user = models.BooleanField(default=True)  # True면 사용자 메시지, False면 AI 메시지
    character_emotion = models.CharField(max_length=50, null=True, blank=True, help_text=_("AI 캐릭터의 감정 상태")) # New field
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return _("{username}: {message_snippet}").format(username=self.user.username, message_snippet=self.message[:50])

class UserAttribute(models.Model):
    """%s""" % _("사용자의 불변의 속성(성격, MBTI, 생일, 신체 특징 등)를 저장하는 모델")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attributes')
    fact_type = models.CharField(max_length=100, help_text=_("속성의 종류 (예: '성격', 'MBTI', '생일')"), null=True, blank=True)
    content = models.CharField(max_length=255, help_text=_("속성 내용 (예: '털털함', 'INFP', '1995-10-31')"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'fact_type', 'content') # 중복 정보 방지

    def __str__(self):
        return _("{username}의 속성 - {fact_type}: {content}").format(username=self.user.username, fact_type=self.fact_type, content=self.content)

class UserActivity(models.Model):
    """%s""" % _("사용자의 활동 기록(일기장)을 저장하는 모델")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_date = models.DateField(help_text=_("활동 날짜"), null=True, blank=True)
    activity_time = models.TimeField(null=True, blank=True, help_text=_("활동 시간"))
    place = models.CharField(max_length=255, null=True, blank=True, help_text=_("장소"))
    companion = models.CharField(max_length=255, null=True, blank=True, help_text=_("동행인"))
    memo = models.TextField(null=True, blank=True, help_text=_("활동 관련 메모 또는 대화 내용"))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return _("[{activity_date}] {username}'s activity at {place}").format(activity_date=self.activity_date, username=self.user.username, place=self.place)

class ActivityAnalytics(models.Model):
    """%s""" % _("사용자의 활동을 주/월/년 단위로 요약하여 통계를 저장하는 모델")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analytics')
    period_type = models.CharField(max_length=10, choices=[('weekly', _('주간')), ('monthly', _('월간')), ('yearly', _('연간'))])
    period_start_date = models.DateField(help_text=_("통계 기간의 시작일"))
    place = models.CharField(max_length=255, db_index=True, help_text=_("장소"))
    companion = models.CharField(max_length=255, null=True, blank=True, db_index=True, help_text=_("동행인"))
    count = models.PositiveIntegerField(default=0, help_text=_("해당 기간 동안의 방문 횟수"))

    class Meta:
        unique_together = ('user', 'period_type', 'period_start_date', 'place', 'companion')

    def __str__(self):
        return _("[{period_start_date} {period_type}] {username} at {place}: {count}").format(period_start_date=self.period_start_date, period_type=self.period_type, username=self.user.username, place=self.place, count=self.count)

class UserRelationship(models.Model):
    """%s""" % _("사용자의 인간관계 정보를 저장하는 모델")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='relationships')
    serial_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, help_text=_("동일 인물 구분을 위한 고유 시리얼 코드")) # New field
    relationship_type = models.CharField(max_length=100, help_text=_("관계 유형 (예: 가족, 친구, 직장 동료)"))
    position = models.CharField(max_length=100, null=True, blank=True, help_text=_("관계 내 포지션 (예: 오빠, 친한 친구, 상사)"))
    name = models.CharField(max_length=100, help_text=_("상대방 이름"))
    disambiguator = models.CharField(max_length=100, null=True, blank=True, help_text=_("동명이인 구분을 위한 식별자 (예: '개발팀', '친구')"))
    traits = models.TextField(null=True, blank=True, help_text=_("상대방 성격 또는 특징"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Update unique_together to use serial_code instead of name and disambiguator
        unique_together = ('user', 'serial_code') 

    def __str__(self):
        return _("{username} - {name} ({relationship_type}) [{serial_code}]").format(username=self.user.username, name=self.name, relationship_type=self.relationship_type, serial_code=self.serial_code)

class UserSchedule(models.Model):
    """%s""" % _("사용자의 하루 일과를 저장하는 모델")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='schedules')
    date = models.DateField(help_text=_("일과 날짜"))
    schedule_time = models.TimeField(null=True, blank=True, help_text=_("일과 시간")) # New field
    content = models.TextField(help_text=_("하루 일과 내용"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # unique_together = ('user', 'date') # 사용자는 하루에 하나의 스케줄만 가질 수 있음
        # 사용자별, 날짜별로 여러 스케줄을 허용하며, 시간(최신순)으로 정렬
        ordering = ['date', '-schedule_time']

    def __str__(self):
        return _("[{date}] {username}'s schedule").format(date=self.date, username=self.user.username)

class PendingProactiveMessage(models.Model):
    """%s""" % _("읽지 않은 능동 메시지를 추적하는 모델")
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pending_proactive_message')
    message = models.OneToOneField(ChatMessage, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return _("{username}의 읽지 않은 능동 메시지").format(username=self.user.username)

class QuizResult(models.Model):
    """%s""" % _("사용자의 퀴즈 결과를 저장하는 모델")
    QUIZ_GENRE_CHOICES = [
        ('all', _('랜덤')),
        ('korean_history', _('한국사')),
        ('world_history', _('세계사')),
        ('science', _('과학')),
        ('literature', _('문학')),
        ('general_knowledge', _('상식')),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_results')
    genre = models.CharField(max_length=100, choices=QUIZ_GENRE_CHOICES, help_text=_("퀴즈 장르"))
    num_questions = models.IntegerField(help_text=_("총 문제 수"))
    score = models.IntegerField(help_text=_("획득 점수"))
    date_completed = models.DateTimeField(auto_now_add=True, help_text=_("퀴즈 완료 시간"))

    class Meta:
        ordering = ['-date_completed'] # 최신 결과부터 표시

    def __str__(self):
        return _("{username} - {genre} 퀴즈 ({score}/{num_questions}) on {date_completed}").format(username=self.user.username, genre=self.genre, score=self.score, num_questions=self.num_questions, date_completed=self.date_completed.strftime('%Y-%m-%d'))


# 쪽지 기능 - 친구 관계 모델 (UserFriendship)
# ----------------------------------------------------
class UserFriendship(models.Model):
    STATUS_PENDING = 1  # 신청 대기 중
    STATUS_ACCEPTED = 2 # 친구 수락 완료

    STATUS_CHOICES = (
        (STATUS_PENDING, _('대기 중')),
        (STATUS_ACCEPTED, _('친구')),
    )

    from_user = models.ForeignKey(User, related_name='friendship_requests_sent', on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name='friendship_requests_received', on_delete=models.CASCADE)
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    class Meta:
        # 🌟 친구 요청 중복 방지 (필수)
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return _("요청: {from_user} -> {to_user} ({status})").format(from_user=self.from_user.username, to_user=self.to_user.username, status=self.get_status_display())

class FriendMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_messages')
    sender_chatbot_name = models.CharField(max_length=100, help_text=_("보낸 사람 챗봇 이름"))
    sender_persona = models.CharField(max_length=100, help_text=_("보낸 사람 챗봇 페르소나"))
    message_content = models.TextField(help_text=_("쪽지 내용"))
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['receiver', 'is_read']),
        ]

    def __str__(self):
        return _("{sender}님이 {receiver}님에게 보낸 쪽지: {message_content}... (읽음: {is_read})").format(sender=self.sender.username, receiver=self.receiver.username, message_content=self.message_content[:50], is_read=self.is_read)
