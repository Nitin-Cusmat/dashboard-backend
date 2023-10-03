# from django.shortcuts import render

# Create your views here.
import logging
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from django.http import HttpResponse
from rest_framework import generics
from django.db import transaction
from django.contrib.auth import authenticate
import django_filters.rest_framework
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from rest_framework import filters
from rest_framework import serializers
import pytz
import json
from collections import Counter


from rest_framework.generics import (
    ListAPIView,
)
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

from accounts.models import User
from accounts.views import IsOrgOwnerOrStaff, IsAdmin
from django.db.models.functions import TruncMonth, Coalesce
import calendar
from .serializers import (
    ModuleActivityForPerformanceSerializer,
    ModuleAttributesSerializer,
    OrganizationSerilaizer,
    AttemptSerializer,
    LevelSerializer,
    AttemptRetriveSerilaizer,
    AssignedUsersSerializer,
    BasicModuleActivitySerializer,
    LevelActivityReportSerializer,
    LatestAttemptSerializer,
    AttemptNameSerializer,
    AttemptReportSerializer,
    AttemptWiseReportSerializer,
    AttemptWiseReportTableSerializer,
    ApplicationUsageSerializer,
    ListLevelSerializer,
    PerformanceSerializer,
)
from accounts.views import IsOrgOwnerOrStaff, IsAdmin
from .utils import *
from django.db.models import (
    Case,
    When,
    Value,
    Sum,
    Prefetch,
    Count,
    Q,
    BooleanField,
    Subquery,
    OuterRef,
)
from django.shortcuts import get_object_or_404


logger = logging.getLogger(__name__)


class OrgModulesApiView(ListAPIView):
    queryset = ModuleAttributes.objects.all()
    serializer_class = ModuleAttributesSerializer
    filter_backends = [
        django_filters.rest_framework.DjangoFilterBackend,
        filters.SearchFilter,
    ]
    filterset_fields = ["organization_id"]
    search_fields = ["module__name"]
    permission_classes = [IsOrgOwnerOrStaff]


class OrganizationListView(ListAPIView):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerilaizer
    permission_classes = [IsAdmin]


class OrganizationView(generics.RetrieveAPIView):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerilaizer
    lookup_field = "slug"


class ModuleAssignmentView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def post(self, request):
        user_ids = self.request.data.get("user_ids", None)
        module_ids = self.request.data.get("module_ids", None)
        is_assign = self.request.data.get("assign", False)

        users = User.objects.filter(id__in=user_ids)
        modules = ModuleAttributes.objects.filter(id__in=module_ids)
        existing = ModuleActivity.objects.filter(
            user_id__in=user_ids, module_id__in=module_ids, active=True
        )

        if is_assign:
            for module in modules:
                for user in users:
                    if (
                        existing.filter(
                            user_id=user.id, module_id=module.id, active=True
                        ).count()
                        < 1
                    ):
                        ModuleActivity.objects.create(
                            user=user,
                            module=module,
                            assigned_on=datetime.now(),
                            active=True,
                        )

        else:
            for module_activity in existing:
                module_activity.active = False
                module_activity.save()

        return Response(status=201)


class ActiveModulesCountView(generics.GenericAPIView):
    serializer_class = ModuleAttributesSerializer
    permission_classes = [IsOrgOwnerOrStaff]

    def get(self, request):
        count_only = self.request.query_params.get("count_only", False)
        organization_id = self.request.query_params.get("organization_id", None)
        active_modules = ModuleAttributes.objects.filter()
        if organization_id is not None:
            active_modules = active_modules.filter(organization_id=organization_id)

        if count_only:
            data = {"active_modules": len(active_modules)}
        else:
            serializer = self.get_serializer(active_modules, many=True)
            active_modules = serializer.data

            data = {"active_modules": active_modules}

        return Response(status=200, data=data)


