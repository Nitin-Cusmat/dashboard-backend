import random
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import datetime
from django.utils import timezone
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist
from .models import PasswordResetToken
from rest_framework import authentication, exceptions, serializers
from rest_framework.authtoken.models import Token
from .serializers import PasswordResetAuthenticationSerializer


class Communication:
    def trigger_email(html_content, subject, to_email_id, from_email_id):
        return send_mail(
            subject=subject,
            message="",
            from_email=from_email_id,
            recipient_list=to_email_id,
            fail_silently=False,
            html_message=html_content,
        )


class PasswordResetAuthentication(authentication.BaseAuthentication):
    """
    Password reset authentication class
    """

    serializer_class = PasswordResetAuthenticationSerializer

    def authenticate(self, request):
        token = request.META.get("HTTP_PASSWORD_RESET_TOKEN")

        if not token:
            return None

        serializer = self.serializer_class(data={"token": token})

        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)

        token_object = PasswordResetToken.objects.filter(token=token).first()

        if not token_object:
            raise exceptions.AuthenticationFailed("Invalid token", "invalid_token")

        # check for token expiration
        if token_object.expires_at <= timezone.now():
            raise exceptions.AuthenticationFailed("Token Expired", "token_expired")

        user_object = token_object.user

        return (user_object, token_object)

