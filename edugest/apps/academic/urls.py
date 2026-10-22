from rest_framework.routers import SimpleRouter

from .views import (
    AsignaturaViewSet,
    AsignacionDocenteViewSet,
    EstudianteViewSet,
    GradoViewSet,
    ParaleloViewSet,
    TemaViewSet,
)

router = SimpleRouter()
router.register("grados", GradoViewSet, basename="grado")
router.register("paralelos", ParaleloViewSet, basename="paralelo")
router.register("asignaturas", AsignaturaViewSet, basename="asignatura")
router.register("estudiantes", EstudianteViewSet, basename="estudiante")
router.register("asignaciones", AsignacionDocenteViewSet, basename="asignacion")
router.register("temas", TemaViewSet, basename="tema")

urlpatterns = router.urls