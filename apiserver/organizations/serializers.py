from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from .models import (
    Organization,
    Category,
    Module,
    Level,
    ModuleAttributes,
    ModuleActivity,
    LevelActivity,
    Attempt,
    Feedback,
    UserActivity,
)
from accounts.models import User
from django.db.models import Sum, Count
from datetime import datetime, timedelta
from collections import Counter
import json
from django.db.models import Q


class ListLevelSerializer(serializers.ModelSerializer):
    user_ids = serializers.ListField(child=serializers.CharField())
    organization_id = serializers.CharField()
    module_name = serializers.CharField()

    class Meta:
        model = Level
        fields = ["user_ids", "organization_id", "module_name"]


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ["name", "id", "category"]


class BaseModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ["name", "id"]


class ModuleLevelSerializer(BaseModuleSerializer):
    levels = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = BaseModuleSerializer.Meta.fields + ["levels"]

    def get_levels(self, instance):
        levels = instance.level_set.all().order_by("level")
        return LevelSerializer(levels, many=True).data


class ModuleAttributesSerializer(serializers.ModelSerializer):
    module = serializers.SerializerMethodField()

    class Meta:
        model = ModuleAttributes
        fields = ["module", "id"]

    def get_module(self, instance):
        include_levels = self.context.get("request").query_params.get(
            "include_levels", None
        )
        if include_levels is not None:
            return ModuleLevelSerializer(instance.module).data
        else:
            return BaseModuleSerializer(instance.module).data


class OrganizationSerilaizer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "logo"]


class IndividualReportSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    time_period = serializers.CharField()
    module_activity_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=0)
    )


class ModuleActivityForPerformanceSerializer(serializers.ModelSerializer):
    organization_id = serializers.CharField(source="user.organization.id")
    module_info = serializers.SerializerMethodField()

    def get_module_info(self, obj):
        return obj.module.module.name

    class Meta:
        model = ModuleActivity
        fields = ["organization_id", "module_info"]


class PerformanceSerializer(serializers.ModelSerializer):
    organization_id = serializers.CharField()
    module_name = serializers.CharField(required=False)

    class Meta:
        model = ModuleActivity
        fields = ["organization_id", "module_name"]


class BasicLevelActivitySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = LevelActivity
        fields = ["id", "name"]

    def get_name(self, instance):
        return instance.level.name


class LevelActivitySerializer(serializers.ModelSerializer):
    total_time = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    level_date = serializers.SerializerMethodField()

    class Meta:
        model = LevelActivity
        fields = ["id", "level", "total_time", "level_date"]

    def get_level(self, instance):
        return instance.level.name

    def get_module(self, instance):
        return instance.level.module.name

    def get_total_time(self, instance):
        return (
            instance.attempt_set.all()
            .aggregate(total_duration=Sum("duration"))
            .get("total_duration")
        )

    def get_level_date(self, instance):
        level_date = instance.attempt_set.filter(level_activity=instance).last()
        return level_date and level_date.created_at.date()


class LevelActivityReportSerializer(serializers.ModelSerializer):
    level = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()
    module = serializers.SerializerMethodField()

    class Meta:
        model = LevelActivity
        fields = ["level", "module", "data"]

    def get_level(self, instance):
        return instance.level.name

    def get_module(self, instance):
        return instance.level.module.name

    def get_data(self, instance):
        attempts = instance.attempt_set.all()
        start_date = self.context.get("start_date")
        end_date = self.context.get("end_date")
        time_period = self.context.get("time_period")

        end_date = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%S.%f%z")
        start_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%S.%f%z")

        final_res = []

        temp_end_date = start_date
        td = 10
        if time_period == "Monthly":
            td = 31

        while temp_end_date <= end_date:
            res_obj = {}
            temp_end_date = start_date + timedelta(td)
            # get data weekly
            res_obj["start_date"] = start_date
            res_obj["end_date"] = temp_end_date
            attempts = attempts.filter(
                start_time__gte=start_date, end_time__lte=temp_end_date
            )
            if attempts:
                res_obj["total_attempts"] = len(attempts)
                res_obj["time_spent"] = attempts.aggregate(
                    total_duration=Sum("duration")
                ).get("total_duration")
                final_res.append(res_obj)

            start_date = temp_end_date
            temp_end_date = temp_end_date + timedelta(td)

        return final_res


