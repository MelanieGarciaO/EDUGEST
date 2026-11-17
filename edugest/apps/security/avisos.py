"""
Correos de la cuenta (categoría SEGURIDAD: siempre se envían, no se pueden desactivar).

El correo es el único canal de las claves temporales: el administrador nunca las ve.
Las claves y códigos van SOLO en el correo; el aviso que queda en la app no los guarda.
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


def _ahora():
    return timezone.localtime().strftime("%d/%m/%Y %H:%M")


# Motivos del correo de acceso (también son el «tipo» de la notificación).
CREADA, REENVIADA, RENOVADA = "cuenta_creada", "acceso_reenviado", "acceso_renovado"
TIPOS_ACCESO = (CREADA, REENVIADA, RENOVADA)

_ASUNTO = {
    CREADA: "Tu cuenta de EduGest está lista",
    REENVIADA: "Nuevo acceso a tu cuenta de EduGest",
    RENOVADA: "Tu nueva contraseña temporal de EduGest",
}
_AVISO = {
    CREADA: "",
    REENVIADA: "Te enviamos una contraseña temporal nueva; la anterior ya no funciona. ",
    RENOVADA: "Tu contraseña temporal anterior venció, así que te enviamos una nueva. ",
}


def cuenta_creada(usuario, temporal, motivo=CREADA, vence_en=None):
    """Contraseña temporal de bienvenida: al crear la cuenta, al reenviarla o al renovarla por vencida."""
    vence = timezone.localtime(vence_en).strftime("%d/%m/%Y a las %H:%M") if vence_en else ""
    detalles = [("Usuario", usuario.email)]
    if vence:
        detalles.append(("Vence", vence))
    return _notificar(
        [usuario], tipo=motivo,
        titulo="¡Bienvenido a EduGest!" if motivo == CREADA else "Nueva contraseña temporal",
        mensaje="Ingresa con la contraseña temporal que te enviamos por correo y crea la tuya.",
        enlace="/cambiar-clave",
        correo=_correo(
            asunto=_ASUNTO[motivo],
            parrafos=[
                f"La institución creó tu cuenta de {usuario.get_role_display().lower()} en EduGest, "
                f"donde podrás {ROLES_INICIO.get(usuario.role, 'usar la plataforma')}.",
                _AVISO[motivo]
                + "Ingresa con tu correo y esta contraseña temporal. Al entrar, el sistema te pedirá crear una propia:",
            ]
            + ([f"Esta contraseña temporal vence el {vence}. Si vence antes de que ingreses, "
                "al intentar entrar te enviaremos una nueva."] if vence else []),
            destacado=temporal,
            detalles=detalles,
            boton=("Ingresar a EduGest", "/login"),
            nota="No compartas esta contraseña: nadie de la institución te la pedirá. "
            "Si no esperabas este correo, comunícate con la institución.",
        ),
    )


def codigo_recuperacion(usuario, codigo, minutos):
    _notificar(
        [usuario], tipo="recuperacion_codigo",
        titulo="Solicitaste recuperar tu contraseña",
        mensaje="Se envió un código de verificación a tu correo.",
        correo=_correo(
            asunto="Tu código para recuperar la contraseña",
            parrafos=[f"Usa este código para recuperar el acceso a EduGest. Vence en {minutos} minutos:"],
            destacado=codigo,
            nota="Si no lo solicitaste, ignora este correo: tu contraseña no cambiará. "
            "Nadie de la institución te pedirá este código.",
        ),
    )


def acceso_recuperado(usuario):
    """Código verificado: la temporal se muestra en pantalla. Aviso solo en la app, sin la clave."""
    _notificar(
        [usuario], tipo="recuperacion_verificada",
        titulo="Verificaste tu código de recuperación",
        mensaje="Se generó una contraseña temporal y se cerraron tus sesiones. Crea tu contraseña nueva.",
        enlace="/cambiar-clave",
    )


def clave_temporal_perfil(usuario, temporal, minutos):
    _notificar(
        [usuario], tipo="clave_temporal_perfil",
        titulo="Solicitaste cambiar tu contraseña",
        mensaje="Te enviamos una clave temporal a tu correo para cambiar la contraseña.",
        correo=_correo(
            asunto="Tu clave temporal para cambiar la contraseña",
            parrafos=[
                "Solicitaste cambiar tu contraseña desde tu perfil de EduGest.",
                f"Escribe esta clave temporal en la pantalla de cambio de contraseña. Vence en {minutos} minutos:",
            ],
            destacado=temporal,
            detalles=[("Fecha", _ahora())],
            nota="Tu contraseña actual sigue funcionando hasta que completes el cambio. "
            "Si no lo solicitaste, ignora este correo y avisa a la institución.",
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
            detalles=[("Fecha", _ahora())],
            nota="Si no fuiste tú, usa «¿Olvidaste tu contraseña?» en la pantalla de inicio o avisa a la institución.",
        ),
    )
