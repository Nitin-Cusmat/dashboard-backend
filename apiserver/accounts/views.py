# from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from django.core.paginator import Paginator
from django.http import JsonResponse
from .models import User, PasswordResetToken
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.conf import settings
from rest_framework import serializers
from django.template.loader import render_to_string
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError
import pytz
from .serializers import (
    UserProfileSerializer,
    CreateOrUpdateeUserFromCSVSerializer,
    CreateUserSerializer,
    LoginSerializer,
    UserSerializer,
    UserDetailsSerializer,
    ForgotPasswordSerializer,
    PasswordResetSerializer,
    UserLoginSerializer,
    ProfileUpdateSerializer,
    LearnersProfileSerializer,
    CreateUserUsingCSVSerializer,
)
from django.http import HttpResponse
import csv
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
import re
from django.utils import timezone
from django.core.mail import send_mail
from .authentication import DashboardAuthenticationBackend
from .app_authentication import AppAuthenticationBackend
import django_filters.rest_framework
from rest_framework import filters
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework import generics, permissions
from organizations.models import Organization
from accounts.utils import PasswordResetAuthentication
from .filters import UsersFilter
from django.contrib.auth.hashers import check_password
from datetime import datetime
from django.db.models import Q

auth_backend = DashboardAuthenticationBackend()
app_auth_backend = AppAuthenticationBackend()


class IsOrgOwnerOrStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        has_perm = False
        if request.user.is_authenticated and request.user.access_type != "Learner":
            has_perm = True
        return has_perm


class IsOrgTrainee(permissions.BasePermission):
    def has_permission(self, request, view):
        has_perm = False
        if (
            request.user.is_authenticated
            and request.user.access_type == "Learner"
            and request.user.active
        ):
            has_perm = True
        return has_perm


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        has_perm = False
        if request.user.is_authenticated and request.user.access_type == "Cusmat":
            has_perm = True
        return has_perm


