from rest_framework import serializers

from .models import Categoria, Notificacion, PreferenciaNotificacion


class NotificacionSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source="get_categoria_display", read_only=True)

    class Meta:
        model = Notificacion
        fields = ("id", "categoria", "categoria_nombre", "tipo", "titulo", "mensaje", "enlace", "leida", "created_at")
        read_only_fields = fields


class PreferenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreferenciaNotificacion
        fields = ("actividades", "calificaciones", "refuerzo", "recordatorios")


CATEGORIAS_POR_ROL = {
    # Lo que cada rol puede recibir (el docente no recibe avisos de actividades ni notas).
    "REPRESENTANTE": [Categoria.ACTIVIDADES, Categoria.CALIFICACIONES, Categoria.REFUERZO, Categoria.RECORDATORIOS],
    "DOCENTE": [Categoria.REFUERZO],
    "ADMINISTRADOR": [],
}
