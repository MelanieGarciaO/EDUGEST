"""
Backend de correo de Django que envía con la API de Resend (https://resend.com).

Configuración (.env):
    EMAIL_BACKEND=apps.notifications.backends.ResendEmailBackend
    RESEND_API_KEY=re_...
    DEFAULT_FROM_EMAIL=EduGest <onboarding@resend.dev>   (o un remitente de tu dominio verificado)

Usa la API HTTPS con `requests` (ya es dependencia del proyecto), así no hace falta un SDK.
Todo el resto del sistema sigue usando la API normal de Django (send_mail / EmailMessage).
"""

import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

URL = "https://api.resend.com/emails"


class ResendError(Exception):
    pass


class ResendEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "RESEND_API_KEY", "")
        self.timeout = getattr(settings, "RESEND_TIMEOUT_SEGUNDOS", 15)

    def _payload(self, mensaje):
        datos = {
            "from": mensaje.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(mensaje.to),
            "subject": mensaje.subject,
            "text": mensaje.body,
        }
        if mensaje.cc:
            datos["cc"] = list(mensaje.cc)
        if mensaje.bcc:
            datos["bcc"] = list(mensaje.bcc)
        if mensaje.reply_to:
            datos["reply_to"] = list(mensaje.reply_to)
        for contenido, tipo in getattr(mensaje, "alternatives", []) or []:
            if tipo == "text/html":
                datos["html"] = contenido
        return datos

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise ResendError("Falta RESEND_API_KEY en el .env.")
        enviados = 0
        for mensaje in email_messages:
            try:
                respuesta = requests.post(
                    URL,
                    json=self._payload(mensaje),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=self.timeout,
                )
                if respuesta.status_code >= 400:
                    try:
                        detalle = respuesta.json().get("message", respuesta.text)
                    except ValueError:
                        detalle = respuesta.text
                    raise ResendError(f"Resend {respuesta.status_code}: {detalle}"[:300])
                enviados += 1
            except (requests.RequestException, ResendError) as exc:
                logger.warning("No se pudo enviar el correo a %s: %s", mensaje.to, exc)
                if not self.fail_silently:
                    raise ResendError(str(exc)[:300]) from exc
        return enviados
