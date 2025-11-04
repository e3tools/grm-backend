from django.urls import path

from dashboard.user_management import views

app_name = "user_management"
urlpatterns = [
    path("", views.UserListView.as_view(), name="list"),
    path("<int:pk>/", views.UserDetailView.as_view(), name="detail"),
    path(
        "toggle-status/<int:pk>/",
        views.ToggleUserStatusView.as_view(),
        name="toggle_status",
    ),
    path(
        "edit-profile/<int:pk>/",
        views.EditUserProfileFormView.as_view(),
        name="edit_profile",
    ),
]
