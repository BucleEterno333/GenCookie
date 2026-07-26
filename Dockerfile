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

# Copiar requirements.txt primero para aprovechar caché
COPY requirements.txt .

# Instalar TODAS las dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright (necesario para la versión pesada)
RUN playwright install chromium
RUN playwright install-deps

# Copiar todo el código (incluyendo la carpeta amazon)
COPY . .

# Si quieres copiar solo lo necesario (recomendado para evitar archivos innecesarios):
# COPY amazon_cookie_gen.py .
# COPY amazon ./amazon

# Exponer el puerto que usa tu API (8080 en tu configuración)
EXPOSE 8080

# Comando de inicio (puedes cambiarlo a gunicorn si quieres)
CMD ["python", "amazon_cookie_gen.py"]FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

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

# Copiar requirements.txt primero para aprovechar caché
COPY requirements.txt .

# Instalar TODAS las dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright (necesario para la versión pesada)
RUN playwright install chromium
RUN playwright install-deps

# Copiar todo el código (incluyendo la carpeta amazon)
COPY . .

# Si quieres copiar solo lo necesario (recomendado para evitar archivos innecesarios):
# COPY amazon_cookie_gen.py .
# COPY amazon ./amazon

# Exponer el puerto que usa tu API (8080 en tu configuración)
EXPOSE 8080

# Comando de inicio (puedes cambiarlo a gunicorn si quieres)
CMD ["python", "amazon_cookie_gen.py"]