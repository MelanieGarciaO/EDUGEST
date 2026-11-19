from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.admin_acciones import AccionesActivoMixin, informar

from . import cola_accesos
from .models import EnvioAcceso, User
from .utils import revoke_user_tokens


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(AccionesActivoMixin, DjangoUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ("email", "full_name", "role", "is_active", "must_change_password")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("last_name", "first_name")

    def validar_activo(self, request, obj, valor):
        if not valor and obj.pk == request.user.pk:
            raise ValidationError("No puedes desactivar tu propia cuenta.")

    def aplicar_activo(self, request, obj, valor):
        """Igual que en la app: al desactivar se cierran sus sesiones abiertas."""
        super().aplicar_activo(request, obj, valor)
        if not valor:
            revoke_user_tokens(obj)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "role")}),
        (
            "Estado y permisos",
            {
                "fields": (
                    "is_active",
                    "must_change_password",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(EnvioAcceso)
class EnvioAccesoAdmin(admin.ModelAdmin):
    """Cola de correos de acceso de las importaciones (solo lectura: no hay contraseñas guardadas)."""

    list_display = ("usuario", "estado", "intentos", "programado_en", "enviado_en", "lote")
    list_filter = ("estado",)
    search_fields = ("usuario__email", "lote")
    readonly_fields = [f.name for f in EnvioAcceso._meta.fields]
    actions = ("reintentar_envios", "cancelar_envios")

    @admin.action(description="Reintentar envío (volver a la cola)")
    def reintentar_envios(self, request, queryset):
        """Errores o cancelados vuelven a la cola desde cero. La clave se genera al enviar."""
        estados = (EnvioAcceso.Estado.ERROR, EnvioAcceso.Estado.CANCELADO)
        omitidos = [f"{e.usuario}: está «{e.get_estado_display()}»." for e in queryset.exclude(estado__in=estados)]
        hechos = queryset.filter(estado__in=estados).update(
            estado=EnvioAcceso.Estado.PENDIENTE, intentos=0, ultimo_error="", programado_en=timezone.now()
        )
        if hechos:
            cola_accesos.despertar()
        informar(self, request, hechos, omitidos, "de vuelta en la cola")

    @admin.action(description="Cancelar envío (si aún está en cola)")
    def cancelar_envios(self, request, queryset):
        omitidos = [
            f"{e.usuario}: está «{e.get_estado_display()}»."
            for e in queryset.exclude(estado=EnvioAcceso.Estado.PENDIENTE)
        ]
        hechos = queryset.filter(estado=EnvioAcceso.Estado.PENDIENTE).update(
            estado=EnvioAcceso.Estado.CANCELADO, ultimo_error="Cancelado por el administrador."
        )
        informar(self, request, hechos, omitidos, "cancelados")
