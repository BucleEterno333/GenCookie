FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias básicas primero
RUN pip install --no-cache-dir requests>=2.28.0

# Instalar beautifulsoup4
RUN pip install --no-cache-dir beautifulsoup4>=4.11.0

# Instalar playwright
RUN pip install --no-cache-dir playwright>=1.35.0

# Instalar navegadores de Playwright
RUN playwright install chromium
RUN playwright install-deps

# Instalar 2captcha
RUN pip install --no-cache-dir 2captcha-python>=1.2.0

# Instalar twocaptcha
RUN pip install --no-cache-dir twocaptcha>=1.3.0

# Instalar anticaptcha
RUN pip install --no-cache-dir anticaptchaofficial>=1.0.5

# Instalar nest_asyncio
RUN pip install --no-cache-dir nest_asyncio>=1.5.0

# Instalar Flask y dependencias web
RUN pip install --no-cache-dir flask>=2.3.0
RUN pip install --no-cache-dir flask-cors>=4.0.0

# Instalar gunicorn para producción (opcional)
RUN pip install --no-cache-dir gunicorn>=21.2.0

# Copiar el script
COPY amazon_cookie_gen.py .

# Puerto que expone la aplicación
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["python", "amazon_cookie_gen.py"]