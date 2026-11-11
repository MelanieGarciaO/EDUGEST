"""
Correos de la cuenta (categoría SEGURIDAD: siempre se envían, no se pueden desactivar).
Las contraseñas temporales van SOLO en el correo; el aviso que queda en la app no las guarda.
"""

from django.utils import timezone

ROLES_INICIO = {
    "ADMINISTRADOR": "administrar la plataforma de tu institución",
    "DOCENTE": "publicar actividades, registrar notas y preparar planes de refuerzo",
    "REPRESENTANTE": "seguir las actividades, notas y planes de refuerzo de tu representado",
}


def _notificar(*args, **kwargs):
    from apps.notifications.models import Categoria
    from apps.notifications.servicio import notificar

    return notificar(*args, categoria=Categoria.SEGURIDAD, inmediato=True, **kwargs)


def _correo(**kwargs):
    from apps.notifications.servicio import Correo

    return Correo(**kwargs)


def cuenta_creada(usuario, temporal):
    _notificar(
        [usuario], tipo="cuenta_creada",
        titulo="¡Bienvenido a EduGest!",
        mensaje="Tu cuenta fue creada. Cambia la contraseña temporal en tu primer ingreso.",
        correo=_correo(
            asunto="Tu cuenta de EduGest está lista",
            parrafos=[
                f"La institución creó tu cuenta de {usuario.get_role_display().lower()} en EduGest, "
                f"donde podrás {ROLES_INICIO.get(usuario.role, 'usar la plataforma')}.",
                "Ingresa con tu correo y esta contraseña temporal. Al entrar, el sistema te pedirá crear una propia:",
            ],
            destacado=temporal,
            detalles=[("Usuario", usuario.email)],
            boton=("Ingresar a EduGest", "/login"),
            nota="No compartas esta contraseña. Si no esperabas este correo, comunícate con la institución.",
        ),
    )


def clave_restablecida(usuario, temporal, por):
    _notificar(
        [usuario], tipo="clave_restablecida",
        titulo="La administración restableció tu contraseña",
        mensaje="Ingresa con la contraseña temporal que te enviamos por correo y crea una nueva.",
        enlace="/cambiar-clave",
        correo=_correo(
            asunto="Se restableció tu contraseña",
            parrafos=[
                "La administración de tu institución restableció tu contraseña de EduGest. "
                "Se cerraron tus sesiones abiertas.",
                "Ingresa con esta contraseña temporal; el sistema te pedirá crear una nueva:",
            ],
            destacado=temporal,
            detalles=[("Usuario", usuario.email), ("Fecha", timezone.localtime().strftime("%d/%m/%Y %H:%M"))],
            boton=("Ingresar a EduGest", "/login"),
            nota="Si no lo solicitaste, comunícate con la institución.",
        ),
    )


def clave_cambiada(usuario):
    _notificar(
        [usuario], tipo="clave_cambiada",
        titulo="Tu contraseña se actualizó",
        mensaje="Se cambió la contraseña de tu cuenta y se cerraron las demás sesiones.",
        correo=_correo(
            asunto="Tu contraseña se actualizó",
            parrafos=["La contraseña de tu cuenta de EduGest se cambió correctamente. Se cerraron las demás sesiones abiertas."],
            detalles=[("Fecha", timezone.localtime().strftime("%d/%m/%Y %H:%M"))],
            nota="Si no fuiste tú, usa «¿Olvidaste tu contraseña?» en la pantalla de inicio o avisa a la institución.",
        ),
    )
