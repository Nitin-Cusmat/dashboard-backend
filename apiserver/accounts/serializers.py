from rest_framework import serializers
from .models import User
from organizations.models import Organization, ModuleActivity
from rest_framework.exceptions import ValidationError
from datetime import datetime


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "logo", "slug"]


class UserProfileSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer()

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "department",
            "designation",
            "work_location",
            "access_type",
            "user_id",
            "organization",
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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "designation",
            "department",
            "work_location",
            "user_id",
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


class CreateOrUpdateeUserFromCSVSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=False)
    organization_id = serializers.IntegerField(required=True)

    def validate_file(self, value):
        if not value.name.endswith(".csv"):
            raise ValidationError("Only CSV file is accepted")


class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password", "placeholder": "Password"},
    )
    organization_id = serializers.IntegerField(required=True)

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "designation",
            "department",
            "work_location",
            "access_type",
            "user_id",
            "password",
            "organization_id",
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


class LoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(max_length=100, required=True)

    class Meta:
        model = User
        fields = ["email", "password"]


class UserLoginSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(required=True)
    password = serializers.CharField(max_length=100, required=True)
    organization_id = serializers.IntegerField(required=True)

    class Meta:
        model = User
        fields = ["user_id", "password", "organization_id"]


class ModuleActivitySerializer(serializers.ModelSerializer):
    module_name = serializers.SerializerMethodField()

    def get_module_name(self, instance):
        return instance.module.module.name

    class Meta:
        model = ModuleActivity
        fields = ["assigned_on", "complete", "id", "module_name"]


class UserDetailsSerializer(serializers.ModelSerializer):
    user_details = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["user_details", "modules"]

    def get_user_details(self, instance):
        return UserProfileSerializer(instance).data

    def get_modules(self, instance):
        modules = instance.moduleactivity_set.filter(active=True)
        return ModuleActivitySerializer(modules, many=True).data


class ForgotPasswordSerializer(serializers.Serializer):
    """
    Forgot password serializer for forgot password API.
    Validates email passed by the user.
    """

    email = serializers.EmailField()

    def validate_email(self, data):
        """
        function to validate email
        """
        if User.objects.filter(email=data).exists():
            return data
        else:
            raise serializers.ValidationError("Email not registered")


class PasswordResetSerializer(serializers.Serializer):
    """
    Password reset serializer for password reset API.
    Validates if new password is equal to confirm password.
    Validates password strength.
    """

    new_password = serializers.CharField()
    confirm_password = serializers.CharField()

    def validate(self, data):
        if data["new_password"] == data["confirm_password"]:
            return data
        else:
            raise serializers.ValidationError("Password mismatch")


class PasswordResetAuthenticationSerializer(serializers.Serializer):
    """
    Password reset authentication serializer for password
    reset authentication custom class.
    Checks if the token passed is a valid uuid field.
    """

    token = serializers.UUIDField()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    new_password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    organization_id = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "user_id",
            "designation",
            "department",
            "work_location",
            "password",
            "new_password",
            "confirm_password",
            "organization_id",
        ]


class LearnersProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(required=True)
    organization_id = serializers.IntegerField(required=True)

    class Meta:
        model = User
        fields = ["user_id", "organization_id"]


class CreateUserUsingCSVSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.CharField(required=False)
    gender = serializers.CharField(required=False)
    course = serializers.CharField(required=False)
    batch = serializers.CharField(required=False)
    roll_no = serializers.CharField(required=False)
    institute = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    state = serializers.CharField(required=False)
    vr_lab = serializers.CharField(required=False)
    password = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "designation",
            "department",
            "work_location",
            "user_id",
            "date_of_birth",
            "gender",
            "course",
            "batch",
            "roll_no",
            "institute",
            "city",
            "state",
            "vr_lab",
            "password",
        ]
