"""
Punto único para notificar a los usuarios: registra el aviso en la app y envía el correo.

    notificar(usuarios, Categoria.ACTIVIDADES, "actividad_publicada",
              titulo="Nueva tarea de Matemática", mensaje="...", enlace="/representante/actividades",
              correo=Correo(asunto=..., parrafos=[...], detalles=[("Entrega", "12/11/2026")],
                            boton=("Ver actividad", "/representante/actividades")))

- El aviso en la app usa `titulo` y `mensaje`. El correo puede tener contenido distinto
  (por ejemplo, un código o una contraseña temporal que NO se guardan en la base de datos).
- Respeta las preferencias del usuario, salvo la categoría SEGURIDAD, que siempre se envía.
- El correo se envía después de confirmar la transacción. Por defecto en un hilo aparte
  (no retrasa la respuesta); los avisos de seguridad se envían en el momento (inmediato=True).
"""

import logging
import threading
from dataclasses import dataclass, field

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Categoria, Notificacion, PreferenciaNotificacion

logger = logging.getLogger(__name__)
Estado = Notificacion.EstadoCorreo


@dataclass
class Correo:
    asunto: str
    parrafos: list
    detalles: list = field(default_factory=list)  # [(etiqueta, valor)]
    boton: tuple | None = None  # (texto, ruta en la app)
    destacado: str = ""  # código OTP o contraseña temporal, en grande
    nota: str = ""


def url_app(ruta=""):
    base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base}{ruta}" if ruta else base


def _institucion():
    return getattr(settings, "INSTITUCION_NOMBRE", "") or "EduGest"


def preferencias(usuario):
    pref, _ = PreferenciaNotificacion.objects.get_or_create(usuario=usuario)
    return pref


def _mensaje_correo(usuario, correo):
    contexto = {
        "nombre": usuario.first_name or usuario.full_name,
        "correo": correo,
        "boton_url": url_app(correo.boton[1]) if correo.boton else "",
        "institucion": _institucion(),
        "url_app": url_app(),
        "url_preferencias": url_app("/notificaciones"),
        "anio": timezone.localdate().year,
    }
    html = render_to_string("notifications/correo.html", contexto)
    texto = render_to_string("notifications/correo.txt", contexto)
    mensaje = EmailMultiAlternatives(
        subject=f"{correo.asunto} · EduGest", body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[usuario.email],
    )
    mensaje.attach_alternative(html, "text/html")
    return mensaje


def _enviar(pendientes):
    """pendientes: [(notificacion_id, usuario, Correo)]. Actualiza el estado de cada aviso."""
    for notificacion_id, usuario, correo in pendientes:
        try:
            _mensaje_correo(usuario, correo).send(fail_silently=False)
            Notificacion.objects.filter(pk=notificacion_id).update(estado_correo=Estado.ENVIADO, error_correo="")
        except Exception as exc:  # el aviso queda en la app aunque el correo falle
            logger.warning("Correo no enviado a %s: %s", usuario.email, exc)
            Notificacion.objects.filter(pk=notificacion_id).update(
                estado_correo=Estado.ERROR, error_correo=str(exc)[:300]
            )


def _en_hilo(pendientes):
    def trabajo():
        try:
            _enviar(pendientes)
        finally:
            close_old_connections()

    threading.Thread(target=trabajo, daemon=True, name="edugest-correo").start()


def notificar(usuarios, categoria, tipo, titulo, mensaje, enlace="", correo=None, inmediato=False):
    """Crea un aviso por usuario activo y programa el correo. Devuelve las notificaciones."""
    creadas, pendientes = [], []
    for usuario in {u.pk: u for u in usuarios if u and u.is_active}.values():
        if correo is None:
            estado = Estado.SIN_CORREO
        elif preferencias(usuario).acepta_correo(categoria):
            estado = Estado.PENDIENTE
        else:
            estado = Estado.OMITIDO
        n = Notificacion.objects.create(
            usuario=usuario, categoria=categoria, tipo=tipo, titulo=titulo[:200],
            mensaje=mensaje[:1000], enlace=enlace[:300], estado_correo=estado,
        )
        creadas.append(n)
        if estado == Estado.PENDIENTE:
            pendientes.append((n.pk, usuario, correo))

    if pendientes:
        asincrono = getattr(settings, "NOTIFICACIONES_ASINCRONAS", True) and not inmediato
        transaction.on_commit(lambda: (_en_hilo if asincrono else _enviar)(pendientes))
    return creadas


__all__ = ["Categoria", "Correo", "notificar", "preferencias", "url_app"]
