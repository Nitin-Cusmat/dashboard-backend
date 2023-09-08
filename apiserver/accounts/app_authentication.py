from django.contrib.auth.backends import ModelBackend
from .models import User
from django.contrib.auth.hashers import check_password


class AppAuthenticationBackend(ModelBackend):
    def authenticate(
        self, request, user_id=None, organization_id=None, password=None, **kwargs
    ):
        try:
            user = User.objects.get(
                user_id=user_id,
                organization_id=organization_id,
                deleted=False,
                active=True,
            )
            if (
                check_password(password, user.password)
                and user.access_type == "Learner"
            ):
                return user
        except User.DoesNotExist:
            pass

        return None
