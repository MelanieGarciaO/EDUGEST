"""
API de notificaciones del usuario autenticado.

GET   /api/notifications/                 bandeja (paginada; ?no_leidas=true)
GET   /api/notifications/resumen/         {"no_leidas": n}  (para la campana)
POST  /api/notifications/{id}/leer/       marca una como leída
POST  /api/notifications/leer-todas/      marca todas como leídas
GET   /api/notifications/preferencias/    qué categorías recibir por correo
PATCH /api/notifications/preferencias/
"""

from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.security.permissions import IsPasswordUpToDate

from .models import Categoria
from .serializers import CATEGORIAS_POR_ROL, NotificacionSerializer, PreferenciaSerializer
from .servicio import preferencias


class NotificacionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificacionSerializer
    permission_classes = [IsPasswordUpToDate]

    def get_queryset(self):
        qs = self.request.user.notificaciones.all()
        if self.request.query_params.get("no_leidas") == "true":
            qs = qs.filter(leida=False)
        return qs

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        return Response({"no_leidas": request.user.notificaciones.filter(leida=False).count()})

    @action(detail=True, methods=["post"])
    def leer(self, request, pk=None):
        n = self.get_object()
        if not n.leida:
            n.leida, n.leida_en = True, timezone.now()
            n.save(update_fields=["leida", "leida_en"])
        return Response(NotificacionSerializer(n).data)

    @action(detail=False, methods=["post"], url_path="leer-todas")
    def leer_todas(self, request):
        total = request.user.notificaciones.filter(leida=False).update(leida=True, leida_en=timezone.now())
        return Response({"marcadas": total})

    @action(detail=False, methods=["get", "patch"])
    def preferencias(self, request):
        pref = preferencias(request.user)
        if request.method == "PATCH":
            s = PreferenciaSerializer(pref, data=request.data, partial=True)
            s.is_valid(raise_exception=True)
            s.save()
        disponibles = CATEGORIAS_POR_ROL.get(request.user.role, [])
        return Response({
            **PreferenciaSerializer(pref).data,
            "disponibles": [{"clave": c.lower(), "nombre": Categoria(c).label} for c in disponibles],
        })
