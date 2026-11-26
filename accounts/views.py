import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.forms import (
    AdminUserCreateForm,
    AdminUserEditForm,
    CustomPasswordChangeForm,
    CustomPasswordResetForm,
    UserLLMConfigForm,
    UserProfileForm,
    UserRegistrationForm,
)
from accounts.models import UserLLMConfig

logger = logging.getLogger(__name__)


def _is_demo_user(user) -> bool:
    if not getattr(settings, "DEMO_MODE", False):
        return False
    demo_username = getattr(settings, "DEMO_USERNAME", "demo")
    return bool(user.is_authenticated and user.username == demo_username)


def _require_admin(user):
    if not (user.is_authenticated and (user.is_staff or user.is_superuser)):
        raise PermissionDenied("You do not have permission to access user administration.")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("frameworks:workspace")
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            UserLLMConfig.objects.create(user=user)
            login(request, user)
            messages.success(request, f"Welcome to PrioritySuite, {user.username}!")
            return redirect("frameworks:workspace")
    else:
        form = UserRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@require_POST
def demo_login_view(request):
    """Logs the visitor into the demonstration account if DEMO_MODE is enabled (§8.3)."""
    if not getattr(settings, "DEMO_MODE", False):
        raise PermissionDenied("Demo mode is not enabled on this instance.")

    demo_username = getattr(settings, "DEMO_USERNAME", "demo")
    existing_user = User.objects.filter(username=demo_username).first()

    # Reject if an existing account (active or inactive) is privileged or password-authenticated
    if existing_user and (
        existing_user.is_staff
        or existing_user.is_superuser
        or existing_user.has_usable_password()
    ):
        raise PermissionDenied(
            f"Account '{demo_username}' cannot be used for public demo login because it is "
            "a privileged or password-authenticated user account."
        )

    # If demo user is missing or inactive, reset/provision it cleanly
    if not existing_user or not existing_user.is_active:
        from django.core.management import call_command

        call_command("reset_demo", username=demo_username)
        demo_user = User.objects.get(username=demo_username)
    else:
        demo_user = existing_user

    login(request, demo_user)
    messages.success(request, "Welcome to the PrioritySuite live demonstration!")
    return redirect("frameworks:workspace")


@login_required
def settings_view(request):
    config, _ = UserLLMConfig.objects.get_or_create(user=request.user)
    if request.method == "POST":
        old_provider = config.provider
        old_api_base = (config.api_base or "").strip()
        form = UserLLMConfigForm(request.POST, instance=config)
        if form.is_valid():
            cfg = form.save(commit=False)
            new_key = form.cleaned_data.get("raw_api_key")
            if new_key:
                cfg.api_key = new_key
            elif cfg.provider != old_provider or (cfg.api_base or "").strip() != old_api_base:
                cfg.api_key = ""
            cfg.save()
            messages.success(request, "LLM settings updated successfully.")
            return redirect("accounts:settings")
    else:
        form = UserLLMConfigForm(instance=config)

    profile_form = UserProfileForm(instance=request.user)
    password_form = CustomPasswordChangeForm(user=request.user)
    return render(
        request,
        "accounts/settings.html",
        {
            "form": form,
            "config": config,
            "profile_form": profile_form,
            "password_form": password_form,
        },
    )


@login_required
@require_POST
def profile_update_view(request):
    if _is_demo_user(request.user):
        messages.warning(request, "Profile modifications are disabled in the live demo.")
        return redirect("accounts:settings")

    config, _ = UserLLMConfig.objects.get_or_create(user=request.user)
    profile_form = UserProfileForm(request.POST, instance=request.user)
    if profile_form.is_valid():
        profile_form.save()
        messages.success(request, "Account profile updated successfully.")
        return redirect("accounts:settings")

    form = UserLLMConfigForm(instance=config)
    password_form = CustomPasswordChangeForm(user=request.user)
    return render(
        request,
        "accounts/settings.html",
        {
            "form": form,
            "config": config,
            "profile_form": profile_form,
            "password_form": password_form,
        },
    )


@login_required
@require_POST
def password_change_view(request):
    if _is_demo_user(request.user):
        messages.warning(request, "Password changes are disabled in the live demo.")
        return redirect("accounts:settings")

    config, _ = UserLLMConfig.objects.get_or_create(user=request.user)
    password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
    if password_form.is_valid():
        user = password_form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed successfully.")
        return redirect("accounts:settings")

    form = UserLLMConfigForm(instance=config)
    profile_form = UserProfileForm(instance=request.user)
    return render(
        request,
        "accounts/settings.html",
        {
            "form": form,
            "config": config,
            "profile_form": profile_form,
            "password_form": password_form,
        },
    )


