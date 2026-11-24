from django.conf import settings

from config import __version__


def user_preferences(request):
    if request.user.is_authenticated:
        config = getattr(request.user, "llm_config", None)
        theme = config.theme_preference if config else "auto"
    else:
        theme = "auto"
    return {
        "current_theme_preference": theme,
        "app_version": __version__,
        "demo_mode": getattr(settings, "DEMO_MODE", False),
        "is_demo_user": (
            request.user.is_authenticated
            and request.user.username == getattr(settings, "DEMO_USERNAME", "demo")
        ),
    }