class BasicModuleActivitySerializer(serializers.ModelSerializer):
    level_activities = serializers.SerializerMethodField()
    module = serializers.SerializerMethodField()

    class Meta:
        model = ModuleActivity
        fields = ["module", "level_activities"]

    def get_module(self, instance):
        return {"id": instance.module.module.id, "name": instance.module.module.name}

    def get_level_activities(self, instance):
        level_activities = instance.levelactivity_set.all()
        ser = BasicLevelActivitySerializer(level_activities, many=True)
        return ser.data


class ModuleActivitySerializer(serializers.ModelSerializer):
    level_activities = serializers.SerializerMethodField()
    module = serializers.SerializerMethodField()
    current_level = serializers.SerializerMethodField()
    total_attempts = serializers.SerializerMethodField()
    total_duration = serializers.SerializerMethodField()
    level_progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = ModuleActivity
        fields = [
            "module",
            "active",
            "complete",
            "level_activities",
            "current_level",
            "total_attempts",
            "total_duration",
            "level_progress_percentage",
        ]

    def get_level_activities(self, instance):
        level_activities = instance.levelactivity_set.all()
        ser = LevelActivitySerializer(level_activities, many=True)
        return ser.data

    def get_module(self, instance):
        return instance.module.module.name

    def get_current_level(self, instance):
        level_activities = instance.levelactivity_set.all().order_by("level__level")
        if len(level_activities) > 0:
            return LevelActivitySerializer(level_activities.last()).data
        else:
            return {}

    def get_total_attempts(self, instance):
        level_activities = instance.levelactivity_set.all()
        total_attempts_count = 0
        for level_activity in level_activities:
            total_attempts_count += level_activity.attempt_set.all().count()
        return total_attempts_count

    def get_total_duration(self, instance):
        level_activities = instance.levelactivity_set.all()
        total_duration = timedelta(seconds=0)
        for level_activity in level_activities:
            attempts = level_activity.attempt_set.all()
            total_duration_result = attempts.aggregate(
                total_duration=Sum("duration")
            ).get("total_duration")
            if total_duration_result is not None:
                total_duration += total_duration_result
        return total_duration

    def get_level_progress_percentage(self, instance):
        total_levels = (
            Level.objects.filter(module__name=instance.module)
            .prefetch_related("levelactivity_set")
            .count()
        )
        if total_levels > 0:
            level_activities = instance.levelactivity_set.filter(complete=True).count()
            success_percentage = round(level_activities / total_levels * 100, 2)
            if success_percentage.is_integer():
                success_percentage = int(success_percentage)
            success_percentage = "{}%".format(success_percentage)
        else:
            success_percentage = 0
        return success_percentage

    def to_representation(self, instance):
        data = super(ModuleActivitySerializer, self).to_representation(instance)
        level_activities = data["level_activities"]
        total_duration = timedelta(seconds=0)
        for level_activity in level_activities:
            if level_activity["total_time"] is not None:
                total_duration += level_activity["total_time"]
        data["total_time"] = total_duration
        return data


class UserPerformanceSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["user_id", "name", "modules"]

    def get_name(self, instance):
        return instance.get_full_name()

    def get_modules(self, instance):
        module_names = self.context.get("request").query_params.get("modules", None)
        module_activities = ModuleActivity.objects.filter(
            user__user_id=instance.user_id,
            user__organization__id=instance.organization_id,
            active=True,
        )
        if module_names:
            module_names = module_names.split(",")
            module_activities = module_activities.filter(
                module__module__name__in=module_names
            )
        ser = ModuleActivitySerializer(module_activities, many=True)
        return ser.data

    def to_representation(self, instance):
        data = super(UserPerformanceSerializer, self).to_representation(instance)
        module_activities = self.get_modules(instance)
        total_duration = timedelta(seconds=0)
        for module_activity in module_activities:
            total_duration += module_activity["total_time"]
        data["total_time"] = total_duration
        success_percentage = 0
        if data["modules"]:
            module_name = data["modules"][0]["module"]
            try:
                ma = ModuleActivity.objects.get(
                    user=instance, module__module__name=module_name
                )
                assessment_levels = Level.objects.filter(
                    category__name__iexact="assessment", module=ma.module.module
                )
                if assessment_levels:
                    completed_assessment_levels = LevelActivity.objects.filter(
                        module_activity=ma,
                        complete=True,
                        level__in=assessment_levels,
                    )
                    success_percentage = (
                        completed_assessment_levels.count()
                        / assessment_levels.count()
                        * 100
                    )
                else:
                    training_levels = Level.objects.filter(
                        category__name__iexact="training", module=ma.module.module
                    )
                    if training_levels:
                        completed_training_levels = LevelActivity.objects.filter(
                            module_activity=ma,
                            complete=True,
                            level__in=training_levels,
                        )
                        success_percentage = (
                            completed_training_levels.count()
                            / training_levels.count()
                            * 100
                        )

                if success_percentage.is_integer():
                    success_percentage = int(success_percentage)
                else:
                    success_percentage = round(success_percentage, 2)
            except:
                success_percentage = 0
        data["success"] = "{}%".format(success_percentage)
        return data


class AttemptRetriveSerilaizer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.CharField())
    module = serializers.CharField()
    level = serializers.CharField()
    attempt = serializers.IntegerField(required=False)
    organization_id = serializers.IntegerField()


class AttemptNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attempt
        fields = ["attempt_number"]


class BaseAttemptSerializer(serializers.ModelSerializer):
    result = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = ["attempt_number", "duration", "start_time", "end_time", "result"]

    def get_result(self, instance):
        if "passed" in instance.data:
            return instance.data["passed"]
        else:
            return False


