from django.contrib import admin
from .models import (
    ChatMessage, UserAttribute, UserActivity, UserProfile, 
    ActivityAnalytics, UserRelationship, UserSchedule, 
    PendingProactiveMessage, UserFriendship, FriendMessage
)

# Register your models here.

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'affinity_score')
    search_fields = ('user__username',)

class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_user', 'timestamp')
    list_filter = ('is_user', 'user')
    search_fields = ('user__username', 'message')
    list_per_page = 20

class UserAttributeAdmin(admin.ModelAdmin):
    list_display = ('user', 'fact_type', 'content', 'created_at')
    list_filter = ('fact_type', 'user')
    search_fields = ('user__username', 'fact_type', 'content')
    list_per_page = 20

class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'activity_date', 'place', 'companion', 'memo', 'created_at')
    list_filter = ('activity_date', 'user')
    search_fields = ('user__username', 'place', 'companion', 'memo')
    list_per_page = 20

class ActivityAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('user', 'period_type', 'period_start_date', 'place', 'companion', 'count')
    list_filter = ('period_type', 'period_start_date', 'place', 'companion')
    search_fields = ('user__username', 'place', 'companion')
    list_per_page = 20

class UserRelationshipAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'relationship_type', 'position', 'disambiguator', 'traits', 'created_at')
    list_filter = ('relationship_type', 'position', 'user')
    search_fields = ('user__username', 'name', 'relationship_type', 'traits', 'disambiguator')
    list_per_page = 20

class UserScheduleAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'schedule_time', 'content', 'created_at', 'updated_at')
    list_filter = ('date', 'user')
    search_fields = ('user__username', 'content')
    list_per_page = 20

class PendingProactiveMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('user__username', 'message__message')
    list_per_page = 20

class UserFriendshipAdmin(admin.ModelAdmin):
    list_display = ('from_user', 'to_user', 'status')
    list_filter = ('status',)
    search_fields = ('from_user__username', 'to_user__username')

class FriendMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'is_read', 'timestamp')
    list_filter = ('is_read', 'sender', 'receiver')
    search_fields = ('sender__username', 'receiver__username', 'message_content')
    readonly_fields = ('timestamp',)

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(ChatMessage, ChatMessageAdmin)
admin.site.register(UserAttribute, UserAttributeAdmin)
admin.site.register(UserActivity, UserActivityAdmin)
admin.site.register(ActivityAnalytics, ActivityAnalyticsAdmin)
admin.site.register(UserRelationship, UserRelationshipAdmin)
admin.site.register(UserSchedule, UserScheduleAdmin)
admin.site.register(PendingProactiveMessage, PendingProactiveMessageAdmin)
admin.site.register(UserFriendship, UserFriendshipAdmin)
admin.site.register(FriendMessage, FriendMessageAdmin)
