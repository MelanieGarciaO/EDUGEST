"""
Contraseñas de EduGest. El canal de las claves temporales es SIEMPRE el correo del usuario:
el administrador nunca ve ni maneja contraseñas.

1. Alta de cuenta (admin crea el usuario)
   El sistema genera una contraseña temporal y la envía por correo (avisos.cuenta_creada).
   Vence en 2 horas (CLAVE_BIENVENIDA_HORAS). El usuario ingresa con ella y el sistema lo
   obliga a crear la suya (must_change_password).
   Si intenta ingresar con la temporal ya vencida (y la escribe bien), el sistema le envía
   una nueva con otras 2 horas de plazo, y así sucesivamente hasta que active su cuenta.
   Se renueva al intentar ingresar y no con un temporizador: una cuenta sin usar no recibe
   correos indefinidamente.

2. «¿Olvidaste tu contraseña?» (sin sesión)
   a) POST auth/recuperar/solicitar/   {email}            -> código OTP de 6 dígitos por correo.
   b) POST auth/recuperar/verificar/   {email, codigo}    -> la clave temporal aparece EN PANTALLA.
   c) POST auth/recuperar/restablecer/ {email, clave_temporal, new_password}
      -> crea la contraseña nueva en el mismo recuperador y abre la sesión.
   Si el usuario cierra la pantalla después de (b), puede ingresar con la temporal y el
   sistema le pedirá crear su contraseña (igual que en el primer acceso).

3. Cambio desde el Perfil (con sesión)
   a) POST auth/clave-temporal/   -> clave temporal por correo. NO reemplaza la contraseña
      actual: es una credencial aparte, de un solo uso, que vence en 10 minutos.
   b) POST auth/change-password/ {clave_temporal, new_password} -> contraseña nueva.

Protecciones: las claves y códigos se guardan como hash, 5 intentos por clave, una nueva
anula la anterior, espera de 60 s entre solicitudes y máximo 5 por hora.
"""

import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password as validar_fortaleza
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

from . import avisos
from .models import CodigoRecuperacion, User
from .utils import generate_temporary_password, revoke_user_tokens

Tipo = CodigoRecuperacion.Tipo

MENSAJE_SOLICITUD = (
    "Si el correo está registrado, te enviamos un código de 6 dígitos. Revisa tu bandeja de "
    "entrada y la carpeta de spam."
)
MENSAJE_CODIGO_INVALIDO = "El código no es válido o ya venció. Solicita uno nuevo."
MENSAJE_SIN_CLAVE = "Primero solicita una clave temporal; te llegará a tu correo."
MENSAJE_CLAVE_INVALIDA = "La clave temporal no es válida o ya venció. Solicita una nueva."


