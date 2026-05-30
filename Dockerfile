FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# Instalar dependencias del sistema necesarias (incluyendo para Pillow)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Actualizar pip y setuptools
RUN pip install --upgrade pip setuptools wheel

# Instalar dependencias básicas primero
RUN pip install --no-cache-dir requests>=2.28.0 beautifulsoup4>=4.11.0

# Instalar playwright y navegadores
RUN pip install --no-cache-dir playwright>=1.35.0
RUN playwright install chromium
RUN playwright install-deps

# Instalar 2captcha
RUN pip install --no-cache-dir 2captcha-python>=1.2.0

# Instalar anticaptcha oficial (con todas sus dependencias)
RUN pip install --no-cache-dir anticaptchaofficial>=1.0.5

# Instalar nest_asyncio, Flask, CORS, gunicorn
RUN pip install --no-cache-dir nest_asyncio>=1.5.0 flask>=2.3.0 flask-cors>=4.0.0 gunicorn>=21.2.0

RUN pip install --no-cache-dir --force-reinstall anticaptchaofficial

RUN pip install curl_cffi

# Copiar el script
COPY amazon_cookie_gen.py .

EXPOSE 8080
CMD ["python", "amazon_cookie_gen.py"]