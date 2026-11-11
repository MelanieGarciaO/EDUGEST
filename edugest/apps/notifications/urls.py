from rest_framework.routers import SimpleRouter

from .views import NotificacionViewSet

router = SimpleRouter()
router.register("", NotificacionViewSet, basename="notificacion")

urlpatterns = router.urls