@login_required
@require_POST
def export_vault_view(request):
    """Exports a password-encrypted vault backup envelope using the user's password."""
    password = request.POST.get("password", "")
    if not password or not request.user.check_password(password):
        messages.error(request, "Incorrect password. Cannot export encrypted vault.")
        return redirect("accounts:settings")

    from django.http import HttpResponse

    from accounts.vault import create_encrypted_vault_payload

    envelope = create_encrypted_vault_payload(request.user, password)
    payload_str = json.dumps(envelope, indent=2)
    response = HttpResponse(payload_str, content_type="application/json")
    response["Content-Disposition"] = (
        f'attachment; filename="prioritysuite_vault_{request.user.username}.json"'
    )
    return response


@login_required
@require_POST
def restore_vault_view(request):
    """Restores user frameworks and decisions from an encrypted vault file."""
    if _is_demo_user(request.user):
        messages.warning(request, "Vault restoration is disabled in the live demo.")
        return redirect("accounts:settings")

    password = request.POST.get("password", "")
    vault_file = request.FILES.get("vault_file")

    if not password or not vault_file:
        messages.error(request, "Both the vault file and password are required for restoration.")
        return redirect("accounts:settings")

    from accounts.vault import decrypt_and_restore_vault

    try:
        content = vault_file.read().decode("utf-8")
        envelope = json.loads(content)
        if not isinstance(envelope, dict):
            raise ValueError("Vault file root structure must be a JSON object.")
        salt = envelope.get("salt")
        ciphertext = envelope.get("ciphertext")
        if not isinstance(salt, str) or not isinstance(ciphertext, str):
            raise ValueError("Vault file must contain string 'salt' and 'ciphertext' fields.")
        count = decrypt_and_restore_vault(request.user, envelope, password)
        messages.success(request, f"Successfully restored {count} framework(s) from vault.")
    except (ValueError, KeyError, json.JSONDecodeError, AttributeError) as exc:
        messages.error(request, f"Failed to restore vault: {exc}")

    return redirect("accounts:settings")


@login_required
def delete_account_view(request):
    if _is_demo_user(request.user):
        messages.warning(request, "Account deletion is disabled in the live demo.")
        return redirect("accounts:settings")

    if request.method == "POST":
        user = request.user
        logout(request)
        user.delete()
        messages.info(
            request,
            "Your account and all associated frameworks and decisions have been "
            "completely deleted from PrioritySuite.",
        )
        return redirect("accounts:login")
    return render(request, "accounts/delete_account.html")


@login_required
def test_llm_connection_view(request):
    if request.method != "POST":
        return redirect("accounts:settings")
    config = getattr(request.user, "llm_config", None)

    if "provider" in request.POST:
        provider = request.POST.get("provider", "none")
        model_name = request.POST.get("model_name", "").strip()
        api_base = request.POST.get("api_base", "").strip()
        consent_given = (
            str(request.POST.get("consent_given", "")).lower() in ("on", "true", "1")
            or request.POST.get("consent_given") is True
        )
        raw_key = (request.POST.get("raw_api_key") or request.POST.get("api_key") or "").strip()
        api_base_matches = (api_base == (config.api_base or "").strip()) if config else False
        api_key = raw_key or (
            config.api_key if (config and config.provider == provider and api_base_matches) else ""
        )
    else:
        if not config:
            messages.warning(request, "Please configure an active LLM provider before testing.")
            return redirect("accounts:settings")
        provider = config.provider
        model_name = config.model_name
        api_base = config.api_base
        consent_given = config.consent_given
        api_key = config.api_key

    valid_providers = {
        choice[0] for choice in UserLLMConfig.PROVIDER_CHOICES if choice[0] != "none"
    }
    if provider not in valid_providers or not model_name:
        messages.warning(request, "Please configure an active LLM provider before testing.")
        return redirect("accounts:settings")
    if not consent_given:
        messages.warning(request, "Consent must be granted before connecting to external LLMs.")
        return redirect("accounts:settings")

    from llm.service import generate_reflection

    success, response_text = generate_reflection(
        user_context_markdown="Ping test connection from PrioritySuite settings.",
        user_prompt="Reply with exactly: 'PrioritySuite thinking partner connection verified.'",
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        api_base=api_base,
        timeout=10,
    )
    if success:
        messages.success(request, f"Connection verified successfully! ({provider}: {model_name})")
    else:
        from llm.service import sanitize_credentials, sanitize_url

        sanitized_base = sanitize_url(api_base)
        sanitized_resp = sanitize_credentials(response_text, api_key=api_key, api_base=api_base)

        logger.warning(
            "LLM test connection failure for user '%s' (%s/%s, base=%s): %s",
            request.user.username,
            provider,
            model_name,
            sanitized_base,
            sanitized_resp,
        )
        messages.error(request, f"Connection failed: {response_text}")
    return redirect("accounts:settings")


