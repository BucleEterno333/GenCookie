# Etapa 1: Construir Node.js (si usas frontend)
FROM node:18-bullseye AS node-builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

# Etapa 2: Imagen final con Python 3.11 + Node
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para Playwright y compilaciones
RUN apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgbm1 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libx11-xcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        xdg-utils \
        libxkbcommon0 \
        libxshmfence1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalar Node.js (necesario si el proyecto usa Node para algo)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean

# Copiar node_modules del builder (si aplica)
COPY --from=node-builder /app/node_modules /app/node_modules

WORKDIR /app

# Copiar requirements primero para aprovechar caché
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalar navegadores de Playwright
RUN playwright install chromium && \
    playwright install-deps

# Copiar el resto del código
COPY . .

# Comando de inicio (ajusta según tu proyecto)
CMD ["python", "main.py"]