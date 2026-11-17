from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import EnvioAcceso, User


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ("email", "full_name", "role", "is_active", "must_change_password")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("last_name", "first_name")

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
