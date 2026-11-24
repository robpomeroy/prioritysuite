from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from accounts import views
from accounts.forms import CustomPasswordResetForm, CustomSetPasswordForm

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path(
        "login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Self-service email password reset
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
            form_class=CustomPasswordResetForm,
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
            form_class=CustomSetPasswordForm,
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("settings/", views.settings_view, name="settings"),
    path("settings/profile/", views.profile_update_view, name="profile_update"),
    path("settings/password/", views.password_change_view, name="password_change"),
    path("settings/test-llm/", views.test_llm_connection_view, name="test_llm"),
    path("delete-account/", views.delete_account_view, name="delete_account"),
    path("users/", views.user_list_view, name="user_list"),
    path("users/create/", views.user_create_view, name="user_create"),
    path("users/<int:user_id>/edit/", views.user_edit_view, name="user_edit"),
    path(
        "users/<int:user_id>/send-reset/",
        views.user_send_password_reset_view,
        name="user_send_password_reset",
    ),
    path("users/<int:user_id>/delete/", views.user_delete_view, name="user_delete"),
]
