from django.urls import path
from .views import (
    OrgModulesApiView,
    ModuleAssignmentView,
    ActiveModulesCountView,
    ActiveUsersCountView,
    OrganizationListView,
    OrganizationView,
    PerformanceView,
    CompleteModuleView,
    UserAttemptView,
    AttemptDataApiView,
    ModuleLevelView,
    # LeaderBoardView,
    UserPerformanceView,
    ApplicationUsageApiView,
    LatestAttemptsApiView,
    IndividualUserReportApiView,
    AssignedUsersApiView,
    LevelActivityApiView,
    AttemptsListApiView,
    ListLevelsAPIView,
    AttemptWiseReportAPIView,
    AttemptWiseReportTableAPIView,
    ApplicationUsageAnalyticsAPIView,
    TotalActiveModuleAndUsersAPIView,
    AdminOrganizationApplicationUsageAPIView,
    LevelUserInfo,
    PerformanceCharts,
)

urlpatterns = [
    path("modules/", OrgModulesApiView.as_view()),
    path("assign-deassign/", ModuleAssignmentView.as_view()),
    path("list/", OrganizationListView.as_view()),
    path("details/<slug:slug>/", OrganizationView.as_view()),
    path("module-analytics/", ActiveModulesCountView.as_view()),
    path("user-analytics/", ActiveUsersCountView.as_view()),
    path("complete/", CompleteModuleView.as_view()),
    path("calculate-performances/", PerformanceView.as_view()),
    path("application-usage/<int:usecase>/", ApplicationUsageApiView.as_view()),
    path("user-attempt-details/", UserAttemptView.as_view()),
    path("attempt-data/", AttemptDataApiView.as_view()),
    path("user-assigned-module-level/", ModuleLevelView.as_view()),
    # path("leader-board/", LeaderBoardView.as_view()),
    path("user-performance/<slug:user_id>/", UserPerformanceView.as_view()),
    path("assigned-users-list/", AssignedUsersApiView.as_view()),
    path("latest-attempts/", LatestAttemptsApiView.as_view()),
    path("individual-report/", IndividualUserReportApiView.as_view()),
    path("level-wise-analytics/", LevelActivityApiView.as_view()),
    path("level-user-info/", LevelUserInfo.as_view()),
    path("attempts/", AttemptsListApiView.as_view()),
    path("list-levels/", ListLevelsAPIView.as_view()),
    path("attempt-wise-report/", AttemptWiseReportAPIView.as_view()),
    path("attempt-wise-report-table/", AttemptWiseReportTableAPIView.as_view()),
    path("performance-charts/", PerformanceCharts.as_view()),
    path(
        "application-usage-analytics/<int:usecase>/",
        ApplicationUsageAnalyticsAPIView.as_view(),
    ),
    path(
        "total-active-module-and-users/",
        TotalActiveModuleAndUsersAPIView.as_view(),
    ),
    path(
        "admin-organization-application-usage/",
        AdminOrganizationApplicationUsageAPIView.as_view(),
    ),
]
