from django.contrib import admin
from .models import (
    Organization,
    Category,
    Module,
    Level,
    ModuleAttributes,
    ModuleActivity,
    LevelActivity,
    Attempt,
    UserActivity,
)
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import FieldListFilter


def custom_titled_filter(title):
    class Wrapper(admin.FieldListFilter):
        def __new__(cls, *args, **kwargs):
            instance = admin.FieldListFilter.create(*args, **kwargs)
            instance.title = title
            return instance

    return Wrapper


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "id", "logo"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "updated_at"]


@admin.register(Level)
class SubModuleAdmin(admin.ModelAdmin):
    list_display = ["id", "module", "name", "level", "category"]
    list_filter = ["module", "category"]


@admin.register(ModuleAttributes)
class ModuleAttributesAdmin(admin.ModelAdmin):
    list_display = [
        "module",
        "organization",
        "max_attempts",
        "passing_score",
    ]


@admin.register(ModuleActivity)
class ModuleActivityAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "module",
        "organization",
        "assigned_on",
        "complete",
        "passed",
        "complete_date",
        "pass_date",
    ]
    list_filter = [
        "module",
        ("user__organization__name", custom_titled_filter("organization")),
        "complete",
        "passed",
    ]

    def organization(self, obj):
        if obj.user and obj.user.organization:
            return obj.user.organization.name
        return None


@admin.register(LevelActivity)
class LevelActivityAdmin(admin.ModelAdmin):
    list_display = ["id", "module_activity", "organization", "level", "complete"]
    list_filter = [
        "level",
        (
            "module_activity__user__organization__name",
            custom_titled_filter("organization"),
        ),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "module_activity__user",
            )
        )

    def organization(self, obj):
        user = obj.module_activity.user
        if user and user.organization:
            return user.organization.name
        return None


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "level_activity",
        "organization",
        "attempt_number",
        "start_time",
        "end_time",
        "duration",
        "created_at",
    ]

    list_filter = (
        "level_activity",
        (
            "level_activity__module_activity__user__organization__name",
            custom_titled_filter("organization"),
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "level_activity__module_activity__user",
            )
        )

    def user(self, obj):
        user = obj.level_activity.module_activity.user
        if user:
            return user.user_id
        return None

    user.short_description = "User ID"

    def organization(self, obj):
        user = obj.level_activity.module_activity.user
        if user and user.organization:
            return user.organization.name
        return None


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ["user", "module", "organization", "start_time", "end_time"]
    list_filter = [
        "module",
        ("user__organization__name", custom_titled_filter("organization")),
    ]

    def organization(self, obj):
        if obj.user and obj.user.organization:
            return obj.user.organization.name
        return None
