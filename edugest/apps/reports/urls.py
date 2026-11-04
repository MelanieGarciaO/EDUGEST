from django.urls import path

from .views import CatalogoReportesView, DescargarReporteView

urlpatterns = [
    path("", CatalogoReportesView.as_view(), name="reportes-catalogo"),
    path("<slug:clave>/", DescargarReporteView.as_view(), name="reportes-descargar"),
]
