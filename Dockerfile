FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# Instalar dependencias del sistema necesarias (compiladores, SSL, etc.)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Actualizar pip y herramientas base
RUN pip install --upgrade pip setuptools wheel

# Instalar TODAS las dependencias Python (tanto para versión ligera como pesada)
RUN pip install --no-cache-dir \
    requests>=2.28.0 \
    beautifulsoup4>=4.11.0 \
    faker>=20.0.0 \
    capsolver>=1.0.0 \
    curl_cffi>=0.5.0 \
    flask>=2.3.0 \
    flask-cors>=4.0.0 \
    gunicorn>=21.2.0 \
    playwright>=1.35.0 \
    2captcha-python>=1.2.0 \
    anticaptchaofficial>=1.0.5 \
    nest_asyncio>=1.5.0

# Instalar navegadores de Playwright (necesario para la versión pesada)
RUN playwright install chromium
RUN playwright install-deps

# Copiar tu script (asegúrate de que el nombre del archivo coincida)
COPY amazon_cookie_gen.py .

# Exponer el puerto que usa tu API (8080 en tu configuración)
EXPOSE 8080

# Comando de inicio (puedes cambiarlo a gunicorn si quieres)
CMD ["python", "amazon_cookie_gen.py"]