# -------------------------------------------------------------------------
# User Administration Views (Staff / Superuser Only)
# -------------------------------------------------------------------------


@login_required
def user_list_view(request):
    _require_admin(request.user)
    users = User.objects.all().order_by("username")
    paginator = Paginator(users, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(
        request,
        "accounts/user_list.html",
        {"users_list": page_obj, "page_obj": page_obj},
    )


@login_required
def user_create_view(request):
    _require_admin(request.user)
    if request.method == "POST":
        form = AdminUserCreateForm(request.POST, current_user=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            if not request.user.is_superuser:
                user.is_staff = False
                user.is_superuser = False
            user.save()
            UserLLMConfig.objects.get_or_create(user=user)
            messages.success(request, f"User '{user.username}' created successfully.")
            return redirect("accounts:user_list")
    else:
        form = AdminUserCreateForm(current_user=request.user)
    return render(request, "accounts/user_form.html", {"form": form, "action": "create"})


@login_required
def user_edit_view(request, user_id):
    _require_admin(request.user)
    target_user = get_object_or_404(User, pk=user_id)
    is_restricted_target = target_user.is_superuser or (
        target_user.is_staff and target_user.pk != request.user.pk
    )
    if is_restricted_target and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to edit staff or superuser accounts.")

    if request.method == "POST":
        form = AdminUserEditForm(request.POST, instance=target_user, current_user=request.user)
        if form.is_valid():
            new_active = form.cleaned_data.get("is_active")
            new_staff = form.cleaned_data.get("is_staff")
            new_superuser = form.cleaned_data.get("is_superuser")
            if target_user.pk == request.user.pk:
                if not new_active:
                    form.add_error("is_active", "You cannot deactivate your own account.")
                if not new_staff and request.user.is_staff:
                    form.add_error("is_staff", "You cannot remove your own staff role.")
                if not new_superuser and request.user.is_superuser:
                    form.add_error("is_superuser", "You cannot remove your own superuser role.")
                if form.errors:
                    return render(
                        request,
                        "accounts/user_form.html",
                        {"form": form, "action": "edit", "target_user": target_user},
                    )

            saved_user = form.save(commit=False)
            if not request.user.is_superuser:
                saved_user.is_staff = target_user.is_staff
                saved_user.is_superuser = target_user.is_superuser
            saved_user.save()
            messages.success(request, f"User '{saved_user.username}' updated successfully.")
            return redirect("accounts:user_list")
    else:
        form = AdminUserEditForm(instance=target_user, current_user=request.user)
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "action": "edit", "target_user": target_user},
    )


@login_required
@require_POST
def user_send_password_reset_view(request, user_id):
    _require_admin(request.user)
    target_user = get_object_or_404(User, pk=user_id)
    is_restricted_target = target_user.is_superuser or (
        target_user.is_staff and target_user.pk != request.user.pk
    )
    if is_restricted_target and not request.user.is_superuser:
        raise PermissionDenied(
            "You do not have permission to trigger password reset for staff or superuser accounts."
        )

    if not target_user.email:
        messages.error(
            request,
            f"User '{target_user.username}' does not have an email address configured. "
            "Cannot send password reset email.",
        )
        return redirect("accounts:user_list")

    reset_form = CustomPasswordResetForm(data={"email": target_user.email})
    if reset_form.is_valid():
        reset_form.save(
            request=request,
            use_https=request.is_secure(),
            email_template_name="accounts/password_reset_email.html",
            subject_template_name="accounts/password_reset_subject.txt",
        )
        messages.success(
            request,
            f"Password reset instructions have been emailed to '{target_user.email}' "
            f"for user '{target_user.username}'.",
        )
    else:
        messages.error(request, "Failed to send password reset email.")
    return redirect("accounts:user_list")


@login_required
def user_delete_view(request, user_id):
    _require_admin(request.user)
    target_user = get_object_or_404(User, pk=user_id)
    if target_user.pk == request.user.pk:
        messages.error(request, "You cannot delete your own account via user administration.")
        return redirect("accounts:user_list")
    is_restricted_target = target_user.is_superuser or (
        target_user.is_staff and target_user.pk != request.user.pk
    )
    if is_restricted_target and not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to delete staff or superuser accounts.")

    if request.method == "POST":
        username = target_user.username
        target_user.delete()
        messages.success(request, f"User '{username}' has been deleted.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_confirm_delete.html", {"target_user": target_user})
