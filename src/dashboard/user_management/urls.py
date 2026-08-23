from django.urls import path

from dashboard.user_management import views

app_name = "user_management"
urlpatterns = [
    path("", views.UserManagementTemplateView.as_view(), name="home"),
    path("list/", views.UserListView.as_view(), name="list"),
    path("create/", views.CreateUserView.as_view(), name="create"),
    path("<int:pk>/", views.UserDetailView.as_view(), name="detail"),
    path("<int:pk>/update/", views.UserUpdateView.as_view(), name="update"),
    path(
        "<int:pk>/toggle-status/",
        views.ToggleUserStatusView.as_view(),
        name="toggle_status",
    ),
    path(
        "<int:pk>/edit-profile/",
        views.EditUserProfileFormView.as_view(),
        name="edit_profile",
    ),
]
