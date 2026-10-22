"""
Rutas principales del proyecto EduGest (config/urls.py).

Cada módulo expone sus propias rutas bajo el prefijo /api/<modulo>/.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static

from .sistema import health

urlpatterns = [
    # Panel de administración de Django (la ruta se configura desde el .env).
    path(settings.ADMIN_URL, admin.site.urls),

    # Estado del sistema (público): lo consulta el frontend para detectar caídas y mantenimiento.
    path("api/health/", health, name="health"),

    # Módulo 1: autenticación, usuarios y roles.
    path("api/security/", include("apps.security.urls")),

    # Módulos siguientes (se activarán conforme se creen):
    path("api/academic/", include("apps.academic.urls")),
    path("api/activities/", include("apps.activities.urls")),
    path("api/grades/", include("apps.grades.urls")),
    path("api/reinforcement/", include("apps.reinforcement.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
