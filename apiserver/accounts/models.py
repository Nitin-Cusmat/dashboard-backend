from django.contrib.auth.models import (
    BaseUserManager,
    PermissionsMixin,
    AbstractBaseUser,
)
from django.db import models
from datetime import timedelta
from django.utils import timezone
from django.db.models.deletion import CASCADE
from django.core.validators import RegexValidator
from organizations.models import Organization
import uuid
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

phone_regex = RegexValidator(
    regex=r"^\+?1?\d{9,15}$",
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
)


class UserManager(BaseUserManager):
    def create_user(self, email, password=None):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(email=self.normalize_email(email))

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_staffuser(self, email, password):
        """
        Creates and saves a staff user with the given email and password.
        """
        user = self.create_user(
            email,
            password=password,
        )
        user.staff = True
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email and password.
        """
        user = self.create_user(
            email,
            password=password,
        )
        user.staff = True
        user.admin = True
        user.is_superuser = True

        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    ORG_ADMIN = "Admin"
    ORG_LEARNER = "Learner"
    ORG_TRAINER = "Trainer"
    CUSMAT_ADMIN = "Cusmat"

    MALE = "M"
    FEMALE = "F"
    GENDER = ((MALE, "Male"), (FEMALE, "Female"))

    USER_TYPES = (
        (ORG_ADMIN, "Admin"),
        (ORG_LEARNER, "Learner"),
        (ORG_TRAINER, "Trainer"),
        (CUSMAT_ADMIN, "Cusmat"),
    )
    objects = UserManager()
    email = models.EmailField(unique=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    work_location = models.CharField(max_length=250, blank=True, null=True)
    access_type = models.CharField(
        max_length=64,
        choices=USER_TYPES,
        verbose_name="User Type",
        default=USER_TYPES[1][1],
        help_text="Organization User Type",
    )
    user_id = models.CharField(
        max_length=100,
        help_text="Will be treated as mobile no. for Immertive Organization",
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=64, choices=GENDER, default=GENDER[0][1], blank=True, null=True
    )
    course = models.CharField(max_length=100, blank=True, null=True)
    batch = models.CharField(max_length=100, blank=True, null=True)
    roll_no = models.CharField(max_length=100, blank=True, null=True)
    institute = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    vr_lab = models.CharField(max_length=100, blank=True, null=True)
    active = models.BooleanField(default=True)
    staff = models.BooleanField(default=False)
    admin = models.BooleanField(default=False)  # a superuser
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.SET_NULL, null=True, blank=True
    )

    deleted = models.BooleanField(default=False)
    USERNAME_FIELD = "email"

    def clean(self):
        super().clean()

        if (
            self.organization
            and self.organization.name.lower() == "immertive"
            and self.access_type == "Learner"
        ):
            field_names = [
                "date_of_birth",
                "gender",
                "course",
                "batch",
                "roll_no",
                "institute",
                "city",
                "state",
                "vr_lab",
            ]
            error_dict = {}
            error_msg = _("This field is required")
            for field in field_names:
                if not getattr(self, field):
                    error_dict[field] = error_msg
            if error_dict:
                raise ValidationError(error_dict)

    def get_full_name(self):
        # The user is identified by their email address
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        # The user is identified by their email address
        return self.first_name

    def __str__(self):
        return self.get_full_name()

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_admin(self):
        "Is the user a admin member?"
        return self.admin

    @property
    def is_staff(self):
        "Is the user a staff member?"
        return self.staff

    @property
    def is_active(self):
        "Is the user active?"
        return self.active

    class Meta:
        unique_together = [
            ["organization", "user_id"],
        ]


def get_default_my_date():
    return timezone.now() + timedelta(hours=24)


class PasswordResetToken(models.Model):
    """
    Password Reset Token model
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_default_my_date)

    def __str__(self):
        return str(self.token)
