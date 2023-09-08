from typing import Any, Dict, List, Optional, Tuple
from django.contrib import admin
from django.http.request import HttpRequest
from .models import User, PasswordResetToken
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.hashers import make_password, identify_hasher
from django.contrib.auth.models import Group


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        # Hash the password before saving
        try:
            hasher = identify_hasher(obj.password)
        except:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)

    list_display = [
        "id",
        "first_name",
        "user_id",
        "designation",
        "department",
        "work_location",
        "deleted",
    ]
    list_filter = ["organization"]

    fieldsets = (
        (None, {"fields": ("first_name", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "last_name",
                    "email",
                    "organization",
                    "designation",
                    "department",
                    "work_location",
                    "access_type",
                    "user_id",
                )
            },
        ),
        (
            _("Immertive Org Fields"),
            {
                "fields": (
                    "date_of_birth",
                    "gender",
                    "course",
                    "batch",
                    "roll_no",
                    "institute",
                    "city",
                    "state",
                    "vr_lab",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "active",
                    "staff",
                    "admin",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
    )


admin.site.unregister(Group)


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ["user"]
    ordering = ["created_at"]
