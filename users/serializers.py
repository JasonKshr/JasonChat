from rest_framework import serializers
from django.contrib.auth.models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
      
from .models import Profile

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["bio", "status", "profile_picture"]
        
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    
from django.contrib.auth.password_validation import validate_password
def validate_password(self, value):
    validate_password(value)
    return value