"""
Correos de la cuenta (categoría SEGURIDAD: siempre se envían, no se pueden desactivar).

- Alta de usuario: la contraseña temporal va SOLO por correo al usuario; el administrador
  nunca la ve y no se crea aviso en la app.
- Cambio de contraseña: correo + aviso en la app (alerta de seguridad).
- Recuperación con código (recuperacion.py): la temporal se muestra al propio usuario en
  pantalla y también va por correo.
El administrador ya no puede restablecer contraseñas: el usuario la cambia o la recupera.
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
    """
    Bienvenida con la contraseña temporal. Va SOLO por correo (el usuario aún no puede entrar
    a la plataforma) y se envía en el momento: si falla, lanza la excepción y la cuenta no se crea.
    """
    from apps.notifications.servicio import enviar_correo

    enviar_correo(usuario, _correo(
        asunto="Tu cuenta de EduGest está lista",
        parrafos=[
            f"La institución creó tu cuenta de {usuario.get_role_display().lower()} en EduGest, "
            f"donde podrás {ROLES_INICIO.get(usuario.role, 'usar la plataforma')}.",
            "Ingresa con tu correo y esta contraseña temporal. Al entrar, el sistema te pedirá crear una propia:",
        ],
        destacado=temporal,
        detalles=[("Usuario", usuario.email)],
        boton=("Ingresar a EduGest", "/login"),
        nota="No compartas esta contraseña; nadie de la institución la conoce. Si la pierdes, usa "
        "«¿Olvidaste tu contraseña?» en la pantalla de inicio. Si no esperabas este correo, comunícate con la institución.",
    ))


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
