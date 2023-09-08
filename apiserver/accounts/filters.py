from .models import User

from django_filters.rest_framework import (
    CharFilter,
    FilterSet,
)


class UsersFilter(FilterSet):
    last_name = CharFilter(field_name="last_name", lookup_expr="icontains")
    first_name = CharFilter(field_name="first_name", lookup_expr="icontains")
    user_id = CharFilter(field_name="user_id", lookup_expr="icontains")
    designation = CharFilter(field_name="designation", lookup_expr="icontains")
    department = CharFilter(field_name="department", lookup_expr="icontains")
    work_location = CharFilter(field_name="work_location", lookup_expr="icontains")
    date_of_birth = CharFilter(field_name="date_of_birth", lookup_expr="icontains")
    gender = CharFilter(field_name="gender", lookup_expr="icontains")
    course = CharFilter(field_name="course", lookup_expr="icontains")
    batch = CharFilter(field_name="batch", lookup_expr="icontains")
    roll_no = CharFilter(field_name="roll_no", lookup_expr="icontains")
    institute = CharFilter(field_name="institute", lookup_expr="icontains")
    city = CharFilter(field_name="city", lookup_expr="icontains")
    state = CharFilter(field_name="state", lookup_expr="icontains")
    vr_lab = CharFilter(field_name="vr_lab", lookup_expr="icontains")

    class Meta:
        model = User
        fields = [
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
