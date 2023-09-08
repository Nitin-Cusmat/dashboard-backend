from datetime import datetime, date, timedelta
import calendar
from django.db.models import F
from organizations.models import *
from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.db.models.functions import Extract


class PerformanceCalculations:
    def performance_trends_monthly(total_counts, current_month, current_year):
        completed_this_month = total_counts.filter(
            complete=True,
            complete_date__month=current_month,
            complete_date__year=current_year,
        )
        completed_till_last_month = total_counts.filter(
            complete=True,
            complete_date__lt=date(current_year, current_month, 1),
        )
        pending_count_current_month = (
            total_counts.count() - completed_till_last_month.count()
        )
        overall_monthly_performance = (
            completed_this_month.count() / pending_count_current_month
            if pending_count_current_month > 0
            else 0
        )
        return overall_monthly_performance

    def performance_trends_across_usecases(total_counts, current_month, current_year):
        counts_by_month = {}
        for module in total_counts.distinct("module"):
            month_dict = {
                calendar.month_name[i]: 0.0 for i in range(1, datetime.now().month + 1)
            }
            module_name = str(module.module)
            module_users_count = total_counts.filter(module__id=module.module_id)
            completed_modules_user_count = module_users_count.filter(complete=True)
            if module_name not in counts_by_month:
                counts_by_month[module_name] = month_dict
            for module_user_count in completed_modules_user_count:
                month_name = module_user_count.complete_date.strftime("%B")
                month_number = module_user_count.complete_date.month
                for i in range(month_number, current_month + 1):
                    month_name = calendar.month_name[i]
                    completed_till_now = module_users_count.filter(
                        complete=True,
                        complete_date__date__month__lte=current_month,
                        complete_date__year=current_year,
                    )
                    overall_monthly_performance = (
                        completed_till_now.count() / module_users_count.count()
                    )
                    counts_by_month[module_name][month_name] = round(
                        overall_monthly_performance * 100, 2
                    )

        return counts_by_month

    def calculate_module_wise_completion_rate(total_counts, current_month):
        module_wise_completion_rate = {}
        module_wise_completion_rate_comparision = {}
        for module in total_counts.distinct("module"):
            module_name = str(module.module)
            module_wise_count = total_counts.filter(module__id=module.module.id)
            module_wise_pass_count = module_wise_count.filter(complete=True)
            module_wise_last_month_pass_count = module_wise_pass_count.exclude(
                complete_date__month=current_month
            )
            module_wise_last_month_assigned_count = module_wise_pass_count.exclude(
                assigned_on__month=current_month
            )

            try:
                module_wise_successful_completion_rate = (
                    module_wise_pass_count.count() / module_wise_count.count()
                ) * 100
            except:
                module_wise_successful_completion_rate = module_wise_completion_rate[
                    module_name
                ]
            module_wise_completion_rate[module_name] = round(
                module_wise_successful_completion_rate, 2
            )

            try:
                module_wise_completion_rate_comparision[module_name] = round(
                    module_wise_completion_rate[module_name]
                    - (
                        module_wise_last_month_pass_count.count()
                        / module_wise_last_month_assigned_count.count()
                    )
                    * 100,
                    2,
                )
            except:
                module_wise_completion_rate_comparision[
                    module_name
                ] = module_wise_completion_rate[module_name]
        return [module_wise_completion_rate, module_wise_completion_rate_comparision]

    def calculate_module_wise_monthly_performance(
        total_counts, current_month, current_year
    ):
        module_wise_monthly_performance = {}
        for module in total_counts.distinct("module"):
            module_name = str(module.module)
            module_wise_count = total_counts.filter(module__id=module.module.id)
            completed_this_month = module_wise_count.filter(
                complete=True,
                complete_date__month=current_month,
                complete_date__year=current_year,
            )
            completed_till_last_month = module_wise_count.filter(
                complete=True, complete_date__lt=date(current_year, current_month, 1)
            )
            pending_count_current_month = (
                module_wise_count.count() - completed_till_last_month.count()
            )
            overall_monthly_performance = (
                completed_this_month.count() / pending_count_current_month
                if pending_count_current_month > 0
                else 0
            )
            module_wise_monthly_performance[module_name] = (
                overall_monthly_performance * 100
            )
        return module_wise_monthly_performance

    def get_quarter_dates(quarter_num):
        if quarter_num < 1 or quarter_num > 4:
            quarter_num = 1
        current_year = datetime.now().year
        quarter_start_month = (quarter_num - 1) * 3 + 1
        quarter_start = datetime(current_year, quarter_start_month, 1)
        quarter_end = quarter_start + timedelta(days=89)
        return quarter_start.date(), quarter_end.date()

    def module_wise_quarter_performance(total_counts, current_month, current_year):
        module_wise_quarter_performance = {}
        if current_month <= 3:
            current_quarter = 1
        elif current_month <= 6:
            current_quarter = 2
        elif current_month <= 9:
            current_quarter = 3
        else:
            current_quarter = 4

        quarters_month_mapping = [
            "JAN - MAR",
            "APR - JUNE",
            "JULY - SEPT",
            "OCT - DEC",
        ]

        quarter_dict = {}
        for i in range(1, current_quarter + 1):
            quarter_dict.update({"{}".format(quarters_month_mapping[i - 1]): 0.0})

        for module in total_counts.distinct("module"):
            module_name = str(module.module)
            module_wise_count = total_counts.filter(module__id=module.module.id)
            (
                quarter_start_date,
                quarter_end_date,
            ) = PerformanceCalculations.get_quarter_dates(current_quarter)
            module_wise_total_count_of_current_quarter = module_wise_count.filter(
                complete=True,
                complete_date__year=current_year,
                complete_date__gte=quarter_start_date,
                complete_date__lte=quarter_end_date,
            )
            (
                previous_quarter_start_date,
                previous_quarter_end_date,
            ) = PerformanceCalculations.get_quarter_dates(current_quarter - 1)
            module_wise_total_count_of_last_quarter = total_counts.filter(
                complete=True,
                complete_date__year=current_year,
                complete_date__gte=previous_quarter_start_date,
                complete_date__lte=previous_quarter_end_date,
            )
            pending_count_current_quarter = (
                module_wise_count.count()
                - module_wise_total_count_of_last_quarter.count()
            )
            overall_quarterly_performance = (
                module_wise_total_count_of_current_quarter.count()
                / pending_count_current_quarter
                if pending_count_current_quarter > 0
                else 0
            )
            if module_name not in module_wise_quarter_performance:
                module_wise_quarter_performance[module_name] = []
                # quarter_name = f"Q{current_quarter}"
                quarter_list = list(quarter_dict)
                quarter_dict_copy = quarter_dict.copy()
                quarter_dict_copy[quarter_list[current_quarter - 1]] = (
                    round(overall_quarterly_performance, 2) * 100
                )
                module_wise_quarter_performance[module_name].append(quarter_dict_copy)
        return module_wise_quarter_performance

    def get_total_counts(organization_id, user_id=None):
        total_counts = ModuleActivity.objects.filter(
            user__organization__id=organization_id,
            user__user_id=user_id if user_id is not None else F("user__user_id"),
            active=True,
            user__deleted=False,
        )
        return total_counts

    def calculate_performance_trends_weekly(total_counts, current_year, module):
        start_of_current_week = datetime.now() - timedelta(
            days=datetime.now().weekday()
        )
        end_of_current_week = start_of_current_week + timedelta(days=6)
        end_of_last_week = start_of_current_week - timedelta(days=1)

        completed_this_week = total_counts.filter(
            complete=True,
            complete_date__lt=end_of_current_week,
            complete_date__gte=start_of_current_week,
            complete_date__year=current_year,
            module=module,
        )

        completed_till_last_week = total_counts.filter(
            complete=True,
            complete_date__lt=end_of_last_week,
            module=module,
        )
        pending_count_current_week = (
            total_counts.count() - completed_till_last_week.count()
        )
        overall_monthly_performance = (
            completed_this_week.count() / pending_count_current_week
            if pending_count_current_week > 0
            else 0
        )
        return overall_monthly_performance

    def convert_seconds_to_hms(seconds):
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return "{:02d}:{:02d}:{:02d}".format(int(hours), int(minutes), int(seconds))

    def module_overall_performance(total_counts):
        module_wise_overall_performance = {}
        for module in total_counts.distinct("module"):
            module_name = str(module.module)
            total_module_activities = ModuleActivity.objects.filter(
                module__module__name=module_name
            )
            completed_module_activities = total_module_activities.filter(complete=True)
            overall_performance = (
                completed_module_activities.count()
                / total_module_activities.count()
                * 100
            )
            module_wise_overall_performance[module_name] = round(overall_performance, 2)
        return module_wise_overall_performance

    def get_completion_rate(
        organization,
        module_attributes,
        month,
        year,
        is_trends=False,
        is_monthly=False,
        is_quarter=False,
        current_quarter=None,
    ):
        completion_rates = {}

        for module_attribute in module_attributes:
            module = module_attribute.module.name
            if is_trends:
                total_module_activities = ModuleActivity.objects.filter(
                    module__module__name=module,
                    module__organization=organization,
                    user__deleted=False,
                    user__active=True,
                    active=True,
                )
                total_pending_assignments_current_month = (
                    total_module_activities.filter(
                        assigned_on__date__month__lte=month,
                        assigned_on__date__year=year,
                    )
                )
                module_completed_this_month = total_module_activities.filter(
                    complete_date__month=month, complete_date__year=year, complete=True
                )

                try:
                    completion_rate = (
                        module_completed_this_month.count()
                        / total_module_activities.count()
                    ) * 100
                except:
                    completion_rate = 0
            elif is_quarter:
                (
                    quarter_start_date,
                    quarter_end_date,
                ) = PerformanceCalculations.get_quarter_dates(current_quarter)

                module_activities = ModuleActivity.objects.filter(
                    module__module__name=module,
                    module__organization=organization,
                    user__deleted=False,
                    active=True,
                )

                module_completed_this_quarter = module_activities.filter(
                    complete_date__gte=quarter_start_date,
                    complete_date__lte=quarter_end_date,
                    complete=True,
                )

                (
                    last_quarter_start_date,
                    last_quarter_end_date,
                ) = PerformanceCalculations.get_quarter_dates(current_quarter - 1)

                module_completed_last_quarter = module_activities.filter(
                    complete_date__gte=last_quarter_start_date,
                    complete_date__lte=last_quarter_end_date,
                    complete=True,
                )

                pending = (
                    module_activities.count() - module_completed_last_quarter.count()
                )
                if pending > 0:
                    completion_rate = (
                        module_completed_this_quarter.count() / pending
                    ) * 100
                else:
                    completion_rate = 0
            elif is_monthly:
                module_users_count = ModuleActivity.objects.filter(
                    module__module__name=module,
                    module__organization=organization,
                    user__deleted=False,
                    user__active=True,
                    active=True,
                )
                completed_till_now = module_users_count.filter(
                    complete=True,
                    complete_date__month__lte=month,
                    complete_date__year=year,
                )
                if module_users_count.count() > 0:
                    overall_monthly_performance = (
                        completed_till_now.count() / module_users_count.count()
                    )
                else:
                    overall_monthly_performance = 0
                completion_rate = round(overall_monthly_performance * 100, 2)
            else:
                total_module_activities = ModuleActivity.objects.filter(
                    module__module__name=module,
                    module__organization=organization,
                    user__deleted=False,
                    active=True,
                )
                completed_module_activities = total_module_activities.filter(
                    complete=True,
                    complete_date__month__lte=month,
                    complete_date__year=year,
                ).count()
                completion_rate = completed_module_activities

            completion_rates[module] = round(completion_rate, 2)

        return completion_rates

    def get_previous_month(current_month, current_year):
        if current_month == 1:
            last_month = 12
            last_month_year = current_year - 1
        else:
            last_month = current_month - 1
            last_month_year = current_year

        return last_month, last_month_year

    def calculate_completion_rate(organization):
        data = {}
        current_month = datetime.now().month
        current_year = datetime.now().year
        last_month, last_month_year = PerformanceCalculations.get_previous_month(
            current_month, current_year
        )
        module_attributes = ModuleAttributes.objects.filter(organization=organization)

        current_month_rates = PerformanceCalculations.get_completion_rate(
            organization, module_attributes, current_month, current_year
        )
        last_month_rates = PerformanceCalculations.get_completion_rate(
            organization, module_attributes, last_month, last_month_year
        )
        module_wise_completion_rate_comparision = {}

        for key in current_month_rates:
            module_wise_completion_rate_comparision[key] = round(
                current_month_rates[key] - last_month_rates[key], 2
            )
        active_module_activity = 0
        for i in current_month_rates:
            active_module_activity += ModuleActivity.objects.filter(
                module__module__name=i,
                module__organization=organization,
                user__deleted=False,
                active=True,
            ).count()
        total_sum_till_date = sum(current_month_rates.values())
        try:
            successful_completion_rate_graph = (
                total_sum_till_date / active_module_activity
            )
        except:
            successful_completion_rate_graph = 0
        successful_completion_rate = total_sum_till_date

        total_sum_till_last_month = sum(last_month_rates.values())
        last_month_successful_completion_rate = total_sum_till_last_month

        successful_completion_rate_comparision = round(
            successful_completion_rate - last_month_successful_completion_rate, 2
        )

        current_month_trend = PerformanceCalculations.get_completion_rate(
            organization, module_attributes, current_month, current_year, True
        )
        last_month_trend = PerformanceCalculations.get_completion_rate(
            organization, module_attributes, last_month, last_month_year, True
        )
        module_wise_monthly_performace_comparison = {}
        for key in current_month_trend:
            module_wise_monthly_performace_comparison[key] = (
                current_month_trend[key] - last_month_trend[key]
            )

        total_trend_sum_till_date = sum(current_month_trend.values())
        successful_completion_trend = total_trend_sum_till_date / len(
            current_month_trend
        )

        total_trend_sum_till_last_month = sum(last_month_trend.values())
        last_month_successful_completion_trend = total_trend_sum_till_last_month / len(
            last_month_trend
        )

        overall_monthly_comparision = round(
            successful_completion_trend - last_month_successful_completion_trend, 2
        )

        counts_by_month = {}
        for i in range(len(module_attributes)):
            module_name = module_attributes[i].module.name
            if module_name not in counts_by_month:
                counts_by_month[module_name] = {}

            for month in calendar.month_name[
                organization.created_at.month : current_month + 1
            ]:
                counts_by_month[module_name][
                    month
                ] = PerformanceCalculations.get_completion_rate(
                    organization,
                    module_attributes,
                    list(calendar.month_name).index(month),
                    current_year,
                    False,
                    True,
                )[
                    module_name
                ]

        if current_month <= 3:
            current_quarter = 1
        elif current_month <= 6:
            current_quarter = 2
        elif current_month <= 9:
            current_quarter = 3
        else:
            current_quarter = 4

        quarters_month_mapping = [
            "JAN - MAR",
            "APR - JUNE",
            "JULY - SEPT",
            "OCT - DEC",
        ]
        module_wise_quarter_performance = {}
        quarter_dict = {}
        for i in range(1, current_quarter + 1):
            quarter_dict.update({"{}".format(quarters_month_mapping[i - 1]): 0.0})

        for i in range(len(module_attributes)):
            module_name = module_attributes[i].module.name
            if module_name not in module_wise_quarter_performance:
                module_wise_quarter_performance[module_name] = {}
                for quarter_number in range(1, current_quarter + 1):
                    module_wise_quarter_performance[module_name][
                        quarters_month_mapping[quarter_number - 1]
                    ] = 0.0
            for quarter_number, quarter in enumerate(
                module_wise_quarter_performance[module_name].keys(), start=1
            ):
                module_wise_quarter_performance[module_name][
                    quarter
                ] = PerformanceCalculations.get_completion_rate(
                    organization,
                    module_attributes,
                    current_month,
                    current_year,
                    False,
                    False,
                    True,
                    quarter_number,
                )[
                    module_name
                ]
        data = {
            "module_wise_completion_rate": current_month_rates,
            "module_wise_completion_rate_comparision": module_wise_completion_rate_comparision,
            "successful_completion_rate": successful_completion_rate,
            "successful_completion_rate_graph": successful_completion_rate_graph,
            "successful_completion_rate_comparision": successful_completion_rate_comparision,
            "module_wise_monthly_performance": current_month_trend,
            "module_wise_monthly_performance_comparison": module_wise_monthly_performace_comparison,
            "overall_monthly_performance": successful_completion_trend,
            "overall_monthly_comparision": overall_monthly_comparision,
            "monthly_counts": counts_by_month,
            "module_wise_quarter_performance": module_wise_quarter_performance,
        }
        return data


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
