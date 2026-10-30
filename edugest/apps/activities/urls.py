from rest_framework.routers import SimpleRouter

from .views import ActividadViewSet, AdjuntoViewSet, ArchivoEntregaViewSet

router = SimpleRouter()
router.register("actividades", ActividadViewSet, basename="actividad")
router.register("adjuntos", AdjuntoViewSet, basename="adjunto")
router.register("archivos-entrega", ArchivoEntregaViewSet, basename="archivo-entrega")

urlpatterns = router.urls
