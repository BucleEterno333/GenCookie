FROM mcr.microsoft.com/playwright/python:v1.35.0-focal

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY amazon_cookie_gen.py .

ENTRYPOINT ["python", "amazon_cookie_gen.py"]