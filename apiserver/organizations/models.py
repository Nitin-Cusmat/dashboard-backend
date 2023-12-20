from django.db import models
from django.contrib.postgres.fields import JSONField
from datetime import timedelta
import os


def logo_path(instance, filename):
    return "{}{}".format(instance.name, os.path.splitext(filename)[1])


class Organization(models.Model):
    name = models.CharField(max_length=120)
    logo = models.ImageField(upload_to=logo_path, blank=True)
    slug = models.SlugField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    def __str__(self):
        return self.name


class Module(models.Model):
    name = models.CharField(max_length=120)
    duration = models.DurationField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=150)
    order = models.SmallIntegerField()

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Level(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    level = models.PositiveSmallIntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE)

    def __str__(self):
        return self.name + " - " + self.module.name


class ModuleAttributes(models.Model):
    module = models.ForeignKey(Module, related_name="module", on_delete=models.CASCADE)
    organization = models.ForeignKey(
        Organization, related_name="module_organization", on_delete=models.CASCADE
    )
    max_attempts = models.PositiveIntegerField(null=True, blank=True)
    passing_score = models.DecimalField(
        decimal_places=2, max_digits=5, null=True, blank=True
    )
    ideal_mistake = models.DecimalField(
        decimal_places=2, max_digits=5, null=True, blank=True
    )
    mistakes = models.JSONField(default=dict, null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.module.name

    class Meta:
        verbose_name_plural = "Module Attributes"


class ModuleActivity(models.Model):
    user = models.ForeignKey(to="accounts.User", on_delete=models.CASCADE)
    module = models.ForeignKey(
        ModuleAttributes,
        on_delete=models.CASCADE,
        related_name="model_attributes",
    )
    assigned_on = models.DateTimeField()
    active = models.BooleanField(default=True)
    passed = models.BooleanField(default=False)
    complete = models.BooleanField(default=False)
    complete_date = models.DateTimeField(null=True, blank=True)
    pass_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.get_full_name() + " " + self.module.module.name

    class Meta:
        verbose_name_plural = "Module Activities"


class LevelActivity(models.Model):
    module_activity = models.ForeignKey(ModuleActivity, on_delete=models.CASCADE)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)
    complete = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Level Activities"

    def __str__(self):
        return self.level.name + " - " + self.module_activity.module.module.name


class Attempt(models.Model):
    level_activity = models.ForeignKey(LevelActivity, on_delete=models.CASCADE)
    attempt_number = models.PositiveIntegerField()
    data = models.JSONField(default=dict)
    duration = models.DurationField(default=timedelta)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "level_activity",
            "attempt_number",
        )


# class Assessment(models.Model):
#     module_activity = models.ForeignKey(ModuleActivity, on_delete=models.CASCADE)
#     start_time = models.DateTimeField()
#     end_time = models.DateTimeField()
#     duration = models.DurationField()
#     score = models.DecimalField(decimal_places=2, max_digits=5)
#     earned_certificate = models.BooleanField(default=False)
#     rewarded_xp = models.BooleanField(default=False)
#     certificate_timestamp = models.DateTimeField()
#     attempts_count = models.PositiveIntegerField()
#     xp = models.IntegerField()
#     mistakes = models.JSONField(default=dict)
#     complete = models.BooleanField(default=False)


class Feedback(models.Model):
    module_activity = models.ForeignKey(ModuleActivity, on_delete=models.CASCADE)
    rating = models.SmallIntegerField()
    comments = models.TextField()
    timestamp = models.DateTimeField()


class UserActivity(models.Model):
    user = models.ForeignKey(to="accounts.User", on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration = models.DurationField()
    log_event = models.CharField(max_length=100)  # give some choices
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "User Activities"
