from django.contrib.auth import views as auth_views
from django.urls import path

from accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path(
        "login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/profile/", views.profile_update_view, name="profile_update"),
    path("settings/password/", views.password_change_view, name="password_change"),
    path("settings/test-llm/", views.test_llm_connection_view, name="test_llm"),
    path("delete-account/", views.delete_account_view, name="delete_account"),
    path("users/", views.user_list_view, name="user_list"),
    path("users/create/", views.user_create_view, name="user_create"),
    path("users/<int:user_id>/edit/", views.user_edit_view, name="user_edit"),
    path(
        "users/<int:user_id>/password/",
        views.user_password_reset_view,
        name="user_password_reset",
    ),
    path("users/<int:user_id>/delete/", views.user_delete_view, name="user_delete"),
]
