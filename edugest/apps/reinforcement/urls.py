from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    ActividadRefuerzoViewSet,
    AlertaTempranaView,
    PlanViewSet,
    RecursoViewSet,
    TemaPlanViewSet,
)

router = SimpleRouter()
router.register("recursos", RecursoViewSet, basename="recurso")
router.register("planes", PlanViewSet, basename="plan")
router.register("temas-plan", TemaPlanViewSet, basename="tema-plan")
router.register("actividades", ActividadRefuerzoViewSet, basename="actividad-refuerzo")

urlpatterns = [
    path("alerta-temprana/", AlertaTempranaView.as_view(), name="alerta-temprana"),
    *router.urls,
]