class AttemptSerializer(serializers.ModelSerializer):
    data = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = ["user", "data", "duration", "start_time", "end_time"]

    def get_user(self, instance):
        user = instance.level_activity.module_activity.user
        user = User.objects.get(id=user.id)
        return user.get_full_name()

    def get_graph_data(self, game_data, x, y, graph):
        fetch_route_x = x.split(".")
        info_x = game_data[fetch_route_x[0]]
        if len(fetch_route_x) > 1:
            total_iteration = len(fetch_route_x) - 1
            for i in range(1, total_iteration):
                info_x = info_x[fetch_route_x[i]]

        fetch_route_y = y.split(".")
        info_y = game_data[fetch_route_y[0]]
        if len(fetch_route_y) > 1:
            total_iteration = len(fetch_route_y) - 1
            for i in range(1, total_iteration):
                info_y = info_y[fetch_route_y[i]]

        x_label = fetch_route_x[-1]
        y_label = fetch_route_y[-1]

        co_ordinates = []
        additional_fields = []
        additional_data = graph.get("additionalData", None)
        if additional_data is not None:
            additional_fields = self.get_additional_fields(additional_data)

        last_added_time = None
        if info_x and info_y:
            for i in range(0, len(info_x)):
                current_time = round(float(info_x[i][x_label]), 2)
                if last_added_time is None or (
                    current_time - last_added_time >= 2
                ):  # Adjusted to 2 seconds here
                    co_ordinates.append(
                        {
                            "x": current_time,
                            "y": round(float(info_y[i][y_label]), 2),
                        }
                    )
                    last_added_time = current_time

                    for additional_field in additional_fields:
                        list_to_append = additional_field["value_list"]
                        value_to_append = info_x[i][additional_field["fetch_field"]]
                        try:
                            value_to_append = float(value_to_append)
                            value_to_append = round(value_to_append, 2)
                        except:
                            pass  # do nothing
                        list_to_append.append(value_to_append)
                        additional_field["value_list"] = list_to_append

        graph_obj = {
            "name": graph.get("name", ""),
            "type": graph.get("type", ""),
            "xlabel": graph.get("xlabel", None)
            if graph.get("xlabel", None) is not None
            else x_label,
            "ylabel": graph.get("ylabel", None)
            if graph.get("ylabel", None) is not None
            else y_label,
            "data": co_ordinates,
            "additional_data": additional_fields,
        }
        return graph_obj

    def get_additional_fields(self, additional_data):
        additional_fields = []
        for additional_field in additional_data:
            additional_obj = {
                "name": additional_field.get("name", ""),
                "fetch_field": additional_field["data"].split(".")[-1],
                "value_list": [],
                "representation": additional_field.get("representation", ""),
            }
            additional_fields.append(additional_obj)
        return additional_fields

    def get_series_data(self, route, data, additional_data=None):
        fetch_route = route.split(".")
        if len(fetch_route) == 1:
            info = fetch_route
        else:
            info = data[fetch_route[0]]
        if len(fetch_route) > 1:
            total_iteration = len(fetch_route) - 1
            for i in range(1, total_iteration):
                info = info[fetch_route[i]]
        series = []
        additional_fields = []

        if additional_data is not None:
            additional_fields = self.get_additional_fields(additional_data)
        if len(fetch_route) > 1:
            for record in info:
                if record[fetch_route[-1]]:
                    for additional_field in additional_fields:
                        list_to_append = additional_field["value_list"]
                        list_to_append.append(record[additional_field["fetch_field"]])
                        additional_field["value_list"] = list_to_append
                    if isinstance(record[fetch_route[-1]], float):
                        series.append(float(record[fetch_route[-1]]))
                    else:
                        series.append(record[fetch_route[-1]])
                else:
                    series.append(0)
        return series, additional_fields

    def extract_dataset(self, graph_obj, graph, game_data):
        datasets = []
        temp_labels = []
        additional_fields = []
        for dataset in graph.get("datasets", []):
            temp_labels = []
            label = dataset.get("label", "")
            data, additional_fields = self.get_series_data(
                dataset["data"],
                game_data,
                additional_data=graph.get("additionalData", None),
            )
            if dataset["label"]:
                labels, additional_fields = self.get_series_data(
                    dataset["label"],
                    game_data,
                )
                if labels:
                    temp_labels = Counter(labels).keys()
                else:
                    for i in range(0, len(data)):
                        temp_labels.append(str(i))
            else:
                for i in range(0, len(data)):
                    temp_labels.append(str(i))
            datasets.append({"name": label, "data": data})
        graph_obj["labels"] = temp_labels
        graph_obj["data"] = datasets
        graph_obj["additional_data"] = additional_fields
        return graph_obj

    def get_data(self, instance):
        res = {}
        if isinstance(instance.data, str):
            json_data = json.loads(instance.data)
        else:
            json_data = instance.data
        game_data = json_data.get("gameData", None)
        if game_data is not None:
            score = json_data.get("score", None)
            passing_score = instance.level_activity.module_activity.module.passing_score
            if score and passing_score:
                res["score"] = {
                    "score": score if score else 0,
                    "passing_score": passing_score,
                    "result": float(score if score else 0) >= float(passing_score),
                }
            inspections_data = game_data.get("inspections", [])
            mistakes_data = game_data.get("mistakes", [])
            module_name = json_data["module"]["name"]
            mistakes_kpi_mapping = {
                "drove over the speed limit": "MAINTAIN SPEED Move Slowly < 6 km/h",
                "engagement error": "FORK ENGAGEMENT",
                "did not report breakdown during pre ops check": "Operator will choose start unit or breakdown or report to spv before start unit",
                "did not lower forks after stacking": "If operator perform reverse & lower the fork",
                "did not horn while pedestrian in vicinity": "If operator push horn & Stop MHE and 3 meters away",
                "did not horn before starting the engine": "if operator push horn 1x when start engine",
                "did not horn before moving forward": "Operator push horn 2x when going forward",
                "did not horn before moving in reverse": "Operator push horn 3x when going backward",
                "did not press horn when turning into aisles": "Operator push horn 3x3 when going through intersections",
                "fork blending occured": "No Blending",
                "did not maintain forkheight above 15 cm": "Fork height condition (15 cm from floor)",
                "stacking error": "Stacking error",
                "did not fix the pallet postion": "FIX INCORRECT PALLET",
                "did not complete pre operation check": "PRE USE CHECK (YES/NO)",
            }

            if inspections_data and module_name.lower() in ["forklift", "reach truck"]:
                actual_flow = inspections_data[0].get("actualFlow", [])
                user_flow_attempt1 = inspections_data[0]["UserFlow"].get(
                    "UserFlow_Attempt1", []
                )
                user_scores = []

                table_kpis = {
                    k["preCheckCondition"].lower(): k
                    for k in game_data.get("tableKpis", [])
                    if k["hasChecked"] == True
                }

                for i, j in zip(actual_flow, user_flow_attempt1):
                    if (
                        i.lower()
                        == "Choose to turn off the unit before get out of the MHE".lower()
                    ):
                        user_scores.append(2)
                    elif table_kpis.get(i.lower(), None):
                        user_scores.append(j)
                    else:
                        user_scores.append(0)

                for mistake in mistakes_kpi_mapping:
                    exists = any(
                        item["name"].lower() == mistake for item in mistakes_data
                    )
                    if not exists:
                        for idx, a in enumerate(actual_flow):
                            if a.lower() == mistakes_kpi_mapping[mistake].lower():
                                user_scores[idx] = user_flow_attempt1[idx]

                if not game_data.get("tableKpis", []):
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
                    for index, score_kpi in enumerate(actual_flow):
                        if score_kpi.lower() in fixed_table_kpis:
                            user_scores[index] = fixed_table_kpis[score_kpi.lower()]

                ideal_total_time = 0
                for ideal_time in game_data["path"]["idealTime"]:
                    ideal_total_time = ideal_total_time + ideal_time["timeTaken"]

                actual_total_time = 0
                actual_paths = {}
                for actual_path in game_data["path"]["vehicleData"]:
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
                    index = actual_flow.index("ideal vs actual path")
                    user_scores[index] = 5

                user_scores[-1] = sum(user_scores)
                inspections_data[0]["UserFlow"]["user_score"] = user_scores

            res["kpis"] = game_data.get("kpis", [])
            res["kpitask"] = game_data.get("kpitask", [])
            res["generalkpis"] = game_data.get("generalkpis", {})
            res["tasks"] = game_data.get("tasks", None)
            res["mistakes"] = mistakes_data
            res["cycleData"] = game_data.get("cycleData", [])
            res["material"] = game_data.get("material", [])
            res["cases"] = game_data.get("cases", [])
            res["inspections"] = inspections_data
            res["interactionError"] = game_data.get("interactionError", [])
            res["skippedCases"] = game_data.get("skippedCases", [])
            res["wrongCases"] = game_data.get("wrongCases", [])
            res["maintenance"] = game_data.get("maintenance", None)
            res["subActivities"] = game_data.get("subActivities", None)
            res["tableKpis"] = game_data.get("tableKpis", None)
            res["wiredConnections"] = game_data.get("wiredConnections", [])
            res["objectPlacements"] = game_data.get("objectPlacements", [])
            res["wrongConnections"] = game_data.get("wrongConnections", [])
            res["assembly"] = game_data.get("assembly", None)
            res["disAssembly"] = game_data.get("disAssembly", None)
            res["measurement"] = game_data.get("measurement", None)
            res["boxPickupData"] = game_data.get("boxPickupData", [])
            res["boxKeptData"] = game_data.get("boxKeptData", [])
            res["hAxisLines"] = game_data.get("hAxisLines", None)
            res["obstacles"] = game_data.get("obstacles", None)
            res["obstacles1"] = game_data.get("obstacles1", None)
            res["vAxisLines"] = game_data.get("vAxisLines", None)
            res["kpitable"] = game_data.get("kpitable", None)
            res["pathtable"] = game_data.get("pathtable", None)
            res["path"] = None

            if "path" in game_data:
                if (
                    "idealPath" in game_data["path"]
                    and "vehicleData" in game_data["path"]
                ):
                    paths = {}
                    ideal_paths = {}
                    for d in game_data["path"]["idealPath"]:
                        k = d["path"]
                        k = k.lower() if k else "unknown"
                        if k in ideal_paths:
                            ideal_paths[k].append(d)
                        else:
                            ideal_paths[k] = [d]

                    actual_paths = {}
                    for d in game_data["path"]["vehicleData"]:
                        k = d["path"]
                        k = k.lower() if k else "unknown"
                        rounded_time_2_seconds = (
                            round(float(d["time"]) / 2) * 2
                        )  ### new code for path taking 2 sec
                        if k in actual_paths:
                            if rounded_time_2_seconds not in [
                                round(float(item["time"]) / 2) * 2
                                for item in actual_paths[k]
                            ]:
                                actual_paths[k].append(d)
                        else:
                            actual_paths[k] = [d]
                    # if "path-1" in actual_paths:
                    #     del actual_paths["path-1"]
                    paths = {"ideal_path": ideal_paths, "actual_path": actual_paths}
                    if "idealTime" in game_data["path"]:
                        paths["ideal_time"] = game_data["path"]["idealTime"]
                    res["path"] = paths

            if "graph" in game_data and game_data["graph"]:
                all_graphs = []
                # iterate through graphs to be plotted
                for graph in game_data["graph"]:
                    graph_obj = {
                        "name": graph.get("name", ""),
                        "type": graph.get("type", ""),
                    }
                    if (
                        graph["type"] == "doughnut"
                        or graph["type"] == "pie"
                        or graph["type"] == "kpis"
                        or graph["type"] == "kpitask1"
                    ):
                        if graph.get("data", None) is not None:
                            graph["data"] = graph["data"].replace("'", '"')
                            try:
                                series = json.loads(graph["data"])
                                graph_obj["data"] = series.values()
                                graph_obj["labels"] = series.keys()
                            except json.JSONDecodeError:
                                series, additional_fields = self.get_series_data(
                                    graph["data"],
                                    game_data,
                                    additional_data=graph.get("additionalData", None),
                                )
                                graph_obj["data"] = Counter(series).values()
                                graph_obj["additional_data"] = additional_fields
                                graph_obj["labels"] = Counter(series).keys()

                                if graph.get("label", None) is not None:
                                    graph_obj["data"] = series
                                    series, additional_fields = self.get_series_data(
                                        graph["label"],
                                        game_data,
                                        additional_data=graph.get(
                                            "additionalData", None
                                        ),
                                    )
                                    graph_obj["labels"] = series
                        all_graphs.append(graph_obj)

                    elif graph["type"] == "bar" or graph["type"] == "stacked_bar":
                        graph_obj = {"name": graph["name"], "type": graph["type"]}
                        x = graph.get("xAxis", None)
                        y = graph.get("yAxis", None)
                        if x is not None and y is not None:
                            graph_obj["xlabel"] = x
                            graph_obj["ylabel"] = y
                        prefix = graph.get("labels", "")
                        graph_obj = self.extract_dataset(graph_obj, graph, game_data)
                        graph_obj["prefix"] = prefix
                        if graph.get("maxValue", None):
                            graph_obj["maxValue"] = graph["maxValue"]
                        all_graphs.append(graph_obj)

                    elif graph["type"] == "line":
                        graph_obj = {"name": graph["name"], "type": graph["type"]}
                        x = graph.get("xAxis", None)
                        y = graph.get("yAxis", None)

                        if x is not None and y is not None:
                            # check for multiple line graphs
                            if type(x) is list:
                                for i in range(0, len(x)):
                                    graph_obj = self.get_graph_data(
                                        game_data, x=x[i], y=y[i], graph=graph
                                    )

                            else:
                                graph_obj = self.get_graph_data(game_data, x, y, graph)
                        else:
                            graph_obj = self.extract_dataset(
                                graph_obj, graph, game_data
                            )
                            graph_obj["type"] = "multiple_line"
                            x_label = graph.get("label", None)
                            if x_label:
                                graph_obj["xlabel"] = x_label.split(".")[-1]

                        all_graphs.append(graph_obj)

                        h_lines = graph.get("hLines", None)
                        if h_lines is not None:
                            fetch_route = h_lines.split(".")
                            info = None
                            for location in fetch_route:
                                if info is None:
                                    info = game_data[location]
                                else:
                                    info = info[location]

                            graph_obj["hAxisLines"] = info

                res["graphs"] = all_graphs
        return res


