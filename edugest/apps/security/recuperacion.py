"""
Recuperación de contraseña con código OTP por correo.

Flujo:
1. POST auth/recuperar/solicitar/ {email}
   Si el correo pertenece a una cuenta activa, se envía un código de 6 dígitos (válido
   10 minutos). La respuesta es SIEMPRE la misma, exista o no la cuenta (no revela qué
   correos están registrados).
2. POST auth/recuperar/verificar/ {email, codigo}
   Si el código es correcto, se genera una contraseña TEMPORAL: se muestra una vez en
   pantalla y también se envía por correo. Se cierran las sesiones abiertas.
3. El usuario inicia sesión con la temporal y el sistema lo obliga a crear su contraseña
   nueva (must_change_password), con el flujo de primer acceso que ya existe.

Protecciones: código guardado como hash, 5 intentos por código, un código nuevo invalida
los anteriores, espera de 60 s entre solicitudes y máximo 5 por hora por correo y por IP.
"""

import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from .models import CodigoRecuperacion, User
from .utils import generate_temporary_password, revoke_user_tokens

MENSAJE_SOLICITUD = (
    "Si el correo está registrado, te enviamos un código de 6 dígitos. Revisa tu bandeja de "
    "entrada y la carpeta de spam."
)
MENSAJE_CODIGO_INVALIDO = "El código no es válido o ya venció. Solicita uno nuevo."


def _ajuste(nombre, defecto):
    return getattr(settings, nombre, defecto)


class DemasiadasSolicitudes(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "demasiadas_solicitudes"


def _limitar(clave, maximo, segundos, mensaje):
    usos = cache.get(clave, 0)
    if usos >= maximo:
        raise DemasiadasSolicitudes(mensaje)
    cache.set(clave, usos + 1, timeout=segundos)


def solicitar(email, ip):
    email = (email or "").strip().lower()
    if not email:
        raise ValidationError({"email": "Escribe tu correo electrónico."})

    espera = _ajuste("RECUPERACION_ESPERA_SEGUNDOS", 60)
    if cache.get(f"recuperar:espera:{email}"):
        raise DemasiadasSolicitudes(f"Espera {espera} segundos antes de pedir otro código.")
    _limitar(f"recuperar:ip:{ip}", 5, 3600, "Demasiadas solicitudes desde esta red. Intenta en una hora.")
    _limitar(f"recuperar:email:{email}", 5, 3600, "Demasiadas solicitudes para este correo. Intenta en una hora.")
    cache.set(f"recuperar:espera:{email}", 1, timeout=espera)

    usuario = User.objects.filter(email__iexact=email, is_active=True).first()
    if usuario is None:
        return  # misma respuesta: no se revela si la cuenta existe

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    minutos = _ajuste("RECUPERACION_MINUTOS", 10)
    with transaction.atomic():
        CodigoRecuperacion.objects.filter(usuario=usuario, usado_en__isnull=True).update(usado_en=timezone.now())
        CodigoRecuperacion.objects.create(
            usuario=usuario, codigo_hash=make_password(codigo), ip=ip,
            expira_en=timezone.now() + timezone.timedelta(minutes=minutos),
        )
        _avisar_codigo(usuario, codigo, minutos)


def verificar(email, codigo, ip):
    email = (email or "").strip().lower()
    codigo = "".join(str(codigo or "").split())
    if not codigo.isdigit() or len(codigo) != 6:
        raise ValidationError({"codigo": "El código tiene 6 dígitos."})
    _limitar(f"recuperar:verificar:ip:{ip}", 20, 3600, "Demasiados intentos desde esta red. Intenta en una hora.")

    usuario = User.objects.filter(email__iexact=email, is_active=True).first()
    error, temporal = None, None
    # El error se lanza FUERA de la transacción: así el intento fallido queda guardado.
    with transaction.atomic():
        registro = (
            CodigoRecuperacion.objects.select_for_update().filter(usuario=usuario, usado_en__isnull=True).first()
            if usuario else None
        )
        maximo = _ajuste("RECUPERACION_MAX_INTENTOS", 5)
        if registro is None or not registro.vigente:
            error = MENSAJE_CODIGO_INVALIDO
        elif not check_password(codigo, registro.codigo_hash):
            registro.intentos += 1
            if registro.intentos >= maximo:
                registro.usado_en = timezone.now()  # se agotaron los intentos: se invalida
            registro.save(update_fields=["intentos", "usado_en"])
            restantes = maximo - registro.intentos
            error = (
                f"Código incorrecto. Te quedan {restantes} intento{'s' if restantes != 1 else ''}."
                if restantes > 0 else "Código incorrecto. Se agotaron los intentos: solicita uno nuevo."
            )
        else:
            registro.usado_en = timezone.now()
            registro.save(update_fields=["usado_en"])
            temporal = generate_temporary_password()
            usuario.set_password(temporal)
            usuario.must_change_password = True
            usuario.save(update_fields=["password", "must_change_password", "updated_at"])
            revoke_user_tokens(usuario)
            _avisar_temporal(usuario, temporal, ip)
    if error:
        raise ValidationError({"codigo": error})
    return temporal


# ---------------------------------------------------------------------------
# Correos (categoría SEGURIDAD: siempre se envían). El código y la contraseña van solo
# en el correo; el aviso que queda en la app no los contiene.
# ---------------------------------------------------------------------------
def _avisar_codigo(usuario, codigo, minutos):
    from apps.notifications.models import Categoria
    from apps.notifications.servicio import Correo, notificar

    notificar(
        [usuario], Categoria.SEGURIDAD, "recuperacion_codigo",
        titulo="Solicitaste recuperar tu contraseña",
        mensaje="Se envió un código de verificación a tu correo.",
        correo=Correo(
            asunto="Tu código para recuperar la contraseña",
            parrafos=[f"Usa este código para recuperar el acceso a EduGest. Vence en {minutos} minutos:"],
            destacado=codigo,
            nota="Si no lo solicitaste, ignora este correo: tu contraseña no cambiará. Nadie de la institución te pedirá este código.",
        ),
        inmediato=True,
    )


def _avisar_temporal(usuario, temporal, ip):
    from apps.notifications.models import Categoria
    from apps.notifications.servicio import Correo, notificar

    notificar(
        [usuario], Categoria.SEGURIDAD, "recuperacion_temporal",
        titulo="Se restableció tu contraseña",
        mensaje="Recuperaste el acceso con un código. Crea tu contraseña nueva al ingresar.",
        enlace="/cambiar-clave",
        correo=Correo(
            asunto="Tu contraseña temporal",
            parrafos=["Verificaste tu código. Esta es tu contraseña temporal; al ingresar, el sistema te pedirá crear una nueva:"],
            destacado=temporal,
            detalles=[("Correo", usuario.email), ("Fecha", timezone.localtime().strftime("%d/%m/%Y %H:%M"))],
            boton=("Ingresar a EduGest", "/login"),
            nota="Si no fuiste tú, avisa de inmediato a la administración de tu institución.",
        ),
        inmediato=True,
    )
