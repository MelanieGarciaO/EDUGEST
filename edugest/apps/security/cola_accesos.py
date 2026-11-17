"""
Intermediario de la importación masiva de usuarios: cola de envío de contraseñas temporales.

Problema: si al importar 200 usuarios se generaran y enviaran 200 correos dentro de la misma
petición, la importación tardaría minutos, el servicio de correo rechazaría el exceso
(Resend limita las peticiones por segundo y por día) y un fallo a la mitad dejaría
datos a medias.

Solución (patrón productor-consumidor):
1. La importación (productor) registra a todos los usuarios en UNA transacción y crea un
   EnvioAcceso PENDIENTE por cada uno. Responde enseguida.
2. Un proceso consumidor toma los envíos de uno en uno y, para cada usuario, genera su
   contraseña temporal EN ESE MOMENTO (no se guarda en ningún lado) y la envía por correo.
   - Ritmo controlado: una pausa entre correos (COLA_ACCESOS_PAUSA_SEGUNDOS).
   - Sin duplicados: cada envío se «toma» con SELECT ... FOR UPDATE SKIP LOCKED, así dos
     procesos nunca envían el mismo correo.
   - Reintentos con espera creciente (1, 2, 4 min...) hasta COLA_ACCESOS_MAX_INTENTOS.
   - Si el servicio de correo responde «demasiadas solicitudes» o cuota agotada (429),
     el envío se reprograma sin gastar intentos y el consumidor se pausa.
   - Envíos que quedaron «tomados» por un proceso que se cayó se liberan a los 10 minutos.
3. El consumidor arranca solo (hilo en segundo plano) al confirmar la importación y cuando
   el admin abre la lista de usuarios. También se puede programar el comando
   «python manage.py procesar_envios_acceso» (por ejemplo cada 5 minutos) como respaldo.
"""

import logging
import threading
import time
import uuid

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import EnvioAcceso, User

logger = logging.getLogger(__name__)
Estado = EnvioAcceso.Estado
ACTIVOS = (Estado.PENDIENTE, Estado.ENVIANDO)

_hilo_lock = threading.Lock()
_hilo_activo = False


def _ajuste(nombre, defecto):
    return getattr(settings, nombre, defecto)


def nuevo_lote():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Productor
# ---------------------------------------------------------------------------
def encolar(usuarios, lote):
    """Pone en cola el correo de acceso de cada usuario y despierta al consumidor al confirmar."""
    EnvioAcceso.objects.bulk_create([EnvioAcceso(usuario=u, lote=lote) for u in usuarios])
    transaction.on_commit(despertar)


def cancelar_pendientes(usuario):
    """Al reenviar el acceso a mano, se descarta lo que aún estaba en cola para ese usuario."""
    EnvioAcceso.objects.filter(usuario=usuario, estado__in=ACTIVOS).update(
        estado=Estado.CANCELADO, ultimo_error="Reemplazado por un reenvío manual del administrador."
    )


def resumen_lote(lote):
    conteo = {e: 0 for e in Estado.values}
    for estado in EnvioAcceso.objects.filter(lote=lote).values_list("estado", flat=True):
        conteo[estado] += 1
    return conteo


# ---------------------------------------------------------------------------
# Consumidor
# ---------------------------------------------------------------------------
def _liberar_atascados():
    limite = timezone.now() - timezone.timedelta(minutes=10)
    EnvioAcceso.objects.filter(estado=Estado.ENVIANDO, tomado_en__lt=limite).update(estado=Estado.PENDIENTE)


def _tomar_siguiente():
    """Reserva el siguiente envío listo. SKIP LOCKED evita que dos procesos tomen el mismo."""
    with transaction.atomic():
        envio = (
            EnvioAcceso.objects.select_for_update(skip_locked=True)
            .filter(estado=Estado.PENDIENTE, programado_en__lte=timezone.now())
            .order_by("programado_en", "id").first()
        )
        if envio is None:
            return None
        envio.estado = Estado.ENVIANDO
        envio.tomado_en = timezone.now()
        envio.save(update_fields=["estado", "tomado_en"])
        return envio


