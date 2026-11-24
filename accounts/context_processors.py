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
    }
