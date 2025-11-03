from django import forms
from .models import UserProfile
import os # Import os module for file deletion
from django.conf import settings # Import settings for MEDIA_ROOT

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['profile_picture', 'status_message', 'chatbot_name', 'persona_preference']
        widgets = {
            'status_message': forms.TextInput(attrs={'placeholder': '상태 메시지를 입력하세요'}),
            'chatbot_name': forms.TextInput(attrs={'placeholder': '챗봇 이름을 입력하세요'}),
            'persona_preference': forms.TextInput(attrs={'placeholder': '챗봇 페르소나를 입력하세요'}),
        }

    def clean_profile_picture(self):
        # Check if the 'profile_picture-clear' checkbox was checked
        # This is how ClearableFileInput signals that the field should be cleared
        if self.cleaned_data.get('profile_picture') is False: # False indicates clear was checked
            # If there was an old profile picture, delete it from storage
            if self.instance.profile_picture:
                old_picture_path = self.instance.profile_picture.path
                if os.path.exists(old_picture_path):
                    os.remove(old_picture_path)
            return False # Return False to clear the field in the model
        return self.cleaned_data.get('profile_picture') # Otherwise, return the new picture or existing one
