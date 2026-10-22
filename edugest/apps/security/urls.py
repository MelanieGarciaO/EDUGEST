from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AceptarTerminosView,
    ChangePasswordView,
    LegalInfoView,
    LoginView,
    LogoutView,
    MeView,
    UserViewSet,
)

router = SimpleRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("auth/aceptar-terminos/", AceptarTerminosView.as_view(), name="aceptar-terminos"),
    path("legal/", LegalInfoView.as_view(), name="legal"),
    *router.urls,
]
