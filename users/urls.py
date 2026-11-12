
from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import ResetPasswordView

urlpatterns = [
    path("register/", views.register),
    path("login/", views.login_user),
    path("logout/", views.logout_user),
    path("me/", views.get_profile),
    path("me/update/", views.UpdateProfileView.as_view()),
    path("search/", views.search_users),
    path("change-password/", views.change_password),

    # Password reset request
    path(
        "password-reset/",
        ResetPasswordView.as_view(),
        name="password_reset"
    ),

    # Password reset email sent
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="users/password_reset_done.html"
        ),
        name="password_reset_done"
    ),

    # Enter new password
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="users/password_reset_confirm.html"
        ),
        name="password_reset_confirm"
    ),

    # Password reset successful
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="users/password_reset_complete.html"
        ),
        name="password_reset_complete"
    ),
    
    path("delete-account/", views.delete_account),
]
