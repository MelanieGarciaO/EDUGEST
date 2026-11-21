# Imagen del backend de EduGest para Render (servicio web y cron jobs).
# Incluye Tesseract con el idioma español para leer fotos y PDF escaneados (OCR).
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000

# Tesseract + idioma español. Sin recomendados para que la imagen sea liviana.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Primero las dependencias (incluye el modelo es_core_news_sm de spaCy): esta capa se
# reutiliza mientras requirements.txt no cambie, y el build es más rápido.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Archivos estáticos del panel de administración (WhiteNoise). Django solo necesita
# valores de relleno para cargar la configuración; no se conecta a la base de datos.
RUN SECRET_KEY=solo-para-collectstatic DB_NAME=x DB_USER=x DB_PASSWORD=x \
    python manage.py collectstatic --noinput

# Usuario sin privilegios.
RUN useradd --create-home --uid 1000 edugest && chown -R edugest /app
USER edugest

EXPOSE 10000

# Al arrancar: aplica las migraciones pendientes y levanta Gunicorn.
# Render define PORT y WEB_CONCURRENCY (1 en el plan gratis: 512 MB no alcanzan para dos copias de spaCy).
# --timeout 180: la IA puede tardar hasta 150 s (IA_TIMEOUT_SEGUNDOS).
CMD python manage.py migrate --noinput && gunicorn edugest.wsgi:application --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-1} --threads 4 --timeout 180 --access-logfile -
