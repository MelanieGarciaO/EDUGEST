from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    ActividadCalificacionesView,
    CalificacionViewSet,
    DesempenoEstudianteView,
    DificultadViewSet,
)

router = SimpleRouter()
router.register("calificaciones", CalificacionViewSet, basename="calificacion")
router.register("dificultades", DificultadViewSet, basename="dificultad")

urlpatterns = [
    path(
        "actividades/<int:actividad_id>/calificaciones/",
        ActividadCalificacionesView.as_view(),
        name="actividad-calificaciones",
    ),
    path(
        "desempeno/estudiantes/<int:estudiante_id>/",
        DesempenoEstudianteView.as_view(),
        name="desempeno-estudiante",
    ),
    *router.urls,
]