class UsersView(ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsOrgOwnerOrStaff]
    filter_backends = [
        django_filters.rest_framework.DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]
    filterset_class = UsersFilter
    filterset_fields = [
        "user_id",
        "first_name",
        "last_name",
        "designation",
        "department",
        "work_location",
        "organization_id",
    ]
    search_fields = [
        "first_name",
        "last_name",
        "user_id",
        "designation",
        "department",
        "work_location",
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
    ordering_fields = [
        "first_name",
        "last_name",
        "user_id",
        "designation",
        "department",
        "work_location",
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

    def get_queryset(self):
        LEARNER = "Learner"
        org_id = self.request.query_params.get("organization_id", None)
        queryset = User.objects.filter(
            deleted=False, active=True, access_type=LEARNER, organization__id=org_id
        ).order_by("-created_at")
        return queryset


class UsersDeleteView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def delete(self, request):
        pk_ids = request.data.get("pk_ids", None)
        if pk_ids is None and pk_ids != "":
            return Response(status=400, data={"error": "No user were found for delete"})
        ids = [int(pk) for pk in pk_ids.split(",")]
        User.objects.filter(id__in=ids).update(active=False, deleted=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserProfileView(RetrieveUpdateAPIView):
    lookup_field = "id"
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsOrgOwnerOrStaff]

    def retrieve(self, request, *args, **kwargs):
        return Response(
            UserProfileSerializer(self.queryset.get(id=kwargs.get("id"))).data
        )


class DownloadTemplate(APIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def get(self, request, *args, **kwargs):
        mode = kwargs.get("str", None)
        org_id = kwargs.get("org_id", None)
        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return Response(status=400, data={"error": "Given organization not found"})
        instructions = [
            "Date must be in a YYYY-MM-DD format.",
            "Mobile No. should be 10 digits only.",
            "Gender can be either Male or Female. Default is Male",
        ]
        immertive_extra_create_headers = [
            "Date of Birth",
            "Gender",
            "Course",
            "Batch",
            "Roll No",
            "Institute",
            "City",
            "State",
            "VR Lab",
        ]
        immertive_extra_update_headers = [
            "Course",
            "Batch",
            "Roll No",
            "Institute",
            "City",
            "State",
            "VR Lab",
        ]
        is_immertive = organization.name.lower() == "immertive"
        if mode == "create":
            headers = [
                "First Name",
                "Last Name",
                "User Id",
                "Designation",
                "Department",
                "Work Location",
                "Password",
            ]
            if is_immertive:
                headers.remove("Password")
                headers.remove("User Id")
                headers = (
                    headers[:2]
                    + ["Mobile No"]
                    + headers[2:]
                    + immertive_extra_create_headers
                    + ["PIN"]
                )

            filename = "UserSampleInfo.csv"
        elif mode == "update":
            headers = [
                "User Id",
                "Designation",
                "Department",
                "Work Location",
            ]
            if is_immertive:
                headers.remove("User Id")
                headers = ["Mobile No"] + headers + immertive_extra_update_headers
            filename = "UpdateUserSampleInfo.csv"
        else:
            return Response(status=400, data={"error": "Encountered invalid slug"})

        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": "attachment; filename={}".format(filename)},
        )
        writer = csv.writer(response)
        if is_immertive and mode == "create":
            for instruction in instructions:
                writer.writerow([instruction])
            writer.writerow([])
        writer.writerow(headers)
        return response


class CreateUpdateUsersFromCSV(APIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = CreateOrUpdateeUserFromCSVSerializer

    def validate_mobile_no(mobile_number):
        if len(mobile_number) == 10:
            # Check if all characters in the mobile number are digits
            if mobile_number.isdigit():
                # Check if the first digit is between 6 and 9
                if 6 <= int(mobile_number[0]) <= 9:
                    return True

        return False

    def post(self, request, format=None, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        org_id = request.POST.get("organization_id")
        try:
            organization = Organization.objects.get(id=org_id)
        except:
            return Response(
                status=400,
                data={
                    "error": "Given Organization does not exists. Please contact your organization admin"
                },
            )
        is_immertive = organization.name.lower() == "immertive"
        if is_immertive:
            actual_headings = [
                "First Name",
                "Last Name",
                "Mobile No",
                "Designation",
                "Department",
                "Work Location",
                "Date of Birth",
                "Gender",
                "Course",
                "Batch",
                "Roll No",
                "Institute",
                "City",
                "State",
                "VR Lab",
                "PIN",
            ]
        else:
            actual_headings = [
                "First Name",
                "Last Name",
                "User Id",
                "Designation",
                "Department",
                "Work Location",
                "Password",
            ]

        file = request.FILES["file"]
        decoded_file = file.read().decode("utf-8").splitlines()
        reader = csv.reader(decoded_file, delimiter=",")
        start = 5 if is_immertive else 0
        if is_immertive:
            try:
                for _ in range(4):
                    next(reader)
            except StopIteration:
                return Response(
                    status=400,
                    data={"error": "CSV file is empty or has no headers"},
                )
        headings = next(reader)
        transformed_headers = []

        for _, heading in enumerate(headings):
            transformed_headers.append(heading.lower().replace(" ", "_"))
        rows = list(reader)
        if not rows:
            return Response(
                status=400,
                data={"error": "Empty file found"},
            )

        with transaction.atomic():
            if actual_headings != headings:
                return Response(
                    status=400,
                    data={
                        "error": "It looks like the headers in the CSV file have been changed. \
                            Please make sure to use the original template and try again."
                    },
                )
            for row_index, row in enumerate(rows, start=start):
                if is_immertive:
                    replacements = {"mobile_no": "user_id", "pin": "password"}
                    transformed_headers = [
                        replacements.get(item, item) for item in transformed_headers
                    ]
                transformed_data = dict(zip(transformed_headers, row))
                user_creation_serializer = CreateUserUsingCSVSerializer(
                    data=transformed_data
                )
                if not user_creation_serializer.is_valid():
                    transaction.set_rollback(True)
                    empty_column_names = list(user_creation_serializer.errors.keys())
                    if is_immertive:
                        if "user_id" in empty_column_names:
                            user_id_index = empty_column_names.index("user_id")
                            empty_column_names[user_id_index] = "mobile_no"
                        if "password" in empty_column_names:
                            password_index = empty_column_names.index("password")
                            empty_column_names[password_index] = "pin"
                    if len(empty_column_names) == 1:
                        formatted_names = (
                            empty_column_names[0].replace("_", " ").capitalize()
                        )
                    else:
                        formatted_names = (
                            ", ".join(
                                [
                                    field.replace("_", " ").capitalize()
                                    for field in empty_column_names[:-1]
                                ]
                            )
                            + f" and {empty_column_names[-1].replace('_', ' ').capitalize()}"
                        )

                    return Response(
                        status=400,
                        data={
                            "error": "Required {} {} {} missing at row {}".format(
                                "field" if len(empty_column_names) == 1 else "fields",
                                formatted_names,
                                "is" if len(empty_column_names) == 1 else "are",
                                row_index + 1,
                            ),
                        },
                    )
                row = dict(zip(transformed_headers, row))
                if "user_id" in row:
                    key = "user_id"
                else:
                    key = "mobile_no"
                    if key in row and not CreateUpdateUsersFromCSV.validate_mobile_no(
                        row[key]
                    ):
                        transaction.set_rollback(True)
                        return Response(
                            status=400,
                            data={
                                "error": "Invalid mobile number at row {}".format(
                                    row_index + 1
                                )
                            },
                        )
                if "gender" in row:
                    gender = row.get("gender", None)
                    if gender is None or gender == "":
                        gender = "M"
                else:
                    gender = None

                user_data = {
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "designation": row["designation"],
                    "department": row["department"],
                    "work_location": row["work_location"],
                    "access_type": "Learner",
                    "email": row["first_name"].lower()
                    + str(row[key]).lower()
                    + "@"
                    + organization.name.replace(" ", "-").lower()
                    + ".com",
                    "date_of_birth": datetime.strptime(
                        row["date_of_birth"], "%Y-%m-%d"
                    ).date()
                    if "date_of_birth" in row
                    else None,
                    "gender": gender,
                    "course": row.get("course", None),
                    "batch": row.get("batch", None),
                    "roll_no": row.get("roll_no", None),
                    "institute": row.get("institute", None),
                    "city": row.get("city", None),
                    "state": row.get("state", None),
                    "vr_lab": row.get("vr_lab", None),
                    "created_by": self.request.user,
                    "password": make_password(row.get("pin", None))
                    if "pin" in row
                    else make_password(row.get("password", None)),
                    "deleted": False,
                    "active": True,
                }
                try:
                    User.objects.update_or_create(
                        user_id=row[key],
                        organization=organization,
                        deleted=True,
                        defaults=user_data,
                    )

                except IntegrityError:
                    transaction.set_rollback(True)
                    return Response(
                        status=400,
                        data={
                            "error": "The user with given {} {} at row {} for user {} already exists".format(
                                " ".join(word.capitalize() for word in key.split("_")),
                                row[key],
                                row_index + 1,
                                row["first_name"] + " " + row["last_name"],
                            )
                        },
                    )

                except ValueError:
                    transaction.set_rollback(True)
                    return Response(
                        status=400,
                        data={
                            "error": "Invalid date format. Expected format: YYYY-MM-DD at row {}".format(
                                row_index + 1
                            )
                        },
                    )

                except Exception:
                    transaction.set_rollback(True)
                    return Response(
                        status=400,
                        data={"error": "Something went wrong. Please try again later."},
                    )

        return Response(status=201, data={"message": "Users created successfully"})

    def put(self, request, format=None, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        org_id = request.POST.get("organization_id")

        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return Response(
                status=400,
                data={
                    "error": "Given Organization does not exist. Please contact your organization admin"
                },
            )

        is_immertive = organization.name.lower() == "immertive"
        updatable_fields = ["user_id", "designation", "department", "work_location"]
        if is_immertive:
            updatable_fields.extend(
                [
                    "mobile_no",
                    "designation",
                    "department",
                    "work_location",
                    "course",
                    "batch",
                    "roll_no",
                    "institute",
                    "city",
                    "state",
                    "vr_lab",
                ]
            )
            updatable_fields.remove("user_id")

        file = request.FILES["file"]
        decoded_file = file.read().decode("utf-8").splitlines()
        reader = csv.reader(decoded_file, delimiter=",")

        headings = next(reader)
        transformed_headers = []
        for _, heading in enumerate(headings):
            transformed_headers.append(heading.lower().replace(" ", "_"))

        rows = list(reader)
        if not rows:
            return Response(
                status=400,
                data={"error": "Empty file found"},
            )

        with transaction.atomic():
            if set(updatable_fields) != set(transformed_headers):
                return Response(
                    status=400,
                    data={
                        "error": "It looks like the headers in the CSV file have been changed. \
                            Please make sure to use the original template and try again."
                    },
                )

            for row_index, row in enumerate(rows, start=1):
                if is_immertive:
                    replacements = {"mobile_no": "user_id"}
                    transformed_headers = [
                        replacements.get(item, item) for item in transformed_headers
                    ]
                transformed_data = dict(zip(transformed_headers, row))
                user_id = transformed_data.get("user_id")
                if not user_id:
                    return Response(
                        status=400,
                        data={
                            "error": "Required field {} is missing at row {}".format(
                                "mobile_no" if is_immertive else "user_id",
                                row_index + 1,
                            )
                        },
                    )

                try:
                    user = User.objects.get(
                        user_id=user_id, organization=organization, deleted=False
                    )
                except User.DoesNotExist:
                    return Response(
                        status=400,
                        data={
                            "error": "User with {} {} does not exist in the organization".format(
                                "mobile_no" if is_immertive else "user_id", user_id
                            )
                        },
                    )
                for field in transformed_data:
                    new_value = transformed_data[field]
                    if new_value != "":
                        user.__dict__[field] = new_value

                user.save()

        return Response(status=200, data={"message": "Users updated successfully"})


class CreateUser(generics.CreateAPIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = CreateUserSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization_id = serializer.validated_data["organization_id"]
        organization = Organization.objects.get(id=organization_id)
        first_name = serializer.validated_data["first_name"]
        last_name = serializer.validated_data["last_name"]
        designation = serializer.validated_data["designation"]
        department = serializer.validated_data["department"]
        work_location = serializer.validated_data.get("work_location", None)
        # Immertive Extra Fields
        date_of_birth = serializer.validated_data.get("date_of_birth", None)
        gender = serializer.validated_data.get("gender", None)
        course = serializer.validated_data.get("course", None)
        batch = serializer.validated_data.get("batch", None)
        roll_no = serializer.validated_data.get("roll_no", None)
        institute = serializer.validated_data.get("institute", None)
        city = serializer.validated_data.get("city", None)
        state = serializer.validated_data.get("state", None)
        vr_lab = serializer.validated_data.get("vr_lab", None)
        user_id = serializer.validated_data["user_id"]
        password = serializer.validated_data["password"]

        try:
            user = User.objects.create(
                first_name=first_name,
                last_name=last_name,
                designation=designation,
                department=department,
                work_location=work_location,
                user_id=user_id,
                organization=organization,
                access_type="Learner",
                email=first_name.lower()
                + str(user_id).lower()
                + "@"
                + organization.name.replace(" ", "-").lower()
                + ".com",
                date_of_birth=date_of_birth,
                gender=gender,
                course=course,
                batch=batch,
                roll_no=roll_no,
                institute=institute,
                city=city,
                state=state,
                vr_lab=vr_lab,
                created_by=self.request.user,
            )
            user.set_password(password)
            user.save()
        except IntegrityError as e:
            existing_user = User.objects.filter(
                organization=organization,
                user_id=user_id,
                deleted=True,
            ).first()
            if existing_user:
                existing_user.deleted = False
                existing_user.active = True
                existing_user.first_name = first_name
                existing_user.last_name = last_name
                existing_user.designation = designation
                existing_user.department = department
                existing_user.work_location = work_location
                # Immertive Extra Fields
                existing_user.date_of_birth = date_of_birth
                existing_user.gender = gender
                existing_user.course = course
                existing_user.batch = batch
                existing_user.roll_no = roll_no
                existing_user.institute = institute
                existing_user.city = city
                existing_user.state = state
                existing_user.vr_lab = vr_lab
                existing_user.user_id = user_id
                existing_user.set_password(password)
                existing_user.save()
            else:
                return Response(status=400, data={"message": "User already exists"})
        except Exception as e:
            return Response(status=400, data={"message": str(e)})
        return Response(status=200, data={"message": "User created successfully"})


class PasswordResetAPIView(APIView):
    """
    Authenticates password reset token.
    Sets new password for the user.
    Returns 200 OK with a success message.
    """

    authentication_classes = [PasswordResetAuthentication]

    serializer_class = PasswordResetSerializer

    def post(self, request):
        """
        post method
        """
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)

        user = request.user
        token = str(request.auth)
        if not PasswordResetToken.objects.filter(
            token=token, expires_at__gte=timezone.now()
        ).exists():
            raise PermissionDenied("Invalid token")

        validated_data = serializer.validated_data

        # Update the password.
        user.set_password(validated_data["new_password"])
        user.save()

        # Delete password reset and auth token after reset is success.
        PasswordResetToken.objects.filter(token=token).delete()

        return Response("Password changed succesfully")


class ForgotPassword(generics.GenericAPIView):
    serializer_class = ForgotPasswordSerializer

    def send_reset_mail(self, email):
        """
        task to send reset password email
        """
        user = User.objects.get(email=email)

        if user and user.access_type == "Learner":
            raise PermissionDenied(
                "You are not authorized to perform this action. Please contact your organization admin."
            )
        # Generate user token
        reset_token = PasswordResetToken.objects.get_or_create(
            user=user, expires_at__gte=timezone.now()
        )
        password_reset_url = f"{settings.PASSWORD_RESET_URL}{str(reset_token[0].token)}"
        html_message = render_to_string(
            "reset_email.html",
            {
                "first_name": user.first_name,
                "password_reset_url": password_reset_url,
            },
        )
        send_mail(
            subject="Reset Your Cusmat Dashboard Password",
            message=f"Click on {password_reset_url} to reset your password. ",
            from_email=f"Cusmat <{settings.SERVER_EMAIL}>",
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )

    def post(self, request):
        serializer = self.serializer_class(data=self.request.data)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        email = serializer.validated_data["email"]
        self.send_reset_mail(email)
        return Response("mail sent successfully", status=200)


class ValidatePasswordToken(APIView):
    authentication_classes = [PasswordResetAuthentication]

    def get(self, request):
        token = str(request.auth)
        try:
            user_token = PasswordResetToken.objects.get(
                token=token, expires_at__gte=timezone.now()
            )
        except PasswordResetToken.DoesNotExist:
            raise PermissionDenied("Invalid token")
        user_org_logo = None
        if user_token.user.organization:
            user_org_logo = user_token.user.organization.logo.url
        return Response(data=user_org_logo, status=200)


class AdminLoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        user = auth_backend.authenticate(
            request=request, email=email, password=password
        )
        if not user:
            return Response(status=401, data={"message": "Invalid email or password"})

        jwt = RefreshToken.for_user(user)
        if user.organization and user.organization.end_date:
            tz = pytz.timezone("Asia/Kolkata")
            ist_date = user.organization.end_date.astimezone(tz)
            jwt["license_expiry_date"] = ist_date.strftime("%Y-%m-%d %H:%M:%S")
        data = {
            "access": str(jwt.access_token),
            "refresh": str(jwt),
        }
        return Response(status=200, data=data)


class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data["user_id"]
        organization_id = serializer.validated_data["organization_id"]
        password = serializer.validated_data["password"]
        user = app_auth_backend.authenticate(
            request=request,
            user_id=user_id,
            password=password,
            organization_id=organization_id,
        )
        if not user:
            return Response(status=401, data={"message": "Invalid user_id or password"})

        if user.organization and user.organization.end_date < timezone.now():
            return Response(
                status=200,
                data={
                    "error": "Your license is expired. Please contact cusmat administrator."
                },
            )

        user_info = UserSerializer(
            User.objects.get(organization_id=organization_id, user_id=user_id)
        )
        data = {
            "refresh": str(RefreshToken.for_user(user)),
            "access": str(RefreshToken.for_user(user).access_token),
            "user_info": user_info.data,
        }
        return Response(status=200, data=data)


class UserDetailsView(generics.GenericAPIView):
    serializer_class = LearnersProfileSerializer
    permission_classes = [IsOrgOwnerOrStaff]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = serializer.validated_data["user_id"]
        organization_id = serializer.validated_data["organization_id"]
        try:
            user = User.objects.get(user_id=user_id, organization_id=organization_id)
        except:
            return Response(status=400, data={"error": "user not found"})
        user_details = UserDetailsSerializer(user)
        return Response(status=200, data=user_details.data)


class DownloadListView(generics.GenericAPIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def convert_dict(dict):
        for key, value in dict.items():
            dict[key] = value[0]
        return dict

    def get(self, request, *args, **kwargs):
        organization_id = self.request.query_params.get("organization_id", None)
        query_params = dict(self.request.query_params)
        filtered_query_params = DownloadListView.convert_dict(query_params)
        if organization_id is None:
            return Response(status=400, data={"error": "No users found"})
        organization_users = User.objects.filter(
            access_type="Learner", deleted=False, active=True, **filtered_query_params
        )
        is_immertive = organization_users[0].organization.name.lower() == "immertive"
        if is_immertive:
            headers = [
                "Mobile No",
                "First Name",
                "Last Name",
                "Designation",
                "Department",
                "Work Location",
                "Date of Birth",
                "Gender",
                "Course",
                "Batch",
                "Roll No.",
                "Institute",
                "City",
                "State",
                "VR Lab",
            ]
        else:
            headers = [
                "User Id",
                "First Name",
                "Last Name",
                "Designation",
                "Department",
                "Work Location",
            ]
        filename = str(request.user.organization) + " Users.csv"
        response = HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": "attachment; filename={}".format(filename)},
        )
        writer = csv.writer(response)
        writer.writerow(headers)
        for organization_user in organization_users:
            data = [
                organization_user.user_id,
                organization_user.first_name,
                organization_user.last_name,
                organization_user.designation,
                organization_user.department,
                organization_user.work_location,
            ]
            if is_immertive:
                data.extend(
                    [
                        organization_user.date_of_birth,
                        organization_user.gender,
                        organization_user.course,
                        organization_user.batch,
                        organization_user.roll_no,
                        organization_user.institute,
                        organization_user.city,
                        organization_user.state,
                        organization_user.vr_lab,
                    ]
                )
            writer.writerow(data)

        return response


class UpdateUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsOrgOwnerOrStaff]

    def get_object(self):
        user_id = self.kwargs["user_id"]
        return User.objects.get(user_id=user_id)


class ProfileUpdateAPIView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = ProfileUpdateSerializer

    def patch(self, request):
        data = request.data
        user_id = data.get("user_id", None)
        organization_id = data.get("organization_id", None)

        if user_id is None:
            return Response(
                status=400,
                data={"error": "user_id is required"},
            )

        if organization_id is None:
            return Response(
                status=400,
                data={"error": "organization_id is required"},
            )

        try:
            trainer = User.objects.get(
                ~Q(access_type="Learner"),
                user_id=user_id,
                organization__id=organization_id,
            )
        except:
            return Response(
                status=400,
                data={"error": "Account not found for the given user"},
            )

        serializer = self.serializer_class(
            data=request.data, partial=True, instance=trainer
        )
        serializer.is_valid(raise_exception=True)

        password = data.get("password", None)
        new_password = data.get("new_password", None)
        confirm_password = data.get("confirm_password", None)

        if (
            password is not None
            and new_password is not None
            and confirm_password is not None
        ):
            if check_password(password, trainer.password):
                if new_password == confirm_password:
                    trainer.set_password(serializer.validated_data["new_password"])
                    trainer.save()
                else:
                    return Response(
                        status=400,
                        data={
                            "error": "New password and confirm password do not match."
                        },
                    )
            else:
                return Response(
                    status=400, data={"error": "Old password is incorrect."}
                )
        else:
            serializer.save()
        return Response(status=200, data={"success": "Profile updated successfully."})


class OrganizationLearnerIdsAPIView(generics.ListAPIView):
    permission_classes = [IsOrgOwnerOrStaff]
    queryset = User.objects.filter(access_type=User.ORG_LEARNER, active=True)
    filter_backends = [
        django_filters.rest_framework.DjangoFilterBackend,
    ]
    serializer_class = UserSerializer
    filterset_class = UsersFilter
    pagination_class = None

    def get_queryset(self):
        organization_id = self.kwargs["organization_id"]
        queryset = super().get_queryset().filter(organization_id=organization_id)
        return queryset
