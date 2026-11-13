from rest_framework import serializers
from django.contrib.auth.models import User

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_password(self, value):
        from django.contrib.auth.password_validation import validate_password as django_validate_password
        django_validate_password(value)
        return value

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

    def validate_new_password(self, value):
        return validate_password(value)

from django.contrib.auth.password_validation import validate_password as django_validate_password

def validate_password(value):
    django_validate_password(value)
    return value