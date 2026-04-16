# Imagen oficial de Playwright para Python (Chromium + dependencias del sistema)
FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# Copiar el archivo de dependencias
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar el navegador Chromium (la imagen base ya lo tiene, pero por si acaso)
RUN playwright install chromium

# Copiar el código de la aplicación
COPY app.py .

# Exponer el puerto de Flask
EXPOSE 8080

# Comando de inicio
CMD ["python", "app.py"]