class LatestAttemptSerializer(BaseAttemptSerializer):
    level = serializers.CharField(source="level_activity__level__name")
    user_id = serializers.CharField(
        source="level_activity__module_activity__user__user_id"
    )
    first_name = serializers.CharField(
        source="level_activity__module_activity__user__first_name"
    )
    last_name = serializers.CharField(
        source="level_activity__module_activity__user__last_name"
    )
    module = serializers.CharField(
        source="level_activity__module_activity__module__module__name"
    )
    level = serializers.CharField(source="level_activity__level__name")

    class Meta:
        model = Attempt
        fields = [
            "user_id",
            "first_name",
            "last_name",
            "module",
            "level",
            "duration",
            "start_time",
            "end_time",
        ]


class AttemptReportSerializer(BaseAttemptSerializer):
    level = serializers.SerializerMethodField()
    module = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = BaseAttemptSerializer.Meta.fields + ["level", "module"]

    def get_level(self, instance):
        return instance.level_activity.level.name

    def get_module(self, instance):
        return instance.level_activity.module_activity.module.module.name


class AttemptWiseReportSerializer(serializers.ModelSerializer):
    filter_type = serializers.CharField()
    start_date = serializers.CharField(required=False)
    end_date = serializers.CharField(required=False)
    module_names = serializers.ListField()
    user_id = serializers.CharField()
    organization_id = serializers.IntegerField(required=True)

    class Meta:
        model = ModuleActivity
        fields = [
            "filter_type",
            "start_date",
            "end_date",
            "module_names",
            "user_id",
            "organization_id",
        ]