class ClaveTemporalVencida(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "clave_temporal_vencida"

    def __init__(self, usuario):
        super().__init__({
            "detail": f"Tu contraseña temporal venció. Te enviamos una nueva a {usuario.email}; "
            f"vence en {horas_bienvenida()} horas.",
            "code": "clave_temporal_vencida",
        })


def horas_bienvenida():
    return _ajuste("CLAVE_BIENVENIDA_HORAS", 2)


def asignar_clave_bienvenida(usuario, motivo=avisos.CREADA, enviar_ya=False):
    """
    Genera la contraseña temporal de bienvenida (2 horas de plazo), cierra las sesiones y la
    envía SOLO al correo del usuario. motivo: avisos.CREADA | avisos.REENVIADA | avisos.RENOVADA.
    Devuelve la notificación del correo (con su estado si enviar_ya=True).
    """
    temporal = generate_temporary_password()
    usuario.set_password(temporal)
    usuario.must_change_password = True
    usuario.clave_temporal_expira_en = timezone.now() + timezone.timedelta(hours=horas_bienvenida())
    usuario.save(update_fields=["password", "must_change_password", "clave_temporal_expira_en", "updated_at"])
    revoke_user_tokens(usuario)
    creadas = avisos.cuenta_creada(
        usuario, temporal, motivo=motivo, vence_en=usuario.clave_temporal_expira_en, enviar_ya=enviar_ya
    )
    return creadas[0] if creadas else None


def renovar_si_vencio(usuario, temporal):
    """
    Si el usuario usa su contraseña temporal de bienvenida (correcta) pero ya vencida, le
    envía una nueva y rechaza el intento. Exigir la temporal correcta evita que cualquiera
    llene de correos a otra persona.
    """
    if usuario and usuario.is_active and usuario.clave_temporal_vencida and usuario.check_password(temporal):
        asignar_clave_bienvenida(usuario, motivo=avisos.RENOVADA)
        raise ClaveTemporalVencida(usuario)


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


def _esperar_entre_envios(clave, mensaje_unidad):
    espera = _ajuste("RECUPERACION_ESPERA_SEGUNDOS", 60)
    if cache.get(clave):
        raise DemasiadasSolicitudes(f"Espera {espera} segundos antes de pedir {mensaje_unidad}.")
    cache.set(clave, 1, timeout=espera)


def _nueva_credencial(usuario, tipo, secreto, ip):
    """Anula las credenciales vigentes del mismo tipo y guarda la nueva (solo su hash)."""
    minutos = _ajuste("RECUPERACION_MINUTOS", 10)
    CodigoRecuperacion.objects.filter(usuario=usuario, tipo=tipo, usado_en__isnull=True).update(
        usado_en=timezone.now()
    )
    CodigoRecuperacion.objects.create(
        usuario=usuario, tipo=tipo, codigo_hash=make_password(secreto), ip=ip,
        expira_en=timezone.now() + timezone.timedelta(minutes=minutos),
    )
    return minutos


def _comprobar(usuario, tipo, secreto, mensaje_invalido, incorrecto, pedir_otro):
    """
    Verifica una credencial vigente y la marca como usada. Devuelve un mensaje de error o None.
    Se llama dentro de una transacción; el error se lanza afuera para que el intento quede guardado.
    """
    registro = (
        CodigoRecuperacion.objects.select_for_update().filter(usuario=usuario, tipo=tipo, usado_en__isnull=True).first()
        if usuario else None
    )
    if registro is None or not registro.vigente:
        return mensaje_invalido
    if not check_password(secreto, registro.codigo_hash):
        maximo = _ajuste("RECUPERACION_MAX_INTENTOS", 5)
        registro.intentos += 1
        if registro.intentos >= maximo:
            registro.usado_en = timezone.now()  # se agotaron los intentos: se anula
        registro.save(update_fields=["intentos", "usado_en"])
        restantes = maximo - registro.intentos
        return (
            f"{incorrecto}. Te quedan {restantes} intento{'s' if restantes != 1 else ''}."
            if restantes > 0 else f"{incorrecto}. Se agotaron los intentos: {pedir_otro}."
        )
    registro.usado_en = timezone.now()
    registro.save(update_fields=["usado_en"])
    return None


def _validar_nueva(usuario, nueva, temporal, campo="new_password"):
    if not nueva:
        raise ValidationError({campo: "Escribe la contraseña nueva."})
    if nueva == temporal or usuario.check_password(nueva):
        raise ValidationError({campo: "La contraseña nueva debe ser distinta de la actual y de la temporal."})
    try:
        validar_fortaleza(nueva, usuario)
    except DjangoValidationError as exc:
        raise ValidationError({campo: list(exc.messages)}) from None


def _guardar_nueva(usuario, nueva):
    usuario.set_password(nueva)
    usuario.must_change_password = False
    usuario.clave_temporal_expira_en = None
    usuario.save(update_fields=["password", "must_change_password", "clave_temporal_expira_en", "updated_at"])
    revoke_user_tokens(usuario)
    avisos.clave_cambiada(usuario)


# ---------------------------------------------------------------------------
# 2. «¿Olvidaste tu contraseña?»
# ---------------------------------------------------------------------------
def solicitar(email, ip):
    email = (email or "").strip().lower()
    if not email:
        raise ValidationError({"email": "Escribe tu correo electrónico."})

    _esperar_entre_envios(f"recuperar:espera:{email}", "otro código")
    _limitar(f"recuperar:ip:{ip}", 5, 3600, "Demasiadas solicitudes desde esta red. Intenta en una hora.")
    _limitar(f"recuperar:email:{email}", 5, 3600, "Demasiadas solicitudes para este correo. Intenta en una hora.")

    usuario = User.objects.filter(email__iexact=email, is_active=True).first()
    if usuario is None:
        return  # misma respuesta: no se revela si la cuenta existe

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    with transaction.atomic():
        minutos = _nueva_credencial(usuario, Tipo.RECUPERACION, codigo, ip)
        avisos.codigo_recuperacion(usuario, codigo, minutos)


def verificar(email, codigo, ip):
    """Código correcto -> contraseña temporal que se muestra en el recuperador (no se envía por correo)."""
    email = (email or "").strip().lower()
    codigo = "".join(str(codigo or "").split())
    if not codigo.isdigit() or len(codigo) != 6:
        raise ValidationError({"codigo": "El código tiene 6 dígitos."})
    _limitar(f"recuperar:verificar:ip:{ip}", 20, 3600, "Demasiados intentos desde esta red. Intenta en una hora.")

    usuario = User.objects.filter(email__iexact=email, is_active=True).first()
    temporal = None
    with transaction.atomic():
        error = _comprobar(
            usuario, Tipo.RECUPERACION, codigo, MENSAJE_CODIGO_INVALIDO, "Código incorrecto", "solicita uno nuevo"
        )
        if not error:
            temporal = generate_temporary_password()
            usuario.set_password(temporal)
            usuario.must_change_password = True
            usuario.clave_temporal_expira_en = None  # se muestra en pantalla y se usa enseguida
            usuario.save(update_fields=["password", "must_change_password", "clave_temporal_expira_en", "updated_at"])
            revoke_user_tokens(usuario)
            avisos.acceso_recuperado(usuario)
    if error:
        raise ValidationError({"codigo": error})
    return temporal


def restablecer(email, temporal, nueva, ip):
    """Crea la contraseña nueva en el recuperador, con la temporal que se mostró en pantalla."""
    email = (email or "").strip().lower()
    temporal = (temporal or "").strip()
    _limitar(f"recuperar:restablecer:ip:{ip}", 20, 3600, "Demasiados intentos desde esta red. Intenta en una hora.")
    usuario = User.objects.filter(email__iexact=email, is_active=True).first()
    if usuario is None or not usuario.must_change_password or not temporal or not usuario.check_password(temporal):
        raise ValidationError({"clave_temporal": "La contraseña temporal no es correcta."})
    _validar_nueva(usuario, nueva, temporal)
    with transaction.atomic():
        _guardar_nueva(usuario, nueva)
    return usuario


# ---------------------------------------------------------------------------
# 3. Cambio desde el Perfil
# ---------------------------------------------------------------------------
def solicitar_clave_perfil(usuario, ip):
    """Envía por correo una clave temporal de un solo uso. La contraseña actual NO cambia."""
    if usuario.must_change_password:
        raise ValidationError({"detail": "Ya tienes una contraseña temporal: úsala para crear tu contraseña."})
    _esperar_entre_envios(f"perfil:espera:{usuario.pk}", "otra clave temporal")
    _limitar(f"perfil:hora:{usuario.pk}", 5, 3600, "Pediste demasiadas claves temporales. Intenta en una hora.")
    temporal = generate_temporary_password()
    with transaction.atomic():
        minutos = _nueva_credencial(usuario, Tipo.CAMBIO_CLAVE, temporal, ip)
        avisos.clave_temporal_perfil(usuario, temporal, minutos)
    return minutos


def cambiar_clave(usuario, temporal, nueva):
    """
    Cambia la contraseña con la clave temporal recibida por correo.
    - Primer acceso o tras recuperar la cuenta (must_change_password): la temporal es la
      contraseña con la que ingresó.
    - Desde el Perfil: la temporal es la que pidió con solicitar_clave_perfil.
    """
    temporal = (temporal or "").strip()
    if not temporal:
        raise ValidationError({"clave_temporal": "Escribe la clave temporal que te llegó por correo."})

    if usuario.must_change_password:
        renovar_si_vencio(usuario, temporal)  # venció mientras tenía la sesión abierta
        if not usuario.check_password(temporal):
            raise ValidationError({"clave_temporal": "La contraseña temporal no es correcta."})
        _validar_nueva(usuario, nueva, temporal)
        with transaction.atomic():
            _guardar_nueva(usuario, nueva)
        return usuario

    if not CodigoRecuperacion.objects.filter(usuario=usuario, tipo=Tipo.CAMBIO_CLAVE).exists():
        raise ValidationError({"clave_temporal": MENSAJE_SIN_CLAVE})
    _validar_nueva(usuario, nueva, temporal)  # antes de gastar un intento
    with transaction.atomic():
        error = _comprobar(
            usuario, Tipo.CAMBIO_CLAVE, temporal, MENSAJE_CLAVE_INVALIDA, "Clave temporal incorrecta", "solicita una nueva"
        )
        if not error:
            _guardar_nueva(usuario, nueva)
    if error:
        raise ValidationError({"clave_temporal": error})
    return usuario
