from django.urls import path
from .views import (
    DownloadTemplate,
    CreateUpdateUsersFromCSV,
    UsersView,
    UserProfileView,
    CreateUser,
    CreateUpdateUsersFromCSV,
    AdminLoginView,
    UserLoginView,
    UsersDeleteView,
    UserDetailsView,
    DownloadListView,
    ForgotPassword,
    PasswordResetAPIView,
    UpdateUserView,
    ProfileUpdateAPIView,
    OrganizationLearnerIdsAPIView,
    ValidatePasswordToken,
)
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
    TokenObtainPairView,
    TokenBlacklistView,
)


urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("download-csv-template/<str>/<int:org_id>/", DownloadTemplate.as_view()),
    path("create-user/", CreateUser.as_view()),
    path("update-user/<str:user_id>/", UpdateUserView.as_view()),
    path("import-users-from-csv/", CreateUpdateUsersFromCSV.as_view()),
    path("list-users/", UsersView.as_view()),
    path("user-profile/<int:id>/", UserProfileView.as_view()),
    path("login/", AdminLoginView.as_view()),
    path("user-login/", UserLoginView.as_view()),
    path("delete-users/", UsersDeleteView.as_view()),
    path("user-details/", UserDetailsView.as_view()),
    path("token/logout/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("download-list/", DownloadListView.as_view()),
    path("reset-password/", PasswordResetAPIView.as_view()),
    path("forgot-password/", ForgotPassword.as_view()),
    path("validate-reset-password-token/", ValidatePasswordToken.as_view()),
    path("update-trainer-profile/", ProfileUpdateAPIView.as_view()),
    path(
        "learners/<int:organization_id>/",
        OrganizationLearnerIdsAPIView.as_view(),
    ),
]
