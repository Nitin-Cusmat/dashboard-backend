from django.contrib.auth.backends import ModelBackend
from .models import User


class DashboardAuthenticationBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        if email is None or password is None:
            return None

        try:
            user = User.objects.get(email__iexact=email, deleted=False, active=True)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            if user.access_type == "Learner":
                return None
            return user
