FROM mcr.microsoft.com/playwright/python:v1.48.0-focal

WORKDIR /app

# Instalar dependencias básicas primero
RUN pip install --no-cache-dir requests>=2.28.0 beautifulsoup4>=4.11.0 playwright>=1.35.0

# Luego las de captcha
RUN pip install --no-cache-dir twocaptcha>=1.3.0 anticaptchaofficial>=1.0.5

# Luego las demás
RUN pip install --no-cache-dir nest_asyncio>=1.5.0

# Finalmente las opcionales (si realmente las necesitas)
RUN pip install --no-cache-dir python-telegram-bot>=20.0 fastapi>=0.104.0 uvicorn[standard]>=0.24.0 || echo "Opcionales fallaron pero continuamos"

COPY amazon_cookie_gen.py .

ENTRYPOINT ["python", "amazon_cookie_gen.py"]