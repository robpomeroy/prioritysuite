from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied

from accounts.models import UserLLMConfig

admin.site.unregister(User)


@admin.register(User)
class PrivacyIsolatedUserAdmin(BaseUserAdmin):
    def user_change_password(self, request, id, form_url=""):
        if not request.user.is_superuser:
            raise PermissionDenied("Only superusers have permission to reset user passwords.")
        return super().user_change_password(request, id, form_url=form_url)

    def has_change_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser:
            if obj.is_superuser or (obj.is_staff and obj.pk != request.user.pk):
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser:
            if obj.is_superuser or (obj.is_staff and obj.pk != request.user.pk):
                return False
        return super().has_delete_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            for field in ("is_superuser", "is_staff", "groups", "user_permissions"):
                if field not in readonly:
                    readonly.append(field)
        return readonly

    def get_deleted_objects(self, objs, request):
        perms_needed = set()
        to_delete = []
        for obj in objs:
            if not self.has_delete_permission(request, obj):
                perms_needed.add(obj._meta.verbose_name)
            to_delete.append(f"{obj._meta.verbose_name.capitalize()}: {obj.username}")
        model_count = {User._meta.verbose_name_plural: len(objs)}
        return to_delete, model_count, perms_needed, []


@admin.register(UserLLMConfig)
class UserLLMConfigAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "provider",
        "model_name",
        "consent_given",
        "theme_preference",
        "updated_at",
    )
    list_filter = ("provider", "consent_given", "theme_preference")
    search_fields = ("user__username", "user__email", "model_name")
    readonly_fields = ("created_at", "updated_at")
    exclude = ("_encrypted_api_key",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(user=request.user)

    def has_view_permission(self, request, obj=None):
        if obj is not None and obj.user != request.user:
            return False
        return super().has_view_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            from django.contrib.auth import get_user_model

            UserModel = get_user_model()
            kwargs["queryset"] = UserModel.objects.filter(id=request.user.id)
            kwargs["initial"] = request.user.id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.user = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # A user only has at most one UserLLMConfig (OneToOne)
        return not UserLLMConfig.objects.filter(user=request.user).exists()

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.user != request.user:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.user != request.user:
            return False
        return super().has_delete_permission(request, obj)