class ActiveUsersCountView(generics.GenericAPIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def get(self, request):
        organization_id = self.request.query_params.get("organization_id", None)
        module = self.request.query_params.get("module", None)
        active_users = User.objects.filter(
            active=True, deleted=False, access_type="Learner"
        )
        data = {}
        if organization_id is not None:
            active_users = active_users.filter(organization__id=organization_id)
            data["active_users_count"] = len(active_users)
        if module is not None:
            # filter based on modules
            user_ids = [user.id for user in active_users]
            module_active_user = ModuleActivity.objects.filter(
                module__module__name=module, user__in=user_ids, active=True
            )
            data["module_active_users_count"] = len(module_active_user)

        return Response(status=200, data=data)


class PerformanceView(APIView):
    serializer_class = PerformanceSerializer
    permission_classes = [IsOrgOwnerOrStaff]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization_id = serializer.validated_data["organization_id"]
        module_name = serializer.validated_data.get("module_name", None)
        try:
            organization = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return Response(status=400, data={"error": "Invalid organization"})
        module = None
        if module_name is not None:
            try:
                module = Module.objects.get(name__iexact=module_name)
            except Module.DoesNotExist:
                return Response(
                    status=400,
                    data={"error": "Invalid module name for the given organization"},
                )
        data = PerformanceCalculations.get_module_performance(organization, module)
        return Response(status=200, data=data)


class CompleteModuleView(APIView):
    def get(self, request):
        module_activity = ModuleActivity.objects.get(user="user", module__id="module")
        module_activity.complete_date = datetime.now()
        module_activity.save()
        return Response(status=200)


# api to collect attempt data for a user assigned to a module
class UserAttemptView(APIView):
    def post(self, request):
        data = self.request.data
        user_id = data["userId"]
        org_id = data["orgId"]
        user = None
        try:
            user = User.objects.get(organization_id=org_id, user_id=user_id)
        except ObjectDoesNotExist:
            logger.error(
                f"User with user id {user_id} or organization id {org_id} not found"
            )

        module_name = data["module"]["name"]
        level_name = data["module"]["level"]
        logger.info(
            f"get the module activity object given the module name as {module_name}"
        )
        try:
            main_module = Module.objects.get(name__iexact=module_name)
            module = ModuleAttributes.objects.get(
                module__name__iexact=module_name, organization_id=org_id
            )
        except ObjectDoesNotExist:
            logger.error(f"module {module_name} does not exist")

        module_activity = ModuleActivity.objects.get(
            user=user, module=module, active=True
        )

        # just for now to add through api...remove later
        logger.info(
            f"get the level from level name {level_name} or create level activity if does not exist"
        )
        try:
            category = Category.objects.get(name__iexact=data["module"]["category"])
        except Category.DoesNotExist:
            last_category = Category.objects.order_by("-order").last()
            category_order = last_category.order + 1 if last_category else 1
            category = Category(
                name=data["module"]["category"].capitalize(), order=category_order
            )
            category.save()
        all_levels = Level.objects.filter(module=module_activity.module.module)
        logger.info("all levels fetched for the module")
        try:
            level_obj = all_levels.get(name__iexact=level_name)
            level_obj.category = category
            level_obj.save()
        except Level.DoesNotExist:
            last_level = (
                Level.objects.filter(module=main_module).order_by("level").last()
            )
            level_number = last_level.level + 1 if last_level else 1
            level_obj = Level(
                module=main_module,
                name=level_name.capitalize(),
                level=level_number,
                category=category,
            )
            level_obj.save()
        logger.info(f"level {level_name} fetched")
        level_activity, created = LevelActivity.objects.get_or_create(
            level=level_obj, module_activity=module_activity
        )
        logger.info("level activity fetched")

        logger.info("mark the level as completed")
        score = data.get("score", None)
        if score is not None and module_name.lower() in ["reach truck", "forklift"]:
            score = 0
            free_score_kpi = {
                "Choose to turn off the unit before get out of the MHE": 2
            }
            if (
                "gameData" in data
                and "inspections" in data["gameData"]
                and data["gameData"]["inspections"]
            ):
                score_kpis = data["gameData"]["inspections"][0].get("actualFlow", [])
            else:
                score_kpis = []
            for score_kpi in score_kpis:
                if score_kpi in free_score_kpi:
                    score = score + free_score_kpi[score_kpi]

            fixed_table_kpis = {
                "brake condition": 2,
                "fork condition": 2,
                "alert light condition": 1,
                "camera condition": 1,
                "tilt condition": 2,
                "steer condition": 2,
                "safety belt condition": 1,
                "fire extiguisher condition": 1,
                "rearviews mirror condition": 1,
                "blue light condition": 1,
                "horn condition": 1,
                "main light condition": 2,
            }

            if not data["gameData"]["tableKpis"]:
                score = score + sum(fixed_table_kpis.values())
            else:
                for table_kpi in data["gameData"]["tableKpis"]:
                    if (
                        "preCheckCondition" in table_kpi
                        and table_kpi["preCheckCondition"].strip().lower()
                        in fixed_table_kpis
                        and table_kpi["hasChecked"] == True
                    ):
                        score = (
                            score
                            + fixed_table_kpis[
                                table_kpi["preCheckCondition"].strip().lower()
                            ]
                        )

            fixed_mistakes = {
                "did not complete pre operation check": 2,
                "drove over the speed limit": 3,
                "engagement error": 2,
                "did not lower forks after stacking": 2,
                "did not horn while pedestrian in vicinity": 2,
                "did not horn before starting the engine": 1,
                "did not horn before moving forward": 1,
                "did not horn before moving in reverse": 1,
                "did not press horn when turning into aisles": 1,
                "fork blending occured": 3,
                "did not maintain forkheight above 15 cm": 1,
                "stacking error": 3,
                "did not fix the pallet postion": 2,
                "did not report breakdown during pre ops check": 2,
            }
            if "mistakes" in data["gameData"]:
                score = score + sum(fixed_mistakes.values())
                for mistake in data["gameData"]["mistakes"]:
                    if mistake["name"].strip().lower() in fixed_mistakes:
                        score = score - fixed_mistakes[mistake["name"].strip().lower()]

            if "path" in data["gameData"]:
                ideal_total_time = 0
                for ideal_time in data["gameData"]["path"]["idealTime"]:
                    ideal_total_time = ideal_total_time + ideal_time["timeTaken"]

                actual_total_time = 0
                actual_paths = {}
                for actual_path in data["gameData"]["path"]["vehicleData"]:
                    if actual_path["path"].lower() != "path-1":
                        if actual_path["path"].lower() not in actual_paths:
                            actual_paths[actual_path["path"].lower()] = []
                        actual_paths[actual_path["path"].lower()].append(actual_path)

                for path in actual_paths:
                    first = actual_paths[path][0]["time"]
                    last = actual_paths[path][len(actual_paths[path]) - 1]["time"]
                    actual_total_time = actual_total_time + (last - first)

                diff = actual_total_time - ideal_total_time
                ideal_10 = ideal_total_time * 10 / 100
                if diff > 0 and diff > ideal_10:
                    score = score + 5

            score = score / 50 * 100
            data["score"] = round(score, 2)
            if module_name.lower() == "forklift":
                level_activity.complete = True
                level_activity.save()
        if score is not None and module_name.lower() != "forklift":
            if module.passing_score and float(score) <= float(module.passing_score):
                level_activity.complete = False
            else:
                level_activity.complete = True
            level_activity.save()
        tz = pytz.timezone("Asia/Kolkata")

        logger.info("Create attempt data record")
        last_attempt = (
            Attempt.objects.filter(level_activity=level_activity)
            .order_by("attempt_number")
            .last()
        )
        attempt_number = last_attempt.attempt_number + 1 if last_attempt else 1
        Attempt.objects.create(
            level_activity=level_activity,
            attempt_number=attempt_number,
            data=json.dumps(data, sort_keys=False),
            duration=data["duration"],
            start_time=datetime.fromtimestamp(int(data["startTime"]), tz),
            end_time=datetime.fromtimestamp(int(data["endTime"]), tz),
        )

        all_levels = Level.objects.filter(module=module_activity.module.module)
        logger.info(
            "Get all the training levels before the assessment levels if the attempt is for assessment level"
        )

        assessment_levels = all_levels.filter(category__name__iexact="assessment")
        if assessment_levels.count() > 0:
            completed_assessment_levels = LevelActivity.objects.filter(
                module_activity=module_activity,
                complete=True,
                level__category__name__iexact="assessment",
            )

            if assessment_levels.count() == completed_assessment_levels.count():
                module_activity.complete = True
                module_activity.complete_date = datetime.now()
                module_activity.save()
            else:
                module_activity.complete = False
                module_activity.complete_date = None
                module_activity.save()

        else:
            training_levels = all_levels.filter(~Q(category__name__iexact="assessment"))
            if training_levels.count() > 0:
                completed_training_levels = LevelActivity.objects.filter(
                    ~Q(level__category__name__iexact="assessment"),
                    module_activity=module_activity,
                    complete=True,
                )
                if training_levels.count() == completed_training_levels.count():
                    module_activity.complete = True
                    module_activity.complete_date = datetime.now()
                    module_activity.save()
                else:
                    module_activity.complete = False
                    module_activity.complete_date = None
                    module_activity.save()

        UserActivity.objects.create(
            module=main_module,
            user=user,
            duration=data["duration"],
            start_time=datetime.fromtimestamp(int(data["startTime"]), tz),
            end_time=datetime.fromtimestamp(int(data["endTime"]), tz),
            log_event="module_activity",
        )

        logger.info("Successfully created attempt data")
        return Response(status=201)


# api to get attempt data for comparitive and inidvidual reports
class AttemptDataApiView(generics.GenericAPIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = AttemptRetriveSerilaizer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)

        user_ids = serializer.data.get("user_ids")
        module_name = serializer.data.get("module")
        level_name = serializer.data.get("level")
        attempt_number = serializer.data.get("attempt", None)
        organization_id = serializer.data.get("organization_id")

        result = []
        for id in user_ids:
            try:
                module_activity = ModuleActivity.objects.get(
                    user__user_id=id,
                    user__organization__id=organization_id,
                    active=True,
                    module__module__name=module_name,
                )
                if module_activity:
                    try:
                        if attempt_number:
                            attempt_data = Attempt.objects.get(
                                attempt_number=attempt_number,
                                level_activity__module_activity=module_activity,
                                level_activity__level__name=level_name,
                            )
                        else:
                            attempt_data = Attempt.objects.filter(
                                level_activity__module_activity=module_activity,
                                level_activity__level__name=level_name,
                            ).order_by("-attempt_number")[0]
                        result.append(attempt_data)
                    except ObjectDoesNotExist:
                        raise ValidationError(detail="Attempt Data not found")

            except ObjectDoesNotExist:
                raise ValidationError(detail="Module activity not found")

        ser = AttemptSerializer(result, many=True)
        return Response(ser.data, status=200)


# api to get all the modules, levels for a specific user
class ModuleLevelView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def get(self, request):
        user_id = self.request.query_params.get("user_id", None)
        organization_id = self.request.query_params.get("organization_id", None)
        # get all the modules assigned to the user currently
        if user_id:
            module_activities = (
                ModuleActivity.objects.filter(
                    user__user_id=user_id,
                    user__organization_id=organization_id,
                    active=True,
                )
                .annotate(level_activity_count=Count("levelactivity"))
                .filter(level_activity_count__gt=0)
            )
            ser = BasicModuleActivitySerializer(module_activities, many=True)
        else:
            Response(details="User not found", status=400)
        return Response(ser.data, status=200)


# api to get all the attempts given and level_activity_id
class AttemptsListApiView(ListAPIView):
    queryset = Attempt.objects.all().order_by("attempt_number")
    serializer_class = AttemptNameSerializer
    permission_classes = [IsOrgOwnerOrStaff]
    filter_backends = [
        django_filters.rest_framework.DjangoFilterBackend,
    ]
    filterset_fields = ["level_activity_id"]


# api to get report for a period of time for a user either attempt wise, monthly or weekly
class IndividualUserReportApiView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def post(self, request):
        org_id = self.request.data.get("org_id")
        if self.request.user.organization or org_id:
            org_id = org_id if org_id is not None else user.organization.id

        user_id = self.request.data.get("user_id")
        module_activity_ids = self.request.data.get("module_activity_ids")
        time_period = self.request.data.get("time_period")
        start_date = self.request.data.get("start_date")
        end_date = self.request.data.get("end_date")

        module_activities = ModuleActivity.objects.filter(
            user__user_id=user_id, user__organization_id=org_id
        )
        if module_activity_ids:
            module_activities.filter(id__in=module_activity_ids)
        response = []

        context = self.request.data
        if time_period == "Weekly" or time_period == "Monthly":
            level_data = LevelActivity.objects.filter(
                module_activity__user__user_id=user_id,
                module_activity_id__in=module_activity_ids,
            )
            level_data_ser = LevelActivityReportSerializer(
                level_data, many=True, context=context
            )
            response = level_data_ser.data

        else:
            # for attempt wise data from start time to end time get all the attempts done by the user in that time for given modules
            attempts = Attempt.objects.filter(
                level_activity__module_activity__user__user_id=user_id
            ).filter(level_activity__module_activity_id__in=module_activity_ids)
            # filter by date
            attempts = attempts.filter(
                start_time__gte=start_date, end_time__lte=end_date
            )
            ser = AttemptReportSerializer(attempts, many=True)
            response = ser.data

        # start_time, end_time, Module, level, time_spent, success_rate, start_time, end_time fields to be sent

        return Response(response, status=200)


class LevelUserInfo(APIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def get(self, request):
        level_name = self.request.query_params.get("level_name")
        module_name = self.request.query_params.get("module_name")
        organization_id = self.request.query_params.get("organization_id")

        module = get_object_or_404(Module, name=module_name)
        organization = get_object_or_404(Organization, id=organization_id)
        level = get_object_or_404(Level, name=level_name, module__name=module_name)

        attempts = (
            Attempt.objects.filter(
                level_activity__level=level,
                level_activity__complete=True,
                level_activity__module_activity__user__active=True,
                level_activity__module_activity__user__deleted=False,
                level_activity__module_activity__active=True,
                level_activity__module_activity__user__organization=organization,
                level_activity__module_activity__module__module=module,
            )
            .exclude(duration=None)
            .select_related("level_activity__module_activity__user")
        )
        user_time_spent = {}
        for attempt in attempts:
            user = attempt.level_activity.module_activity.user.get_full_name()
            time_spent = attempt.duration.total_seconds()
            if user not in user_time_spent:
                user_time_spent[user] = 0
            user_time_spent[user] += time_spent

        return Response(status=200, data=user_time_spent)


class LevelActivityApiView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]

    def get(self, request):
        org_id = self.request.query_params.get("org_id")
        if self.request.user.organization or org_id:
            org_id = org_id if org_id is not None else self.request.user.organization.id

        module_name = self.request.query_params.get("module_name")
        try:
            module = Module.objects.get(name=module_name)
        except ObjectDoesNotExist:
            logger.error(f"Module with name {module_name} not found")
            return Response("Module not found", status=404)

        level_activities = (
            LevelActivity.objects.filter(
                module_activity__module__module=module,
                module_activity__user__organization_id=org_id,
                module_activity__active=True,
                module_activity__user__active=True,
                module_activity__user__deleted=False,
                complete=True,
            )
            .values("level__name", "level__category__name")
            .annotate(
                users_completed=Count("module_activity__user", distinct=True),
                total_time=Sum("attempt__duration"),
            )
        )

        sorted_data = []
        if level_activities.count() == 0:
            sorted_data.append({})
        else:
            response = []
            num_module_users = ModuleActivity.objects.filter(
                module__module=module,
                user__organization_id=org_id,
                user__deleted=False,
                user__active=True,
                active=True,
            )
            for level_data in level_activities:
                progress = (
                    level_data["users_completed"] / len(num_module_users) * 100
                    if len(num_module_users)
                    else 0
                )
                if progress.is_integer():
                    progress = int(progress)
                level_obj = {
                    "level_name": level_data["level__name"],
                    "category": level_data["level__category__name"],
                    "total_time": level_data["total_time"] or 0,
                    "users_completed": level_data["users_completed"],
                    "total_count": len(num_module_users),
                    "progress_%": "{}%".format(round(progress, 2)),
                }
                response.append(level_obj)

            sorted_data = sorted(
                response, key=lambda x: float(x["progress_%"][:-1]), reverse=True
            )
        return Response(sorted_data, status=200)


# api to get all users average performance for all the modules assigned
class AssignedUsersApiView(generics.GenericAPIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = AssignedUsersSerializer

    def get_queryset(self):
        LEARNER = "Learner"
        org_id = self.request.query_params.get("org_id", None)
        if org_id is None:
            return User.objects.none()

        module = self.request.query_params.get("modules", None)
        if module is None:
            return Module.objects.none()
        module_names = module.split(",")

        module_activities = ModuleActivity.objects.filter(
            user__organization__id=org_id,
            module__module__name__in=module_names,
            active=True,
            user__deleted=False,
            user__active=True,
        )

        total_non_assessment_count_subquery = (
            Level.objects.filter(
                ~Q(category__name__iexact="assessment"),
                module=OuterRef("module__module"),
            )
            .values("module")
            .annotate(total_non_assessment_count=Coalesce(Count("id"), 0))
            .values("total_non_assessment_count")
        )

        completed_non_assessment_count_subquery = (
            LevelActivity.objects.filter(
                ~Q(level__category__name__iexact="assessment"),
                module_activity=OuterRef("id"),  # Link to ModuleActivity
                complete=True,
            )
            .values("module_activity")
            .annotate(completed_non_assessment_count=Coalesce(Count("id"), 0))
            .values("completed_non_assessment_count")
        )

        total_assessment_count_subquery = (
            Level.objects.filter(
                category__name__iexact="assessment",
                module=OuterRef("module__module"),
            )
            .values("module")
            .annotate(total_non_assessment_count=Coalesce(Count("id"), 0))
            .values("total_non_assessment_count")
        )

        completed_assessment_count_subquery = (
            LevelActivity.objects.filter(
                level__category__name__iexact="assessment",
                module_activity=OuterRef("id"),  # Link to ModuleActivity
                complete=True,
            )
            .values("module_activity")
            .annotate(completed_non_assessment_count=Coalesce(Count("id"), 0))
            .values("completed_non_assessment_count")
        )

        last_attempted_level_subquery = (
            LevelActivity.objects.filter(module_activity=OuterRef("pk"))
            .order_by("-attempt__end_time")
            .values("level__name")[:1]
        )
        last_attempt_date_subquery = (
            Attempt.objects.filter(level_activity__module_activity=OuterRef("pk"))
            .order_by("-end_time")
            .values("end_time")[:1]
        )

        queryset = (
            module_activities.annotate(
                current_level=Subquery(last_attempted_level_subquery),
                level_date=Subquery(last_attempt_date_subquery),
                module_usage=Sum("levelactivity__attempt__duration"),
                total_attempts=Count("levelactivity__attempt"),
                total_non_assessment_count=Subquery(
                    total_non_assessment_count_subquery
                ),
                completed_non_assessment_count=Subquery(
                    completed_non_assessment_count_subquery
                ),
                total_assessment_count=Subquery(total_assessment_count_subquery),
                completed_assessment_count=Subquery(
                    completed_assessment_count_subquery
                ),
            )
            .values(
                "id",
                "module__module__name",
                "user__first_name",
                "user__last_name",
                "user__user_id",
                "current_level",
                "level_date",
                "module_usage",
                "total_attempts",
                "total_non_assessment_count",
                "completed_non_assessment_count",
                "total_assessment_count",
                "completed_assessment_count",
            )
            .order_by(F("level_date").desc(nulls_last=True))
        )

        search_query = self.request.query_params.get("search", None)
        if search_query is not None and len(search_query) > 0:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search_query)
                | Q(user__last_name__icontains=search_query)
                | Q(user__user_id__icontains=search_query)
            )
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = self.paginator
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class LatestAttemptsApiView(ListAPIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = LatestAttemptSerializer

    def get_queryset(self):
        organization_id = self.request.query_params.get("organization_id", None)

        attempts = (
            Attempt.objects.filter(
                level_activity__module_activity__user__organization__id=organization_id
            )
            .select_related(
                "level_activity__level",
                "level_activity__module_activity__user",
                "level_activity__module_activity__module__module",
            )
            .values(
                "level_activity__level__name",
                "level_activity__module_activity__user__user_id",
                "level_activity__module_activity__user__first_name",
                "level_activity__module_activity__user__last_name",
                "level_activity__module_activity__module__module__name",
                "duration",
                "start_time",
                "end_time",
            )
            .order_by("-id")[:15]
        )

        return attempts


class ApplicationUsageApiView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = ApplicationUsageSerializer

    def post(self, request, usecase=0):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization_id = serializer.validated_data["organization_id"]
        organization = Organization.objects.get(id=organization_id)
        data = {}
        user_activity = UserActivity.objects.filter(user__organization=organization_id)

        if usecase == 0:
            data = ApplicationUsage.get_organization_application_usage(
                user_activity, organization
            )
        else:
            data = ApplicationUsage.get_module_application_usage(user_activity)

        return Response(status=200, data=data)


class UserPerformanceView(APIView):
    serializer_class = ModuleActivityForPerformanceSerializer
    permission_classes = [IsOrgOwnerOrStaff]

    def post(self, request, user_id):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization_id = serializer.validated_data["user"]["organization"]["id"]

        current_month = datetime.now().month
        current_year = datetime.now().year

        total_counts = PerformanceCalculations.get_total_counts(
            organization_id, user_id
        )
        completed_modules = total_counts.filter(complete=True)
        try:
            current_month_overall_performace_chart = round(
                completed_modules.count() / total_counts.count() * 100, 2
            )
        except:
            current_month_overall_performace_chart = 0

        completed_modules_till_last_month = completed_modules.filter(
            complete_date__lt=date(current_year, current_month, 1),
        )

        last_month_overall_performance = completed_modules_till_last_month.count()

        overall_monthly_performance_comparison = (
            completed_modules.count() - last_month_overall_performance
        )

        module_wise_total_time_spent_monthly = {}
        overall_total_time_spent = (
            total_counts.annotate(month=TruncMonth("assigned_on"))
            .values("month")
            .annotate(total_duration=Sum("levelactivity__attempt__duration"))
        )
        try:
            total_time_spent = overall_total_time_spent[0]["total_duration"].seconds
        except:
            total_time_spent = 0

        if len(total_counts) > 0:
            smallest_datetime = (
                min(total_counts, key=lambda x: x.assigned_on.date())
                .assigned_on.date()
                .month
            )
        for module in total_counts:
            user_level_activities = (
                module.levelactivity_set.all()
                .annotate(month=TruncMonth("attempt__created_at"))
                .values("month")
                .annotate(total_duration=Sum("attempt__duration"))
                .order_by("month")
            )
            monthly_dict = {
                calendar.month_name[i]: 0
                for i in range(smallest_datetime, datetime.now().month + 1)
            }
            if len(user_level_activities) > 0:
                if user_level_activities[0]["total_duration"].seconds > 0:
                    month_name_str = calendar.month_name[
                        user_level_activities[0]["month"].month
                    ]
                    monthly_dict[month_name_str] = user_level_activities[0][
                        "total_duration"
                    ].seconds
                    module_wise_total_time_spent_monthly[
                        module.module.module.name
                    ] = monthly_dict

        data = {
            "current_month_overall_performace_chart": current_month_overall_performace_chart,
            "current_month_overall_performace": completed_modules.count(),
            "overall_monthly_performance_comparison": overall_monthly_performance_comparison,
            "total_time_spent": total_time_spent,
            "module_wise_total_time_spent_monthly": module_wise_total_time_spent_monthly,
        }

        return Response(status=200, data=data)


class ListLevelsAPIView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = ListLevelSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data["user_ids"]
        organization_id = serializer.validated_data["organization_id"]
        module_name = serializer.validated_data["module_name"]
        levels = Level.objects.filter(module__name=module_name)
        level_names = LevelActivity.objects.filter(
            module_activity__user__user_id__in=user_ids,
            module_activity__user__organization_id=organization_id,
            level__in=levels,
            # complete=True,
        ).values_list("level__name", flat=True)
        level_counts = dict(Counter(level_names))
        new_level_names = [name for name, count in level_counts.items() if count > 1]
        levels = levels.filter(name__in=new_level_names)
        if not levels:
            return Response(
                status=400, data={"error": "No levels found for the given module"}
            )
        serializer = LevelSerializer(levels, many=True)
        return Response(status=200, data=serializer.data)


class AttemptWiseReportTableAPIView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = AttemptWiseReportTableSerializer

    def get_weeks_info_from_dates(start_date_str, end_date_str):
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        week_dates = []
        week_dict = {}

        days_diff = (end_date - start_date).days
        for i in range(0, days_diff + 1, 7):
            week_start = start_date + timedelta(days=i)
            week_end = min(week_start + timedelta(days=6), end_date)
            week_dates.append((week_start, week_end))

        for week_start, week_end in week_dates:
            week_dict[
                f"Week {week_start.isocalendar()[1]}"
            ] = f"{week_start.strftime('%Y/%m/%d')} - {week_end.strftime('%Y/%m/%d')}"
        return week_dict

    def get_months_info_from_dates(start_date_str, end_date_str):
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        dates = {}
        i = 0
        current_date = start_date.replace(day=1)
        while current_date <= end_date:
            next_month = current_date.replace(day=1) + timedelta(days=32)
            last_day = next_month - timedelta(days=next_month.day)
            if last_day > end_date:
                last_day = end_date
            period_str = (
                current_date.strftime("%Y/%m/%d")
                + " - "
                + last_day.strftime("%Y/%m/%d")
            )
            dates[i] = period_str
            current_date = next_month.replace(day=1)
            i = i + 1
        return dates

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        category_filter = serializer.validated_data["category_filter"]
        start_date_str = serializer.validated_data.get("start_date", None)
        end_date_str = serializer.validated_data.get("end_date", None)
        module_names = serializer.validated_data["module_names"]
        user_id = serializer.validated_data["user_id"]
        organization_id = serializer.validated_data["organization_id"]

        data = []

        if category_filter == "weekly":
            results = AttemptWiseReportTableAPIView.get_weeks_info_from_dates(
                start_date_str, end_date_str
            )
        elif category_filter == "monthly":
            results = AttemptWiseReportTableAPIView.get_months_info_from_dates(
                start_date_str, end_date_str
            )
        elif category_filter == "attempt_wise":
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            results = {
                "key": f"{start_date.strftime('%Y/%m/%d')} - {end_date.strftime('%Y/%m/%d')}"
            }

        else:
            return Response(
                status=400,
                data={
                    "error": "Invalid category filter. Possible category filters are  weekly, monthly and attempt_wise"
                },
            )
        user_activities = ModuleActivity.objects.filter(
            module__module__name__in=module_names,
            user__user_id=user_id,
            user__organization__id=organization_id,
            active=True,
        ).prefetch_related(
            Prefetch(
                "levelactivity_set",
                queryset=LevelActivity.objects.select_related("level"),
            ),
            "levelactivity_set__attempt_set",
        )
        for result in results.values():
            table_start_date_str = result.split("-")[0].strip()
            table_end_date_str = result.split("-")[1].strip()
            table_start_date = datetime.strptime(
                table_start_date_str, "%Y/%m/%d"
            ).date()
            table_end_date = datetime.strptime(table_end_date_str, "%Y/%m/%d").date()

            for index, user_activity in enumerate(user_activities):
                level_activities = user_activity.levelactivity_set.all()
                for level_activity in level_activities:
                    attempts = level_activity.attempt_set.filter(
                        end_time__date__gte=table_start_date,
                        end_time__date__lte=table_end_date,
                    ).order_by("-attempt_number", "-level_activity__level")
                    try:
                        if level_activity.complete:
                            success_rate = round(1 / len(attempts) * 100, 2)
                        else:
                            success_rate = 0.0
                    except:
                        success_rate = 0.0
                    if success_rate.is_integer():
                        success_rate = int(success_rate)
                    duration = timedelta(seconds=0)
                    if category_filter != "attempt_wise":
                        mini_data = {}
                        if attempts:
                            for attempt in attempts:
                                duration += attempt.duration
                            mini_data["start_date"] = table_start_date
                            mini_data["end_date"] = table_end_date
                            mini_data["module"] = module_names[index]
                            mini_data["level"] = level_activity.level.name
                            mini_data["time_spent"] = duration
                            mini_data["total_attempts"] = len(attempts)
                            mini_data["success_rate"] = str(success_rate) + "%"
                            data.append(mini_data)
                    else:
                        for attempt in attempts:
                            mini_data = {}
                            duration = attempt.duration
                            mini_data["date"] = attempt.start_time.date()
                            mini_data["module"] = module_names[index]
                            mini_data["level"] = level_activity.level.name
                            mini_data["time_spent"] = duration
                            mini_data["completed"] = level_activity.complete
                            mini_data["start_time"] = attempt.start_time
                            mini_data["end_time"] = attempt.end_time
                            mini_data["attempt_number"] = attempt.attempt_number
                            data.append(mini_data)

        return Response(status=200, data=data)


class AttemptWiseReportAPIView(APIView):
    permission_classes = [IsOrgOwnerOrStaff]
    serializer_class = AttemptWiseReportSerializer

    def get_required_records(filter_type, start_date_str=None, end_date_str=None):
        if filter_type == "last_7_days":
            end_date = date.today()
            start_date = end_date - timedelta(days=7)

        elif filter_type == "last_30_days":
            end_date = date.today()
            start_date = end_date - timedelta(days=30)

        elif filter_type == "this_month":
            start_date = date.today().replace(day=1)
            end_date = date.today().replace(
                day=1, month=start_date.month + 1
            ) - timedelta(days=1)

        elif filter_type == "last_month":
            today = date.today()
            start_date = today.replace(day=1) - timedelta(days=1)
            end_date = start_date.replace(day=1)

        elif filter_type == "last_6_months":
            end_date = date.today()
            start_date = end_date.replace(day=1) - relativedelta(months=5)

        elif filter_type == "this_year":
            start_date = date.today().replace(month=1, day=1)
            end_date = date.today()

        elif filter_type == "custom_range":
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        return start_date, end_date

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        filter_type = serializer.validated_data["filter_type"]
        module_names = serializer.validated_data["module_names"]
        user_id = serializer.validated_data["user_id"]
        organization_id = serializer.validated_data["organization_id"]
        start_date_str = None
        end_date_str = None
        if filter_type == "custom_range":
            start_date_str = serializer.validated_data.get("start_date", None)
            end_date_str = serializer.validated_data.get("end_date", None)
            if start_date_str is None or end_date_str is None:
                return Response(
                    status=400, data={"error": "Please provide start_date and end_date"}
                )
        assigned_modules = ModuleActivity.objects.filter(
            user__user_id=user_id,
            module__module__name__in=module_names,
            user__organization__id=organization_id,
            active=True,
            user__deleted=False,
        )
        start_date, end_date = AttemptWiseReportAPIView.get_required_records(
            filter_type, start_date_str, end_date_str
        )

        total_attempts = 0
        total_time_spent = 0
        mistakes_content = []
        all_completed_levels = 0
        for index, assigned_module in enumerate(assigned_modules):
            total_levels = assigned_module.levelactivity_set.all()
            module_name = module_names[index]
            for total_level in total_levels:
                attempts = total_level.attempt_set.filter(
                    end_time__date__gte=start_date,
                    end_time__date__lte=end_date,
                )
                total_attempts += len(attempts)
                for attempt in attempts:
                    total_time_spent += attempt.duration.seconds
                    all_completed_levels += 1 if attempt.level_activity.complete else 0
                    try:
                        attempt = json.loads(attempt.data)
                    except:
                        attempt = attempt.data
                    if "gameData" in attempt:
                        if "mistakes" in attempt["gameData"]:
                            for mistake in attempt["gameData"]["mistakes"]:
                                name = mistake["name"]
                                existing_mistake = next(
                                    (
                                        item
                                        for item in mistakes_content
                                        if item["name"] == name
                                    ),
                                    None,
                                )
                                if existing_mistake:
                                    existing_mistake["count"] += mistake["count"]
                                    if (
                                        module_name
                                        not in existing_mistake["module_names"]
                                    ):
                                        existing_mistake["module_names"].append(
                                            module_name
                                        )
                                else:
                                    mistakes_content.append(
                                        {
                                            "name": name,
                                            "count": mistake["count"],
                                            "module_names": [module_name],
                                        }
                                    )

        data = {
            "success_rate": sum(1 for module in assigned_modules if module.complete)
            / len(assigned_modules)
            * 100,
            "completed_levels": all_completed_levels,
            "assigned_modules": len(assigned_modules),
            "total_attempts": total_attempts,
            "total_time_spent": PerformanceCalculations.convert_seconds_to_hms(
                total_time_spent
            ),
            "mistakes_content": mistakes_content,
            "mistakes_count": sum([item["count"] for item in mistakes_content]),
        }

        return Response(status=200, data=data)


class ApplicationUsageAnalyticsAPIView(APIView):
    permission_classes = [IsAdmin]

    def get_merge_data(self, data1, data2, data3):
        data1_dict = {item["name"]: item for item in data1}
        data2_dict = {item["name"]: item for item in data2}
        data3_dict = {item["name"]: item for item in data3}

        merged_data = [
            {
                **data1_dict.get(name, {}),
                **data2_dict.get(name, {}),
                **data3_dict.get(name, {}),
            }
            for name in set(data1_dict.keys())
            | set(data2_dict.keys())
            | set(data3_dict.keys())
        ]

        sorted_organization_info = sorted(
            merged_data, key=lambda x: x["total_duration"], reverse=True
        )

        return sorted_organization_info

    def get(self, request, usecase=0):
        if not bool(usecase):
            organizations = Organization.objects.exclude(
                Q(name__iexact="cusmat") | Q(name__isnull=True)
            )
            total_users = organizations.annotate(
                total_users=Count(
                    Case(
                        When(
                            user__deleted=False,
                            user__active=True,
                            then=Value(1),
                        ),
                        default=None,
                        output_field=BooleanField(),
                    ),
                )
            ).values("name", "slug", "total_users")

            total_modules = organizations.annotate(
                total_modules=Count("module_organization", distinct=True)
            ).values("name", "total_modules")

            time_spent = organizations.annotate(
                total_duration=Coalesce(
                    Sum(
                        "user__useractivity__duration",
                    ),
                    timedelta(),
                )
            ).values("name", "total_duration")

            sorted_organization_info = self.get_merge_data(
                total_users, total_modules, time_spent
            )

            return Response(status=200, data=sorted_organization_info)
        else:
            modules = Module.objects.all()
            total_users = modules.annotate(
                total_users=Count(
                    Case(
                        When(
                            module__model_attributes__user__deleted=False,
                            module__model_attributes__user__active=True,
                            module__model_attributes__active=True,
                            then=Value(1),
                        ),
                        default=None,
                        output_field=BooleanField(),
                    )
                )
            ).values("name", "total_users")

            total_organizations = (
                modules.annotate(
                    organization_count=Count("module__organization", distinct=True)
                )
                .annotate(user_count=Count("module__model_attributes", distinct=True))
                .values("name", "organization_count", "user_count")
            )

            time_spent = modules.annotate(
                total_duration=Coalesce(Sum("useractivity__duration"), timedelta()),
            ).values("name", "total_duration")

            sorted_module_info = self.get_merge_data(
                total_users, total_organizations, time_spent
            )

            return Response(status=200, data=sorted_module_info)


class TotalActiveModuleAndUsersAPIView(APIView):
    permission_classes = [IsAdmin]

    def calculate_rate_of_change(queryset):
        today = datetime.now().date()
        current_month_start = today.replace(day=1)
        previous_month_end = current_month_start - timedelta(days=1)

        total_count = queryset.count()
        count_since_previous_month = queryset.filter(
            created_at__lte=previous_month_end
        ).count()

        rate_of_change = total_count - count_since_previous_month

        return total_count, rate_of_change

    def get(self, request):
        (
            total_modules,
            modules_rate_of_change,
        ) = TotalActiveModuleAndUsersAPIView.calculate_rate_of_change(
            queryset=Module.objects.all()
        )

        (
            total_users,
            users_rate_of_change,
        ) = TotalActiveModuleAndUsersAPIView.calculate_rate_of_change(
            queryset=User.objects.exclude(
                Q(organization__name="cusmat") | Q(organization__isnull=True)
            )
        )

        (
            total_organizations,
            organizations_rate_of_change,
        ) = TotalActiveModuleAndUsersAPIView.calculate_rate_of_change(
            queryset=Organization.objects.exclude(name="cusmat")
        )

        today = datetime.now()
        current_month_start = today.replace(day=1)
        previous_month_end = current_month_start - timedelta(days=1)

        total_duration = UserActivity.objects.exclude(
            Q(user__organization__name__iexact="cusmat")
            | Q(user__organization__isnull=True)
        ).aggregate(total_duration=Sum("duration"))["total_duration"]

        if total_duration is None:
            total_duration = timedelta()

        last_month_duration = UserActivity.objects.filter(
            created_at__lte=previous_month_end,
        ).aggregate(last_month_duration=Sum("duration"))["last_month_duration"]

        if last_month_duration is None:
            last_month_duration = timedelta()

        total_duration_rate_of_change = total_duration - last_month_duration

        total_duration_result = PerformanceCalculations.convert_seconds_to_hms(
            total_duration.total_seconds()
        )
        total_duration_rate_of_change_result = (
            PerformanceCalculations.convert_seconds_to_hms(
                total_duration_rate_of_change.total_seconds()
            )
        )
        if total_duration_rate_of_change > timedelta():
            total_duration_rate_of_change_result = (
                "+" + total_duration_rate_of_change_result
            )
        else:
            total_duration_rate_of_change_result = (
                "-" + total_duration_rate_of_change_result
            )

        response_data = [
            {
                "users_count": total_users,
                "users_rate_of_change": users_rate_of_change,
                "modules_count": total_modules,
                "modules_rate_of_change": modules_rate_of_change,
                "organizations_count": total_organizations,
                "organizations_rate_of_change": organizations_rate_of_change,
                "total_usage": total_duration_result,
                "total_duration_rate_of_change": total_duration_rate_of_change_result,
            }
        ]

        return Response(status=200, data=response_data)


class AdminOrganizationApplicationUsageAPIView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        user_activity = UserActivity.objects.all().exclude(
            Q(user__organization__name__iexact="cusmat")
            | Q(user__organization__isnull=True)
        )
        data = ApplicationUsage.get_organization_application_usage(user_activity)
        return Response(status=200, data=data)