class AttemptWiseReportTableSerializer(serializers.ModelSerializer):
    category_filter = serializers.CharField()
    start_date = serializers.CharField(required=False)
    end_date = serializers.CharField(required=False)
    module_names = serializers.ListField()
    user_id = serializers.CharField()
    organization_id = serializers.IntegerField(required=True)

    class Meta:
        model = ModuleActivity
        fields = [
            "category_filter",
            "start_date",
            "end_date",
            "module_names",
            "user_id",
            "organization_id",
        ]


class ApplicationUsageSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(required=True)

    class Meta:
        model = UserActivity
        fields = ["organization_id"]


class AssignedUsersSerializer(serializers.ModelSerializer):
    modules = serializers.CharField(source="module__module__name")
    user_id = serializers.CharField(source="user__user_id")
    current_level = serializers.CharField()
    level_date = serializers.SerializerMethodField()
    module_usage = serializers.SerializerMethodField()
    total_attempts = serializers.CharField()
    name = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    def get_name(self, obj):
        return f"{obj['user__first_name']} {obj['user__last_name']}"

    def get_module_usage(self, obj):
        if obj["module_usage"]:
            obj["module_usage"] = obj["module_usage"].total_seconds()
        else:
            obj["module_usage"] = timedelta()
        return obj["module_usage"]

    def get_level_date(self, obj):
        if obj["level_date"]:
            obj["level_date"] = obj["level_date"].date()
        else:
            obj["level_date"] = None
        return obj["level_date"]

    def get_progress(self, obj):
        if (
            obj["total_assessment_count"] is not None
            and obj["completed_assessment_count"] is not None
        ):
            progress = round(
                obj["completed_assessment_count"] / obj["total_assessment_count"] * 100,
                2,
            )
        elif (
            obj["total_non_assessment_count"] is not None
            and obj["completed_non_assessment_count"] is not None
        ):
            progress = round(
                obj["completed_non_assessment_count"]
                / obj["total_non_assessment_count"]
                * 100,
                2,
            )
        else:
            progress = 0

        if isinstance(progress, float) and progress.is_integer():
            progress = int(progress)

        return f"{progress}%"

    class Meta:
        model = ModuleActivity
        fields = [
            "modules",
            "name",
            "user_id",
            "current_level",
            "level_date",
            "module_usage",
            "total_attempts",
            "progress",
        ]
