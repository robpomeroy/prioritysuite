import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import UserLLMConfig
from frameworks.models import Framework
from frameworks.services import (
    seed_career_transition_framework,
    seed_creator_framework,
    seed_sample_framework,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Resets the demonstration account data and restores clean sample frameworks, "
        "decisions, and simulated LLM reflection logs (§8.3 & §11.2)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default=getattr(settings, "DEMO_USERNAME", "demo"),
            help="Username of the demonstration account to reset.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        self.stdout.write(f"Resetting demonstration account '{username}'...")

        demo_user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": "demo@prioritysuite.local",
                "first_name": "Demo",
                "last_name": "Visitor",
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
            },
        )
        if created:
            demo_user.set_unusable_password()
            demo_user.save()
            self.stdout.write(f"Created demo account '{username}'.")
        else:
            # Revert any metadata changes made to demo account
            demo_user.is_active = True
            demo_user.is_staff = False
            demo_user.is_superuser = False
            demo_user.set_unusable_password()
            demo_user.save()

        # Ensure demo LLM config is offline/sample
        UserLLMConfig.objects.update_or_create(
            user=demo_user,
            defaults={
                "provider": "ollama",
                "model_name": "ollama/llama3.1",
                "api_base": "http://localhost:11434",
                "consent_given": False,
            },
        )

        # Clear existing frameworks and decisions for demo user
        Framework.objects.filter(owner=demo_user).delete()

        # Seed full suite of starter frameworks
        seed_sample_framework(demo_user)
        seed_career_transition_framework(demo_user)
        seed_creator_framework(demo_user)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully reset demo account '{username}' with 3 starter frameworks."
            )
        )
