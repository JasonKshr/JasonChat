
from django.contrib.auth import authenticate, login, logout, get_user_model

from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from .models import Profile
from .serializers import RegisterSerializer, ProfileSerializer


User = get_user_model()


# Register a new user
@api_view(["POST"])
def register(request):
    serializer = RegisterSerializer(data=request.data)

    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User created!"}, status=201)

    return Response(serializer.errors, status=400)


# Login
@api_view(["POST"])
def login_user(request):
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(
        request,
        username=username,
        password=password
    )

    if user is not None:
        login(request, user)
        return Response({"message": "Login successful!"})

    return Response(
        {"error": "Invalid credentials"},
        status=401
    )


# Logout
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    logout(request)
    return Response({"message": "Logged out successfully!"})


# Get current user's profile
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    user = request.user
    profile, created = Profile.objects.get_or_create(user=user)

    return Response({
        "username": user.username,
        "email": user.email,
        "date_joined": user.date_joined,
        "bio": profile.bio,
        "status": profile.status,
        "profile_picture": (
            request.build_absolute_uri(profile.profile_picture.url)
            if profile.profile_picture else None
        )
    })


# View and update profile
class UpdateProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "patch", "options"]

    def get_object(self):
        profile, created = Profile.objects.get_or_create(
            user=self.request.user
        )
        return profile

    def post(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


# Search for users
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_users(request):
    query = request.query_params.get("q", "").strip()

    if not query:
        return Response([])

    users = User.objects.filter(
        username__icontains=query
    ).exclude(id=request.user.id)[:20]

    return Response([
        {
            "id": user.id,
            "username": user.username
        }
        for user in users
    ])
    
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash
from .serializers import ChangePasswordSerializer

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    user = request.user
    old_password = serializer.validated_data["old_password"]
    new_password = serializer.validated_data["new_password"]

    if not user.check_password(old_password):
        return Response({"error": "Incorrect current password"}, status=400)

    try:
        validate_password(new_password, user=user)
    except ValidationError as error:
        return Response({"error": error.messages}, status=400)

    user.set_password(new_password)
    user.save()
    update_session_auth_hash(request, user)

    return Response({"message": "Password changed successfully!"})
  
from django.contrib.auth.views import PasswordResetView
class ResetPasswordView(PasswordResetView):
    email_template_name = "users/password_reset_email.txt"
    success_url = "/users/password-reset/done/"
    template_name = "users/password_reset_form.html"
    
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def delete_account(request):
    password = request.data.get("password")

    if not request.user.check_password(password or ""):
        return Response(
            {"error": "Incorrect password"},
            status=400
        )

    request.user.delete()

    return Response(
        {"message": "Account deleted successfully!"},
        status=200
    )