def _enviar_uno(envio):
    """Genera la clave temporal y la envía. Devuelve 'ok' | 'error' | 'cuota' | 'omitido'."""
    from .recuperacion import asignar_clave_bienvenida

    usuario = User.objects.get(pk=envio.usuario_id)
    if not (usuario.is_active and usuario.must_change_password and usuario.last_login is None):
        envio.estado = Estado.CANCELADO
        envio.ultimo_error = "La cuenta ya no está pendiente de activar."
        envio.save(update_fields=["estado", "ultimo_error"])
        return "omitido"

    notificacion = asignar_clave_bienvenida(usuario, enviar_ya=True)
    if notificacion is not None and notificacion.estado_correo == notificacion.EstadoCorreo.ENVIADO:
        envio.estado, envio.enviado_en, envio.ultimo_error = Estado.ENVIADO, timezone.now(), ""
        envio.save(update_fields=["estado", "enviado_en", "ultimo_error"])
        return "ok"

    error = (notificacion.error_correo if notificacion else "") or "Error desconocido al enviar."
    envio.ultimo_error = error[:300]
    if " 429" in error or "rate limit" in error.lower() or "quota" in error.lower():
        # El servicio de correo pidió esperar: se reprograma sin gastar un intento.
        envio.estado = Estado.PENDIENTE
        envio.programado_en = timezone.now() + timezone.timedelta(seconds=_ajuste("COLA_ACCESOS_ESPERA_CUOTA", 60))
        envio.save(update_fields=["estado", "programado_en", "ultimo_error"])
        return "cuota"

    envio.intentos += 1
    if envio.intentos >= _ajuste("COLA_ACCESOS_MAX_INTENTOS", 3):
        envio.estado = Estado.ERROR  # el admin lo ve como «Correo no enviado» y puede reenviar
    else:
        envio.estado = Estado.PENDIENTE
        envio.programado_en = timezone.now() + timezone.timedelta(minutes=2 ** (envio.intentos - 1))
    envio.save(update_fields=["estado", "intentos", "programado_en", "ultimo_error"])
    return "error"


def procesar(maximo=None, pausa=None):
    """Envía los correos listos, uno a uno. Devuelve un resumen {'ok': n, 'error': n, ...}."""
    pausa = _ajuste("COLA_ACCESOS_PAUSA_SEGUNDOS", 0.6) if pausa is None else pausa
    resumen = {"ok": 0, "error": 0, "cuota": 0, "omitido": 0}
    _liberar_atascados()
    procesados = 0
    while maximo is None or procesados < maximo:
        envio = _tomar_siguiente()
        if envio is None:
            break
        try:
            resultado = _enviar_uno(envio)
        except Exception as exc:  # nunca se queda tomado por un error inesperado
            logger.exception("Error en la cola de accesos (envío %s)", envio.pk)
            EnvioAcceso.objects.filter(pk=envio.pk).update(
                estado=Estado.PENDIENTE, ultimo_error=str(exc)[:300],
                programado_en=timezone.now() + timezone.timedelta(minutes=1),
            )
            resultado = "error"
        resumen[resultado] += 1
        procesados += 1
        if resultado == "cuota":
            break  # se reintenta más tarde
        if pausa:
            time.sleep(pausa)
    return resumen


def hay_pendientes():
    return EnvioAcceso.objects.filter(estado=Estado.PENDIENTE, programado_en__lte=timezone.now()).exists()


def _trabajo():
    global _hilo_activo
    try:
        while True:
            procesar()
            if not hay_pendientes():
                break
    except Exception:  # pragma: no cover
        logger.exception("La cola de accesos se detuvo")
    finally:
        close_old_connections()
        with _hilo_lock:
            _hilo_activo = False


def despertar():
    """Arranca el consumidor si no está corriendo ya en este proceso."""
    global _hilo_activo
    if not _ajuste("COLA_ACCESOS_ASINCRONA", True):
        procesar(pausa=0)  # pruebas: en el mismo hilo
        return
    with _hilo_lock:
        if _hilo_activo:
            return
        _hilo_activo = True
    threading.Thread(target=_trabajo, daemon=True, name="edugest-cola-accesos").start()


def despertar_si_hay_pendientes():
    if hay_pendientes():
        despertar()
