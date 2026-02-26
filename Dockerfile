FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para aprovechar caché de Docker
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright
RUN playwright install chromium
RUN playwright install-deps

# Copiar el script
COPY amazon_cookie_gen.py .

# Puerto que expone la aplicación
EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["python", "amazon_cookie_gen.py"]