from datetime import datetime, timedelta
import calendar
from django.db.models import Count, F, Case, When, Value, IntegerField, Sum, Q
from django.db.models.functions import TruncMonth
from organizations.models import *
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.db.models.functions import Extract
import math
from collections import defaultdict


class PerformanceCalculations:
    def get_quarter_dates(quarter_num):
        if quarter_num < 1 or quarter_num > 4:
            quarter_num = 1
        current_year = datetime.now().year
        quarter_start_month = 3 * (quarter_num - 1) + 1
        quarter_start = datetime(current_year, quarter_start_month, 1)
        next_quarter_start = (
            datetime(current_year, quarter_start_month + 3, 1)
            if quarter_num < 4
            else datetime(current_year + 1, 1, 1)
        )
        quarter_end = next_quarter_start - timedelta(days=1)
        return quarter_start.date(), quarter_end.date()

    def get_total_counts(organization_id, user_id=None):
        total_counts = ModuleActivity.objects.filter(
            user__organization__id=organization_id,
            user__user_id=user_id if user_id is not None else F("user__user_id"),
            active=True,
            user__deleted=False,
        )
        return total_counts

    def convert_seconds_to_hms(seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return "{:02d}:{:02d}:{:02d}".format(int(hours), int(minutes), int(seconds))

    def get_previous_month(current_month, current_year):
        if current_month == 1:
            last_month = 12
            last_month_year = current_year - 1
        else:
            last_month = current_month - 1
            last_month_year = current_year

        return last_month, last_month_year

    def get_module_performance(organization, module=None):
        current_month = datetime.now().month
        current_year = datetime.now().year
        last_month, last_month_year = PerformanceCalculations.get_previous_month(
            current_month, current_year
        )
        module_attribute_query = Q(organization=organization)
        module_activity_query = Q(
            user__organization=organization,
            user__deleted=False,
            user__active=True,
            active=True,
        )
        if module:
            module_attribute_query &= Q(module=module)
            module_activity_query &= Q(module__module=module)
        module_attribute = ModuleAttributes.objects.filter(
            module_attribute_query
        ).select_related("module")
        current_month_completion_rate = (
            PerformanceCalculations.calculate_completion_rate(
                current_month=current_month,
                current_year=current_year,
                module_activity_query=module_activity_query,
            )
        )

        previous_month_completion_rate = (
            PerformanceCalculations.calculate_completion_rate(
                current_month=last_month,
                current_year=last_month_year,
                module_activity_query=module_activity_query,
            )
        )

        module_completion_rate_chart = round(
            (
                current_month_completion_rate["completed_users"]
                / current_month_completion_rate["total_users"]
            )
            * 100,
            2,
        )
        if int(module_completion_rate_chart) == module_completion_rate_chart:
            module_completion_rate_chart = int(module_completion_rate_chart)

        current_month_performance_trends = (
            PerformanceCalculations.calculate_performance_trends(
                module_attribute,
                current_month=current_month,
                current_year=current_year,
            )
        )
        previous_month_performance_trends = (
            PerformanceCalculations.calculate_performance_trends(
                module_attribute,
                current_month=last_month,
                current_year=last_month_year,
            )
        )

        data = {
            "current_month_performance_trends": current_month_performance_trends,
            "performance_comparison": current_month_performance_trends
            - previous_month_performance_trends,
        }
        if module:
            data["module_completion_rate"] = current_month_completion_rate[
                "completed_users"
            ]
            data["module_completion_rate_comparison"] = current_month_completion_rate[
                "completed_users"
            ]
            -previous_month_completion_rate["completed_users"],
            data["module_completion_rate_chart"] = module_completion_rate_chart
            data[
                "quarter_trends"
            ] = PerformanceCalculations.calculate_quarterly_performance(
                module_attribute, current_month=current_month
            )
        else:
            data["completion_rate"] = current_month_completion_rate["completed_users"]
            data["completion_rate_comparison"] = current_month_completion_rate[
                "completed_users"
            ]
            - previous_month_completion_rate["completed_users"]
            data["completion_rate_chart"] = module_completion_rate_chart
            completion_rates = (
                ModuleActivity.objects.filter(
                    user__active=True,
                    user__deleted=False,
                    active=True,
                    user__organization=organization,
                )
                .annotate(month=TruncMonth("assigned_on"))
                .values("month", "module__module__name")
                .annotate(
                    completed_count=Count("id", filter=F("complete")),
                    assigned_count=Count("id"),
                )
                .order_by("month")
            )
            result = defaultdict(dict)
            for item in completion_rates:
                month_number = item['month'].month
                month_name = calendar.month_name[month_number]
                module_name = item['module__module__name']
                completed_count = item['completed_count']
                assigned_count = item['assigned_count']
        
                completion_rate = round(completed_count / assigned_count * 100, 2) if assigned_count > 0 else 0
                if int(completion_rate) == completion_rate:
                    completion_rate = int(completion_rate)
                result[module_name][month_name] = completion_rate
            data["monthly_counts"] = result


        return data

    def calculate_performance_trends(module_attribute, current_month, current_year):
        last_month, last_month_year = PerformanceCalculations.get_previous_month(
            current_month, current_year
        )

        data = (
            module_attribute.annotate(
                current_month_assigned=Sum(
                    Case(
                        When(
                            model_attributes__assigned_on__month=current_month,
                            model_attributes__assigned_on__year=current_year,
                            model_attributes__user__deleted=False,
                            model_attributes__user__active=True,
                            model_attributes__active=True,
                            then=1,
                        ),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                current_month_complete=Sum(
                    Case(
                        When(
                            model_attributes__complete_date__month=current_month,
                            model_attributes__complete_date__year=current_year,
                            model_attributes__complete=True,
                            model_attributes__user__deleted=False,
                            model_attributes__user__active=True,
                            model_attributes__active=True,
                            then=1,
                        ),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                last_month_assigned=Sum(
                    Case(
                        When(
                            model_attributes__assigned_on__month=last_month,
                            model_attributes__assigned_on__year=last_month_year,
                            model_attributes__user__deleted=False,
                            model_attributes__user__active=True,
                            model_attributes__active=True,
                            then=1,
                        ),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                last_month_complete=Sum(
                    Case(
                        When(
                            model_attributes__complete_date__month=last_month,
                            model_attributes__complete_date__year=last_month_year,
                            model_attributes__complete=True,
                            model_attributes__user__deleted=False,
                            model_attributes__user__active=True,
                            model_attributes__active=True,
                            then=1,
                        ),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
            )
        ).values(
            "current_month_assigned",
            "current_month_complete",
            "last_month_assigned",
            "last_month_complete",
        )

        monthly_trends = {}

        for item in data:
            for key, value in item.items():
                if key not in monthly_trends:
                    monthly_trends[key] = value
                else:
                    monthly_trends[key] += value

        # Calculate pending users
        pending_users = (
            monthly_trends["current_month_assigned"]
            + monthly_trends["last_month_assigned"]
            - monthly_trends["last_month_complete"]
        )

        # Calculate performance trends
        performance_trends = (
            round((monthly_trends["current_month_complete"] / pending_users) * 100, 2)
            if pending_users != 0
            else 0
        )

        if int(performance_trends) == performance_trends:
            performance_trends = int(performance_trends)

        return performance_trends

    def calculate_quarterly_performance(module_attribute, current_month):
        all_quarters_performance = {}
        quarters_month_mapping = [
            "JAN - MAR",
            "APR - JUNE",
            "JULY - SEPT",
            "OCT - DEC",
        ]
        for index, quarter_num in enumerate(
            range(1, math.ceil(float(current_month) / 3) + 1)
        ):
            (
                quarter_start_date,
                quarter_end_date,
            ) = PerformanceCalculations.get_quarter_dates(quarter_num)

            (
                last_quarter_start_date,
                last_quarter_end_date,
            ) = PerformanceCalculations.get_quarter_dates(quarter_num - 1)

            quarterly_trends = (
                module_attribute.annotate(
                    current_quarter_assigned=Sum(
                        Case(
                            When(
                                model_attributes__assigned_on__gte=quarter_start_date,
                                model_attributes__assigned_on__lte=quarter_end_date,
                                model_attributes__user__deleted=False,
                                model_attributes__user__active=True,
                                model_attributes__active=True,
                                then=1,
                            ),
                            default=Value(0),
                            output_field=IntegerField(),
                        )
                    ),
                    current_quarter_complete=Sum(
                        Case(
                            When(
                                model_attributes__complete_date__gte=quarter_start_date,
                                model_attributes__complete_date__lte=quarter_end_date,
                                model_attributes__user__deleted=False,
                                model_attributes__user__active=True,
                                model_attributes__active=True,
                                model_attributes__complete=True,
                                then=1,
                            ),
                            default=Value(0),
                            output_field=IntegerField(),
                        )
                    ),
                    previous_quarter_assigned=Sum(
                        Case(
                            When(
                                model_attributes__assigned_on__gte=last_quarter_start_date,
                                model_attributes__assigned_on__lte=last_quarter_end_date,
                                model_attributes__user__deleted=False,
                                model_attributes__user__active=True,
                                model_attributes__active=True,
                                then=1,
                            ),
                            default=Value(0),
                            output_field=IntegerField(),
                        )
                    ),
                    previous_quarter_complete=Sum(
                        Case(
                            When(
                                model_attributes__complete_date__gte=last_quarter_start_date,
                                model_attributes__complete_date__lte=last_quarter_end_date,
                                model_attributes__complete=True,
                                model_attributes__user__deleted=False,
                                model_attributes__user__active=True,
                                model_attributes__active=True,
                                then=1,
                            ),
                            default=Value(0),
                            output_field=IntegerField(),
                        )
                    ),
                )
            ).values(
                "current_quarter_complete",
                "current_quarter_assigned",
                "previous_quarter_assigned",
                "previous_quarter_complete",
            )[
                0
            ]

            # Calculate pending users
            pending_users = (
                quarterly_trends["current_quarter_assigned"]
                + quarterly_trends["previous_quarter_assigned"]
                - quarterly_trends["previous_quarter_complete"]
            )

            # Calculate quarterly trends
            quarterly_trends = (
                round(
                    (quarterly_trends["current_quarter_complete"] / pending_users)
                    * 100,
                    2,
                )
                if pending_users != 0
                else 0
            )

            if int(quarterly_trends) == quarterly_trends:
                quarterly_trends = int(quarterly_trends)
            all_quarters_performance[quarters_month_mapping[index]] = quarterly_trends

        return all_quarters_performance

    def calculate_completion_rate(current_month, current_year, module_activity_query):
        completion_rate = ModuleActivity.objects.filter(
            module_activity_query
        ).aggregate(
            total_users=Count("user"),
            completed_users=Sum(
                Case(
                    When(
                        complete=True,
                        complete_date__month__lte=current_month,
                        complete_date__year=current_year,
                        then=1,
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
        )

        return completion_rate


class ApplicationUsage:
    def get_module_application_usage(user_activity):
        data = {}
        intervals = {
            "all": None,
            "1m": relativedelta(months=1),
            "6m": relativedelta(months=6),
            "1y": relativedelta(years=1),
        }
        duration_by_module = user_activity.values("module__name").annotate(
            total_duration=Sum("duration")
        )

        for interval, delta in intervals.items():
            if delta:
                end_time = datetime.now() - delta
                duration = (
                    user_activity.filter(end_time__gte=end_time)
                    .values("module__name")
                    .annotate(total_duration=Sum("duration"))
                )
            else:
                duration = duration_by_module

            module_data = []
            for module in duration:
                module_data.append(
                    {
                        module["module__name"]: module[
                            "total_duration"
                        ].total_seconds(),
                    }
                )

            data[interval] = module_data

        return data

    def get_organization_application_usage(user_activity, organization=None):
        if organization:
            current_year = datetime.now().year
            monthly = (
                user_activity.filter(end_time__year=current_year)
                .annotate(month=Extract("end_time", "month"))
                .values("month")
                .annotate(total_duration=Sum("duration"))
            ).order_by("month")
            monthly_dict = {
                calendar.month_name[i]: 0.0
                for i in range(organization.created_at.month, datetime.now().month + 1)
            }
            for month in monthly:
                month_name_str = calendar.month_name[month["month"]]
                if month_name_str in monthly_dict:
                    monthly_dict[month_name_str] = month[
                        "total_duration"
                    ].total_seconds()

            quarter_dict = {}
            quarterly = (
                user_activity.filter(end_time__year=current_year)
                .annotate(quarter=Extract("end_time", "quarter"))
                .values("quarter")
                .annotate(total_duration=Sum("duration"))
            ).order_by("quarter")

            if organization.created_at.month <= 3:
                current_quarter = 1
            elif organization.created_at.month <= 6:
                current_quarter = 2
            elif organization.created_at.month <= 9:
                current_quarter = 3
            else:
                current_quarter = 4

            quarters_month_mapping = [
                "JAN - MAR",
                "APR - JUNE",
                "JULY - SEPT",
                "OCT - DEC",
            ]

            for i in range(current_quarter, 5):
                if i <= (datetime.now().month - 1) // 3 + 1:
                    quarter_dict.update(
                        {"{}".format(quarters_month_mapping[i - 1]): 0.0}
                    )

            for entry in quarterly:
                quarter = entry["quarter"]
                total_duration = entry["total_duration"] or 0
                if quarters_month_mapping[quarter - 1] in quarter_dict:
                    quarter_dict[
                        quarters_month_mapping[quarter - 1]
                    ] = total_duration.total_seconds()

            yearly = (
                user_activity.filter(end_time__month__gte=organization.created_at.month)
                .annotate(year=Extract("end_time", "year"))
                .values("year")
                .annotate(total_duration=Sum("duration"))
            ).order_by("year")

            year_dict = {}
            for year in yearly:
                year_dict[year["year"]] = year["total_duration"].total_seconds()

            data = {
                "monthly": monthly_dict,
                "quaterly": quarter_dict,
                "yearly": year_dict,
            }
        else:
            monthly_total_time_by_organization = (
                user_activity.annotate(month=Extract("end_time", "month"))
                .values("month")
                .annotate(total_duration=Sum("duration"))
            ).order_by("month")
            quarterly_total_time_by_organization = (
                user_activity.annotate(quarter=Extract("end_time", "quarter"))
                .values("quarter")
                .annotate(total_duration=Sum("duration"))
            ).order_by("quarter")
            yearly_total_time_by_organization = (
                user_activity.annotate(year=Extract("end_time", "year"))
                .values("year")
                .annotate(total_duration=Sum("duration"))
            ).order_by("year")

            monthly_dict = {
                calendar.month_name[i]: 0.0 for i in range(1, datetime.now().month + 1)
            }
            for month in monthly_total_time_by_organization:
                month_name_str = calendar.month_name[month["month"]]
                monthly_dict[month_name_str] = month["total_duration"].total_seconds()

            quarter_dict = {}
            quarters_month_mapping = [
                "JAN - MAR",
                "APR - JUNE",
                "JULY - SEPT",
                "OCT - DEC",
            ]

            for i in range(1, 5):
                quarter_dict.update({"{}".format(quarters_month_mapping[i - 1]): 0.0})

            quarter_list = list(quarter_dict)
            for index, quarter in enumerate(quarterly_total_time_by_organization):
                quarter_dict[quarter_list[index]] = quarter[
                    "total_duration"
                ].total_seconds()

            year_dict = {}
            for year in yearly_total_time_by_organization:
                year_dict[year["year"]] = year["total_duration"].total_seconds()

            data = {
                "monthly": monthly_dict,
                "quaterly": quarter_dict,
                "yearly": year_dict,
            }
        return data
