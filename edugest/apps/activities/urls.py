from rest_framework.routers import SimpleRouter

from .views import ActividadViewSet

router = SimpleRouter()
router.register("actividades", ActividadViewSet, basename="actividad")

urlpatterns = router.urls
