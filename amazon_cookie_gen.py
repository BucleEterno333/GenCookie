#!/usr/bin/env python3
"""
Amazon Cookie Generator - Versión API REST con navegación dinámica
- Parte desde la URL base del país
- Navega haciendo clic en elementos: "Hola, identifícate" 
- Incluye registro, verificación de correo, captcha, agregar dirección y wallet
- Logs detallados en cada paso (visibles en Northflank y en consola)
- Capturas de pantalla en base64 para el frontend
- Soporte para captchas de selección de imágenes (coordenadas) con 2Captcha y Anti-Captcha
- Reintentos automáticos con cambio de IP (proxy rotativo) ante cualquier error
"""

import os
import re
import json
import time
import random
import uuid
import asyncio
import logging
import argparse
import base64
import sys
from urllib.parse import urljoin, urlencode
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify
from flask_cors import CORS

# -------------------------------------------------------------------
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO
# -------------------------------------------------------------------
CAPTCHA_PROVIDER = os.getenv('CAPTCHA_PROVIDER', '2captcha')
API_KEY_2CAPTCHA = os.getenv('API_KEY_2CAPTCHA', '')
API_KEY_ANTICAPTCHA = os.getenv('API_KEY_ANTICAPTCHA', '')
PROXY_STRING = os.getenv('PROXY_STRING', '')
HERO_SMS_API_KEY = os.getenv('HERO_SMS_API_KEY', '')
HERO_SMS_COUNTRY = os.getenv('HERO_SMS_COUNTRY', 'us')
HERO_SMS_OPERATOR = os.getenv('HERO_SMS_OPERATOR', 'any')
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8080'))
API_KEY = os.getenv('API_KEY', '')
FIVESIM_API_KEY = os.getenv('FIVESIM_API_KEY', '')


# Proxy
PROXY_AUTH = None
PROXY_HOST_PORT = None
if PROXY_STRING:
    if '@' in PROXY_STRING:
        PROXY_AUTH, PROXY_HOST_PORT = PROXY_STRING.split('@', 1)
    else:
        PROXY_HOST_PORT = PROXY_STRING

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'
]

# -------------------------------------------------------------------
# MAPA DE PAÍSES A DOMINIOS Y URLS BASE
# -------------------------------------------------------------------
base_urls = {
    'CA': 'https://www.amazon.ca',
    'MX': 'https://www.amazon.com.mx',
    'US': 'https://www.amazon.com',
    'UK': 'https://www.amazon.co.uk',
    'DE': 'https://www.amazon.de',
    'FR': 'https://www.amazon.fr',
    'IT': 'https://www.amazon.it',
    'ES': 'https://www.amazon.es',
    'JP': 'https://www.amazon.co.jp',
    'AU': 'https://www.amazon.com.au',
    'IN': 'https://www.amazon.in'
}

address_book_urls = {
    'CA': "https://www.amazon.ca/a/addresses?ref_=ya_d_c_addr",
    'MX': "https://www.amazon.com.mx/a/addresses?ref_=ya_d_c_addr",
    'US': "https://www.amazon.com/a/addresses?ref_=ya_d_c_addr",
    'UK': "https://www.amazon.co.uk/a/addresses?ref_=ya_d_c_addr",
    'DE': "https://www.amazon.de/a/addresses?ref_=ya_d_c_addr",
    'FR': "https://www.amazon.fr/a/addresses?ref_=ya_d_c_addr",
    'IT': "https://www.amazon.it/a/addresses?ref_=ya_d_c_addr",
    'ES': "https://www.amazon.es/a/addresses?ref_=ya_d_c_addr",
    'JP': "https://www.amazon.co.jp/a/addresses?ref_=ya_d_c_addr",
    'AU': "https://www.amazon.com.au/a/addresses?ref_=ya_d_c_addr",
    'IN': "https://www.amazon.in/a/addresses?ref_=ya_d_c_addr"
}

add_address_urls = {
    'CA': "https://www.amazon.ca/a/addresses/add?ref=ya_address_book_add_button",
    'MX': "https://www.amazon.com.mx/a/addresses/add?ref=ya_address_book_add_button",
    'US': "https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button",
    'UK': "https://www.amazon.co.uk/a/addresses/add?ref=ya_address_book_add_button",
    'DE': "https://www.amazon.de/a/addresses/add?ref=ya_address_book_add_button",
    'FR': "https://www.amazon.fr/a/addresses/add?ref=ya_address_book_add_button",
    'IT': "https://www.amazon.it/a/addresses/add?ref=ya_address_book_add_button",
    'ES': "https://www.amazon.es/a/addresses/add?ref=ya_address_book_add_button",
    'JP': "https://www.amazon.co.jp/a/addresses/add?ref=ya_address_book_add_button",
    'AU': "https://www.amazon.com.au/a/addresses/add?ref=ya_address_book_add_button",
    'IN': "https://www.amazon.in/a/addresses/add?ref=ya_address_book_add_button"
}

wallet_urls = {
    'CA': "https://www.amazon.ca/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'MX': "https://www.amazon.com.mx/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'US': "https://www.amazon.com/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'UK': "https://www.amazon.co.uk/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'DE': "https://www.amazon.de/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'FR': "https://www.amazon.fr/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'IT': "https://www.amazon.it/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'ES': "https://www.amazon.es/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'JP': "https://www.amazon.co.jp/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'AU': "https://www.amazon.com.au/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'IN': "https://www.amazon.in/cpe/yourpayments/wallet?ref_=ya_mb_mpo"
}

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amazon_cookie_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES
# -------------------------------------------------------------------
def test_proxy(session, max_retries=3):
    """Prueba la conectividad del proxy y retorna la IP pública, con reintentos."""
    for attempt in range(max_retries):
        try:
            response = session.get('https://api.ipify.org?format=json', timeout=15)
            if response.status_code != 200:
                logger.warning(f"   Intento {attempt+1}: status code {response.status_code}")
                if attempt == max_retries - 1:
                    return False, f"Status code {response.status_code}"
            else:
                data = response.json()
                return True, data['ip']
        except requests.exceptions.SSLError as e:
            logger.warning(f"   Intento {attempt+1}: SSL Error: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"   Intento {attempt+1}: Connection Error: {e}")
        except Exception as e:
            logger.warning(f"   Intento {attempt+1}: Error: {e}")
        time.sleep(2)  # espera antes de reintentar
    return False, "Max retries exceeded"

def get_str(string, start, end, occurrence=1):
    """Extrae texto entre dos cadenas."""
    try:
        pattern = f'{re.escape(start)}(.*?){re.escape(end)}'
        matches = re.finditer(pattern, string)
        for i, match in enumerate(matches, 1):
            if i == occurrence:
                return match.group(1)
        return None
    except Exception:
        return None

# -------------------------------------------------------------------
# CAPTCHA RESOLUTION (coordenadas)
# -------------------------------------------------------------------
def solve_coordinates_captcha(image_path, hint_text=None):
    """
    Resuelve un captcha de selección de imágenes (coordenadas) usando 2captcha o anticaptcha.
    Retorna una lista de puntos [{'x': int, 'y': int}] o None si falla.
    """
    solution = None
    logger.debug(f"🔍 Intentando resolver captcha de coordenadas con imagen: {image_path}")

    # Intentar con 2captcha
    if API_KEY_2CAPTCHA:
        try:
            from twocaptcha import TwoCaptcha
            solver = TwoCaptcha(API_KEY_2CAPTCHA)
            # El método coordinates recibe la ruta de la imagen
            result = solver.coordinates(image_path, textinstructions=hint_text)
            if result and 'code' in result:
                coord_str = result['code']
                if coord_str.startswith('coordinates='):
                    coord_str = coord_str.replace('coordinates=', '')
                points = []
                for pair in coord_str.split(';'):
                    if pair:
                        x, y = pair.split(',')
                        points.append({'x': int(x), 'y': int(y)})
                logger.debug(f"✅ 2captcha resolvió coordenadas: {points}")
                return points
            else:
                logger.warning("⚠️ 2captcha no devolvió coordenadas")
        except Exception as e:
            logger.warning(f"⚠️ 2captcha falló: {e}")

    # Intentar con anticaptcha
    if not solution and API_KEY_ANTICAPTCHA:
        try:
            from anticaptchaofficial.imagecoordinates import imagecoordinates
            solver = imagecoordinates()
            solver.set_api_key(API_KEY_ANTICAPTCHA)
            solver.set_comment(hint_text or "Click on all images that match the description")
            solver.set_image_path(image_path)
            coordinates = solver.solve_and_return_solution()
            if coordinates:
                logger.debug(f"✅ anticaptcha resolvió coordenadas: {coordinates}")
                return coordinates
            else:
                logger.warning("⚠️ anticaptcha no devolvió coordenadas")
        except Exception as e:
            logger.warning(f"⚠️ anticaptcha falló: {e}")

    logger.error("❌ No se pudo resolver captcha de coordenadas")
    return None

# -------------------------------------------------------------------
# CAPTCHA RESOLUTION (reCAPTCHA e imagen simple)
# -------------------------------------------------------------------
def solve_captcha(site_key, page_url, is_image_captcha=False, image_path=None):
    """Resuelve captcha usando 2captcha o anticaptcha."""
    solution = None
    logger.debug(f"🔍 Intentando resolver captcha: site_key={site_key}, url={page_url}, is_image={is_image_captcha}")

    if API_KEY_2CAPTCHA and (CAPTCHA_PROVIDER == '2captcha' or not solution):
        try:
            from twocaptcha import TwoCaptcha
            solver = TwoCaptcha(API_KEY_2CAPTCHA)
            if is_image_captcha and image_path:
                result = solver.normal(image_path)
                solution = result['code']
                logger.debug(f"✅ 2captcha resolvió imagen: {solution[:10]}...")
            else:
                result = solver.recaptcha(sitekey=site_key, url=page_url)
                solution = result['code']
                logger.debug(f"✅ 2captcha resolvió recaptcha: {solution[:10]}...")
        except Exception as e:
            logger.warning(f"⚠️ 2captcha falló: {e}")

    if not solution and API_KEY_ANTICAPTCHA:
        try:
            from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
            from anticaptchaofficial.imagecaptcha import imagecaptcha
            if is_image_captcha and image_path:
                solver = imagecaptcha()
                solver.set_api_key(API_KEY_ANTICAPTCHA)
                solution = solver.solve_and_return_solution(image_path)
                logger.debug(f"✅ anticaptcha resolvió imagen: {solution[:10]}...")
            else:
                solver = recaptchaV2Proxyless()
                solver.set_api_key(API_KEY_ANTICAPTCHA)
                solver.set_website_url(page_url)
                solver.set_website_key(site_key)
                solution = solver.solve_and_return_solution()
                logger.debug(f"✅ anticaptcha resolvió recaptcha: {solution[:10]}...")
        except Exception as e:
            logger.error(f"❌ anticaptcha falló: {e}")

    if not solution:
        logger.error("❌ No se obtuvo solución de captcha")
    return solution






















# -------------------------------------------------------------------
# 5SIM SMS (versión mejorada con manejo de errores)
# -------------------------------------------------------------------
FIVESIM_BASE_URL = "https://5sim.net/v1"

FIVESIM_COUNTRY_MAP = {
    'MX': 'mexico',
    'US': 'usa',
    'CA': 'canada',
    'UK': 'uk',
    'DE': 'germany',
    'FR': 'france',
    'IT': 'italy',
    'ES': 'spain',
    'JP': 'japan',
    'AU': 'australia',
    'IN': 'india',
}

async def get_fivesim_number(country_code, product='amazon'):
    """
    Compra un número de teléfono temporal en 5sim (usando GET).
    Retorna (phone_number, order_id) o None si falla.
    """
    if not FIVESIM_API_KEY:
        logger.warning("⚠️ No hay API key de 5sim")
        return None

    country = FIVESIM_COUNTRY_MAP.get(country_code)
    if not country:
        logger.error(f"❌ No hay mapeo de país 5sim para {country_code}")
        return None

    url = f"{FIVESIM_BASE_URL}/user/buy/activation/{country}/any/{product}"
    headers = {
        'Authorization': f'Bearer {FIVESIM_API_KEY}',
        'Accept': 'application/json'
    }
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, timeout=30))
        logger.debug(f"📡 5sim respuesta HTTP {response.status_code}")
        if response.status_code == 200:
            # Intentar parsear JSON
            try:
                data = response.json()
                phone = data.get('phone')
                order_id = data.get('id')
                if phone and order_id:
                    logger.debug(f"📱 Número 5sim comprado: {phone} (order_id: {order_id})")
                    return phone, order_id
                else:
                    logger.warning(f"⚠️ Respuesta inesperada de 5sim (faltan campos): {data}")
            except ValueError as e:
                logger.warning(f"⚠️ Respuesta no JSON de 5sim: {response.text[:200]}")
        else:
            logger.warning(f"⚠️ Error HTTP {response.status_code} de 5sim: {response.text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Error comprando número 5sim: {e}")
        return None

async def get_fivesim_code(order_id, timeout=180):
    """
    Espera y obtiene el código SMS de 5sim.
    Retorna el código como string o None si no se obtiene.
    """
    url = f"{FIVESIM_BASE_URL}/user/check/{order_id}"
    headers = {
        'Authorization': f'Bearer {FIVESIM_API_KEY}',
        'Accept': 'application/json'
    }
    start_time = time.time()
    loop = asyncio.get_running_loop()
    while time.time() - start_time < timeout:
        try:
            response = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, timeout=30))
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    logger.warning(f"⚠️ Respuesta no JSON de 5sim: {response.text[:200]}")
                    await asyncio.sleep(5)
                    continue
                status = data.get('status')
                if status == 'RECEIVED':
                    sms = data.get('sms', [])
                    if sms:
                        code = sms[0].get('code')
                        if not code:
                            text = sms[0].get('text', '')
                            import re
                            codes = re.findall(r'\b(\d{5,6})\b', text)
                            if codes:
                                code = codes[0]
                        if code:
                            logger.debug(f"📱 Código SMS recibido de 5sim: {code}")
                            return code
                elif status == 'PENDING':
                    pass
                else:
                    logger.warning(f"⚠️ Estado inesperado de 5sim: {status}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.debug(f"📱 Error esperando código: {e}")
            await asyncio.sleep(5)
    logger.error("❌ Tiempo de espera agotado para código SMS")
    return None






# -------------------------------------------------------------------
# CORREO TEMPORAL (MEJORADO CON MÚLTIPLES SERVICIOS)
# -------------------------------------------------------------------
async def generate_temp_email():
    """Genera una dirección de correo temporal usando múltiples servicios con reintentos."""
    services = [
        ('mail.tm', 'https://api.mail.tm'),
        ('guerrillamail', 'https://api.guerrillamail.com/ajax.php'),
        ('tempmail.plus', 'https://api.tempmail.plus/generate'),
        ('mailinator', 'https://api.mailinator.com/v2/domains/public'),
        ('10minutemail', 'https://10minutemail.net/api/1.1/')
    ]
    for service_name, api_url in services:
        for attempt in range(3):
            try:
                logger.debug(f"📧 Intentando {service_name} (intento {attempt+1}/3)...")
                if service_name == 'mail.tm':
                    # Obtener dominios
                    resp = requests.get(f"{api_url}/domains", timeout=30)
                    if resp.status_code != 200:
                        logger.warning(f"   mail.tm dominios respondió {resp.status_code}")
                        continue
                    data = resp.json()
                    domains_list = data.get('hydra:member', [])
                    if not domains_list or not domains_list[0].get('domain'):
                        logger.warning("   mail.tm no devolvió dominios")
                        continue
                    domain = domains_list[0]['domain']
                    email = f"{uuid.uuid4().hex[:8]}@{domain}"
                    password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
                    # Crear cuenta
                    acc_resp = requests.post(
                        f"{api_url}/accounts",
                        json={"address": email, "password": password},
                        timeout=30
                    )
                    if acc_resp.status_code == 201:
                        # Autenticarse para obtener el token
                        token_resp = requests.post(
                            f"{api_url}/token",
                            json={"address": email, "password": password},
                            timeout=30
                        )
                        if token_resp.status_code == 200:
                            token_data = token_resp.json()
                            token = token_data.get('token')
                            logger.debug(f"✅ mail.tm: {email}, token obtenido")
                            return email, token, service_name
                        else:
                            logger.warning(f"   mail.tm autenticación falló: {token_resp.status_code}")
                    else:
                        logger.warning(f"   mail.tm creación falló: {acc_resp.status_code}")

                elif service_name == 'guerrillamail':
                    resp = requests.get(
                        f"{api_url}?f=get_email_address&ip=127.0.0.1",
                        timeout=30
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        email = data.get('email_addr')
                        token = data.get('sid_token')
                        if email and token:
                            logger.debug(f"✅ guerrillamail: {email}")
                            return email, token, service_name
                    else:
                        logger.warning(f"   guerrillamail respondió {resp.status_code}")

                elif service_name == 'tempmail.plus':
                    resp = requests.get(api_url, timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        email = data.get('email')
                        token = data.get('token')
                        if email and token:
                            logger.debug(f"✅ tempmail.plus: {email}")
                            return email, token, service_name
                    else:
                        logger.warning(f"   tempmail.plus respondió {resp.status_code}")

                elif service_name == 'mailinator':
                    domain = 'mailinator.com'
                    email = f"{uuid.uuid4().hex[:8]}@{domain}"
                    logger.debug(f"✅ mailinator: {email} (sin token)")
                    return email, None, service_name

                elif service_name == '10minutemail':
                    resp = requests.get(f"{api_url}new", timeout=30)
                    if resp.status_code == 200:
                        data = resp.json()
                        email = data.get('email')
                        token = data.get('token')
                        if email:
                            logger.debug(f"✅ 10minutemail: {email}")
                            return email, token, service_name
                    else:
                        logger.warning(f"   10minutemail respondió {resp.status_code}")

            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Timeout en {service_name}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"⚠️ Error de conexión en {service_name}: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Error inesperado en {service_name}: {e}")
            await asyncio.sleep(2)
    logger.error("❌ Todos los servicios de correo fallaron")
    return None, None, None

async def get_verification_code(email, token, service, max_attempts=20, wait_time=10):
    """
    Obtiene el código de verificación del correo temporal.
    Busca cualquier número de 5 o 6 dígitos en el texto del mensaje.
    """
    logger.debug(f"📧 Esperando código de verificación para {email} (servicio: {service})...")
    
    for attempt in range(max_attempts):
        try:
            if service == 'mail.tm' and token:
                resp = requests.get(
                    "https://api.mail.tm/messages",
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=30
                )
                if resp.status_code == 200:
                    data = resp.json()
                    messages = data.get('hydra:member', [])
                    for msg in messages:
                        # Obtener el texto del mensaje (puede estar en varios campos)
                        text = msg.get('text', '') or msg.get('html', '') or msg.get('intro', '')
                        # Buscar cualquier número de 5 o 6 dígitos
                        import re
                        codes = re.findall(r'\b(\d{5,6})\b', text)
                        if codes:
                            code = codes[0]
                            logger.debug(f"📧 Código obtenido de mail.tm: {code}")
                            return code
            # Aquí puedes agregar otros servicios (guerrillamail, etc.) con la misma lógica
        except Exception as e:
            logger.debug(f"📧 Intento {attempt+1} falló: {e}")
        
        await asyncio.sleep(wait_time)
    
    logger.error("❌ No se pudo obtener código de verificación después de múltiples intentos")
    return None

# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA CAPTURAR PANTALLA
# -------------------------------------------------------------------
async def take_screenshot(page, step_name):
    try:
        screenshot_bytes = await page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        logger.debug(f"📸 Screenshot tomado en paso: {step_name}")
        return screenshot_b64
    except Exception as e:
        logger.warning(f"⚠️ Error tomando screenshot en paso {step_name}: {e}")
        return None

# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA OBTENER CONTENIDO DE FORMA SEGURA
# -------------------------------------------------------------------
async def safe_get_content(page, timeout=20):
    try:
        await page.wait_for_function('document.readyState === "complete"', timeout=timeout*1000)
        await page.wait_for_timeout(500)
        return await page.content()
    except Exception as e:
        logger.warning(f"⚠️ Error en safe_get_content: {e}")
        await page.wait_for_timeout(2000)
        return await page.content()

# -------------------------------------------------------------------
# FUNCIÓN PARA AGREGAR DIRECCIÓN
# -------------------------------------------------------------------
async def add_address(session, country_code, email, password, token=None, service=None):
    """Agrega una dirección por defecto a la cuenta."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{base_urls[country_code]}/gp/your-account?ref_=nav_AccountFlyout_ya",
        "Viewport-Width": "1536"
    }

    resp = session.get(address_book_urls[country_code], headers=headers, timeout=15, allow_redirects=True)
    if resp.status_code != 200:
        logger.warning("⚠️ No se pudo acceder a address book")
        return False

    if 'signin' in resp.url.lower():
        logger.debug("🔑 Sesión expirada, intentando reautenticar... (no implementado, se asume éxito)")
        # Aquí podrías implementar login_again si es necesario

    resp = session.get(add_address_urls[country_code], headers=headers, timeout=15, allow_redirects=True)
    if resp.status_code != 200:
        logger.warning("⚠️ No se pudo acceder a add address")
        return False

    soup = BeautifulSoup(resp.text, 'html.parser')
    form = soup.find('form', {'id': 'address-ui-widgets-form'}) or soup.find('form', {'action': re.compile('add', re.I)})
    if not form:
        logger.warning("⚠️ No se encontró formulario de dirección")
        return False

    address_data = {
        'CA': {'countryCode': 'CA', 'fullName': 'Mark O. Montanez', 'phone': f'1{random.randint(1000000000,9999999999)}',
               'line1': '456 Bloor Street West', 'city': 'Toronto', 'state': 'ON', 'postalCode': 'M5S 1X8'},
        'MX': {'countryCode': 'US', 'fullName': 'John Doe', 'phone': f'1{random.randint(1000000000,9999999999)}',
               'line1': '123 Main Street', 'city': 'New York', 'state': 'NY', 'postalCode': '10001'},
        'US': {'countryCode': 'US', 'fullName': 'John Doe', 'phone': f'1{random.randint(1000000000,9999999999)}',
               'line1': '123 Main Street', 'city': 'New York', 'state': 'NY', 'postalCode': '10001'},
        'UK': {'countryCode': 'GB', 'fullName': 'James Smith', 'phone': f'44{random.randint(1000000000,9999999999)}',
               'line1': '123 Oxford Street', 'city': 'London', 'state': '', 'postalCode': 'W1D 1AA'},
        'DE': {'countryCode': 'DE', 'fullName': 'Hans Müller', 'phone': f'49{random.randint(1000000000,9999999999)}',
               'line1': 'Hauptstraße 12', 'city': 'Berlin', 'state': '', 'postalCode': '10115'},
        'FR': {'countryCode': 'FR', 'fullName': 'Pierre Dubois', 'phone': f'33{random.randint(1000000000,9999999999)}',
               'line1': '12 Rue de Rivoli', 'city': 'Paris', 'state': '', 'postalCode': '75001'},
        'IT': {'countryCode': 'IT', 'fullName': 'Giuseppe Rossi', 'phone': f'39{random.randint(1000000000,9999999999)}',
               'line1': 'Via Roma 10', 'city': 'Roma', 'state': '', 'postalCode': '00184'},
        'ES': {'countryCode': 'ES', 'fullName': 'Carlos García', 'phone': f'34{random.randint(1000000000,9999999999)}',
               'line1': 'Calle Mayor 15', 'city': 'Madrid', 'state': '', 'postalCode': '28013'},
        'JP': {'countryCode': 'JP', 'fullName': 'Taro Yamada', 'phone': f'81{random.randint(1000000000,9999999999)}',
               'line1': '1-2-3 Shibuya', 'city': 'Tokyo', 'state': '', 'postalCode': '150-0002'},
        'AU': {'countryCode': 'AU', 'fullName': 'Emma Wilson', 'phone': f'61{random.randint(1000000000,9999999999)}',
               'line1': '123 George Street', 'city': 'Sydney', 'state': 'NSW', 'postalCode': '2000'},
        'IN': {'countryCode': 'IN', 'fullName': 'Amit Sharma', 'phone': f'91{random.randint(1000000000,9999999999)}',
               'line1': '123 MG Road', 'city': 'Mumbai', 'state': 'Maharashtra', 'postalCode': '400001'}
    }

    country_data = address_data[country_code]

    post_data = {}
    for inp in form.find_all('input', type='hidden'):
        if inp.get('name'):
            post_data[inp['name']] = inp.get('value', '')

    post_data.update({
        "address-ui-widgets-countryCode": country_data['countryCode'],
        "address-ui-widgets-enterAddressFullName": country_data['fullName'],
        "address-ui-widgets-enterAddressPhoneNumber": country_data['phone'],
        "address-ui-widgets-enterAddressLine1": country_data['line1'],
        "address-ui-widgets-enterAddressLine2": "",
        "address-ui-widgets-enterAddressCity": country_data['city'],
        "address-ui-widgets-enterAddressStateOrRegion": country_data['state'],
        "address-ui-widgets-enterAddressPostalCode": country_data['postalCode'],
        "address-ui-widgets-use-as-my-default": "true",
        "address-ui-widgets-addressFormButtonText": "save"
    })

    post_url = urljoin(base_urls[country_code], form.get('action') or "/a/addresses/add")
    headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": base_urls[country_code],
        "Referer": add_address_urls[country_code]
    })

    resp = session.post(
        post_url,
        data=urlencode(post_data),
        headers=headers,
        timeout=15,
        allow_redirects=True
    )

    if resp.status_code == 200:
        logger.debug("✅ Dirección agregada exitosamente")
        return True
    else:
        logger.warning(f"⚠️ Error al agregar dirección: {resp.status_code}")
        return False











































async def create_amazon_account(country_code, email=None, token=None, service=None, add_address_flag=True):
    # NOTA: email, token, service se ignoran; usamos número de teléfono.
    logger.debug(f"🏁 [ENTRADA] create_amazon_account para país {country_code} (vía número de teléfono)")

    max_global_retries = 3
    for global_attempt in range(1, max_global_retries + 1):
        logger.debug(f"🔄 Intento global {global_attempt}/{max_global_retries}")
        playwright = None
        browser = None
        context = None
        page = None
        session = None
        last_screenshot = None

        account_data = {
            'email': None,          # No se usará
            'password': None,
            'name': None,
            'phone': None,
            'address': None,
            'cookie_string': None,
            'cookie_dict': None,
            'country': country_code,
            'timestamp': time.time()
        }

        try:
            # ----- PASO 1: Configurar sesión y proxy -----
            logger.debug("📦 [PASO 1] Configurando sesión requests...")
            session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            if PROXY_HOST_PORT:
                proxy_url = f"http://{PROXY_HOST_PORT}"
                if PROXY_AUTH:
                    proxy_url = f"http://{PROXY_AUTH}@{PROXY_HOST_PORT}"
                session.proxies = {'http': proxy_url, 'https': proxy_url}
                logger.debug(f"   ✅ Proxy configurado: {PROXY_HOST_PORT}")
            else:
                logger.warning("   ⚠️ No se configuró proxy")

            # ----- PASO 2: Probar proxy -----
            logger.debug("🔄 [PASO 2] Probando proxy...")
            ok, ip = test_proxy(session)
            if not ok:
                logger.error(f"   ❌ Proxy no funciona: {ip}")
                raise Exception(f"Proxy error: {ip}")
            logger.debug(f"   ✅ Proxy OK - IP pública: {ip}")

            # ----- PASO 3: Obtener número de teléfono temporal -----
            logger.debug("📱 [PASO 3] Obteniendo número de teléfono temporal...")
            phone_number = None
            order_id = None

            # Intentar con 5sim
            if FIVESIM_API_KEY:
                sms_info = await get_fivesim_number(country_code, product='amazon')
                if sms_info:
                    full_phone, order_id = sms_info
                    logger.debug(f"   ✅ Número 5sim obtenido: {full_phone} (order_id: {order_id})")
                    # Quitar código de país
                    country_prefix_length = {
                        'MX': 3, 'US': 2, 'CA': 2, 'UK': 3, 'DE': 3,
                        'FR': 3, 'IT': 3, 'ES': 3, 'JP': 3, 'AU': 3, 'IN': 3,
                    }
                    prefix_len = country_prefix_length.get(country_code, 0)
                    if prefix_len and len(full_phone) > prefix_len:
                        phone_number = full_phone[prefix_len:]
                        phone_number = re.sub(r'\D', '', phone_number)
                        logger.debug(f"   ✅ Número local (sin código): {phone_number}")
                    else:
                        phone_number = full_phone
                        logger.warning(f"   ⚠️ No se pudo quitar código de país, se usará completo: {phone_number}")
                else:
                    logger.warning("   ⚠️ 5sim falló, intentando con HeroSMS...")
                    # Aquí podrías llamar a get_hero_sms_number si está implementada
                    if HERO_SMS_API_KEY:
                        # Implementar get_hero_sms_number similar
                        logger.error("❌ HeroSMS no implementado en este ejemplo")
                        raise Exception("No se pudo obtener número de teléfono")
                    else:
                        logger.error("❌ No hay API de 5sim ni HeroSMS configurada")
                        raise Exception("No se pudo obtener número de teléfono")
            else:
                logger.error("❌ No hay API key de 5sim configurada")
                raise Exception("Se requiere número de teléfono pero no hay API de SMS")

            account_data['phone'] = phone_number

            # ----- PASO 4: Generar credenciales (nombre y contraseña) -----
            logger.debug("🔑 [PASO 4] Generando credenciales...")
            password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
            first_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            last_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            fullname = f"{first_name} {last_name}"
            account_data['password'] = password
            account_data['name'] = fullname
            logger.debug(f"   👤 Nombre: {fullname}")
            logger.debug(f"   🔐 Contraseña: {password}")

            # ----- PASO 5: Iniciar Playwright -----
            logger.debug("🎬 [PASO 5] Iniciando Playwright...")
            try:
                playwright = await async_playwright().start()
                logger.debug("   ✅ Playwright iniciado")
            except Exception as e:
                logger.error(f"   ❌ Error iniciando Playwright: {e}")
                raise Exception(f"Error iniciando Playwright: {e}")

            launch_options = {
                'headless': True,
                'args': [
                    '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas', '--no-first-run', '--no-zygote',
                    '--disable-gpu',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-automation',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-features=BlockInsecurePrivateNetworkRequests',
                    '--disable-sync',
                    '--disable-default-apps',
                    '--disable-extensions',
                    '--disable-component-extensions-with-background-pages',
                    '--disable-client-side-phishing-detection',
                    '--disable-crash-reporter',
                    '--disable-ipc-flooding-protection',
                    '--disable-prompt-on-repost',
                    '--disable-renderer-backgrounding',
                    '--force-color-profile=srgb',
                    '--metrics-recording-only',
                    '--password-store=basic',
                    '--use-mock-keychain',
                    '--hide-scrollbars',
                    '--mute-audio',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-breakpad',
                    '--disable-component-update',
                    '--disable-domain-reliability',
                    '--disable-print-preview',
                    '--disable-ntp-popular-sites',
                    '--disable-top-sites',
                    '--disable-voice-input',
                    '--enable-automation=0',
                    '--enable-blink-features=IdleDetection',
                    '--disable-notifications',
                    '--disable-permissions-api',
                    '--disable-speech-api',
                    '--disable-background-net',
                    '--disable-features=ChromeWhatsNewUI',
                    '--disable-features=TranslateUI',
                    '--disable-features=OptimizationHints',
                    '--disable-features=MediaRouter',
                    '--disable-features=DialMediaRouteProvider',
                    '--disable-features=PasswordImport',
                    '--disable-features=ImprovedCookieControls',
                    '--disable-features=LazyFrameLoading',
                    '--disable-features=LazyImageLoading',
                    '--disable-features=AutofillServerCommunication',
                    '--disable-features=AutofillEnableCompanyName',
                    '--disable-features=InterestFeedContentSuggestions',
                    '--disable-features=WebRtcHideLocalIpsWithMdns',
                    '--disable-features=WebRtcAllowInputVolumeAdjustment',
                    '--disable-features=WebRtcUseEchoCanceller3',
                    '--disable-features=WebRtcAllowWgcScreenCapturer',
                    '--disable-features=WebRtcStunOrigin',
                    '--disable-features=WebRtcUseMinMaxVEABitrate',
                    '--disable-features=WebRtcAllowWgcScreenCapturer',
                    '--disable-features=WebRtcEnableFrameDropper',
                    '--disable-features=WebRtcEnableFrameRateDecoupling',
                    '--disable-features=WebRtcEnableRtcEventLog',
                    '--disable-features=WebRtcEnableTimeLimitedFreeze',
                    '--disable-features=WebRtcEnableVp9kSvc',
                    '--disable-features=WebRtcH264WithH264',
                    '--disable-features=WebRtcH265WithH265',
                    '--disable-features=WebRtcVp8WithVp8',
                    '--disable-features=WebRtcVp9WithVp9',
                    '--disable-features=WebRtcAv1WithAv1'
                ]
            }
            if PROXY_HOST_PORT:
                proxy_dict = {'server': f'http://{PROXY_HOST_PORT}'}
                if PROXY_AUTH:
                    user, pwd = PROXY_AUTH.split(':', 1)
                    proxy_dict['username'] = user
                    proxy_dict['password'] = pwd
                launch_options['proxy'] = proxy_dict
                logger.debug(f"   🌐 Proxy Playwright: {PROXY_HOST_PORT}")

            # ----- PASO 6: Lanzar browser -----
            logger.debug("🚀 [PASO 6] Lanzando browser...")
            try:
                browser = await playwright.chromium.launch(**launch_options)
                logger.debug("   ✅ Browser lanzado")
            except Exception as e:
                logger.error(f"   ❌ Error lanzando browser: {e}")
                raise Exception(f"Error lanzando browser: {e}")

            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=random.choice(USER_AGENTS),
                locale='es-MX' if country_code == 'MX' else 'en-US',
                timezone_id='America/Mexico_City' if country_code == 'MX' else 'America/New_York'
            )

            # Inyectar script anti-detección
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['es-ES', 'es', 'en']});
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 1});
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)

            page = await context.new_page()
            logger.debug("   ✅ Contexto y página creados con evasión")

            # ----- PASO 7: Navegar a la URL base del país (con reintentos) -----
            base_url = base_urls[country_code]
            logger.debug(f"🌐 [PASO 7] Navegando a URL base: {base_url}")

            page_loaded = False
            for attempt in range(3):
                try:
                    await page.goto(base_url, wait_until='domcontentloaded', timeout=120000)
                    await page.wait_for_timeout(5000)
                    body = await page.query_selector('body')
                    if body:
                        logger.debug(f"   ✅ Página cargada en intento {attempt+1}")
                        page_loaded = True
                        break
                    else:
                        logger.warning(f"   ⚠️ Intento {attempt+1}: no se detectó body")
                except Exception as e:
                    logger.warning(f"   ⚠️ Intento {attempt+1} falló: {e}")
                    if attempt == 2:
                        raise
                    await asyncio.sleep(5)

            if not page_loaded:
                raise Exception("No se pudo cargar la página de Amazon después de reintentos")

            await page.wait_for_timeout(3000)
            last_screenshot = await take_screenshot(page, "home_page")
            logger.debug(f"   📍 URL actual: {page.url}")

            # ----- PASO 8: Hacer clic en "Hola, identifícate" -----
            logger.debug("👤 [PASO 8] Buscando enlace de inicio de sesión...")
            login_selectors = [
                'a[data-nav-role="signin"]',
                'a.nav-a[data-nav-role="signin"]',
                'a[data-csa-c-slot-id="nav-link-accountList"]',
                'a:has-text("Hola, identifícate")',
                'a:has-text("Hello, Sign in")',
                'a:has-text("Identifícate")'
            ]
            login_link = None
            for selector in login_selectors:
                try:
                    link = await page.wait_for_selector(selector, state='visible', timeout=5000)
                    if link:
                        login_link = link
                        logger.debug(f"   ✅ Enlace de login encontrado con selector: {selector}")
                        break
                except:
                    continue
            if not login_link:
                raise Exception("No se encontró enlace de inicio de sesión")

            await login_link.click()
            await page.wait_for_load_state('networkidle', timeout=20000)
            await page.wait_for_timeout(2000)
            logger.debug(f"   📍 URL después de login: {page.url}")
            last_screenshot = await take_screenshot(page, "after_login_click")

            # ----- PASO 9: Ingresar número de teléfono en primera página -----
            logger.debug("📱 [PASO 9] Ingresando número de teléfono...")
            phone_field = None
            phone_selectors = ['input#ap_email', 'input[name="email"]', 'input[type="email"]', 'input[type="tel"]']
            for selector in phone_selectors:
                field = await page.query_selector(selector)
                if field and await field.is_visible():
                    phone_field = field
                    logger.debug(f"   ✅ Campo encontrado con selector: {selector}")
                    break
            if not phone_field:
                raise Exception("No se encontró campo para ingresar número de teléfono")

            await phone_field.fill(phone_number)
            logger.debug(f"   ✅ Número ingresado: {phone_number}")
            last_screenshot = await take_screenshot(page, "phone_llenado")

            # ----- PASO 10: Hacer clic en Continuar -----
            logger.debug("🖱️ [PASO 10] Haciendo clic en Continuar...")
            continue_button = None
            continue_selectors = ['input#continue', 'input.a-button-input', 'button#continue']
            for selector in continue_selectors:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    continue_button = btn
                    logger.debug(f"   ✅ Botón Continuar encontrado con selector: {selector}")
                    break
            if not continue_button:
                raise Exception("No se encontró botón Continuar")

            await continue_button.click()
            await page.wait_for_load_state('networkidle', timeout=15000)
            await page.wait_for_timeout(2000)
            logger.debug(f"   📍 Nueva URL: {page.url}")
            last_screenshot = await take_screenshot(page, "despues_continuar")

            # ----- PASO 11: Página intermedia "Proceder a crear una cuenta" -----
            logger.debug("🔍 [PASO 11] Verificando página intermedia...")
            proceed_selectors = [
                'span#intention-submit-button input.a-button-input',
                'input[value="Proceder a crear una cuenta"]',
                'button:has-text("Proceder a crear una cuenta")',
                'input[value*="Create account"]',
                'button:has-text("Create account")'
            ]
            proceed_button = None
            for selector in proceed_selectors:
                try:
                    btn = await page.wait_for_selector(selector, state='visible', timeout=4000)
                    if btn:
                        proceed_button = btn
                        logger.debug(f"   ✅ Botón 'Proceder' encontrado con selector: {selector}")
                        break
                except:
                    continue

            if proceed_button:
                logger.debug("   🔘 Haciendo clic en 'Proceder'...")
                await proceed_button.click()
                try:
                    await page.wait_for_selector('#ap_customer_name', state='visible', timeout=30000)
                    logger.debug("   ✅ Campo de nombre visible, formulario cargado")
                except Exception as e:
                    content = await safe_get_content(page)
                    if "JavaScript se ha deshabilitado" in content:
                        raise Exception("Error: JavaScript deshabilitado")
                    raise Exception(f"Timeout esperando campo de nombre: {e}")
                await page.wait_for_timeout(2000)
                last_screenshot = await take_screenshot(page, "despues_proceder")
            else:
                raise Exception("No se pudo acceder al formulario de registro después de Continuar")

            # ----- PASO 12: Llenar formulario de registro (nombre, contraseña) -----
            logger.debug("📝 [PASO 12] Llenando formulario completo...")
            last_screenshot = await take_screenshot(page, "formulario_antes_llenar")

            async def safe_fill(selector, value, desc):
                for attempt in range(3):
                    try:
                        field = await page.wait_for_selector(selector, state='visible', timeout=5000)
                        await field.fill(value)
                        logger.debug(f"   ✅ {desc} llenado con selector: {selector}")
                        return True
                    except Exception as e:
                        logger.debug(f"      ⚠️ Intento {attempt+1} falló: {str(e)[:50]}")
                        await page.wait_for_timeout(1000)
                return False

            # Nombre
            name_selectors = ['input#ap_customer_name', 'input[name="customerName"]']
            name_filled = False
            for sel in name_selectors:
                if await safe_fill(sel, fullname, "Nombre"):
                    name_filled = True
                    break
            if not name_filled:
                logger.warning("⚠️ No se pudo llenar campo de nombre, puede estar precargado")

            # Contraseña
            pwd_selectors = ['input#ap_password', 'input[name="password"]']
            pwd_filled = False
            for sel in pwd_selectors:
                if await safe_fill(sel, password, "Contraseña"):
                    pwd_filled = True
                    break
            if not pwd_filled:
                raise Exception("No se pudo llenar campo de contraseña")

            # Confirmación de contraseña
            confirm_selectors = ['input#ap_password_check', 'input[name="passwordCheck"]']
            for sel in confirm_selectors:
                if await safe_fill(sel, password, "Confirmación"):
                    break

            # ----- PASO 13: Botón de registro final -----
            logger.debug("🎯 [PASO 13] Buscando botón de registro final...")
            final_btn_selectors = [
                'input#continue', 'input.a-button-input', 'button[type="submit"]',
                'input[value*="Crear cuenta"]', 'button:has-text("Crear cuenta")',
                'input[value*="Create account"]', 'button:has-text("Create account")'
            ]
            clicked = False
            for sel in final_btn_selectors:
                try:
                    btn = await page.wait_for_selector(sel, state='visible', timeout=3000)
                    if btn:
                        await btn.click()
                        logger.debug(f"   ✅ Botón final clickeado con selector: {sel}")
                        clicked = True
                        break
                except:
                    continue
            if not clicked:
                logger.warning("⚠️ No se encontró botón de registro final, puede que ya se haya enviado")

            await page.wait_for_load_state('networkidle', timeout=30000)
            last_screenshot = await take_screenshot(page, "despues_registro")





            # ----- PASO 15: Detectar captcha después del envío -----
            logger.debug("🔍 [PASO 15] Verificando captcha después del envío...")
            await page.wait_for_timeout(5000)
            content = await safe_get_content(page)


            # Detectar captcha de selección de imágenes (tipo "elige las sillas")
            if "Resuelve esta adivinanza" in content or "Elija todo las sillas" in content or "Elija todo" in content:
                logger.warning("⚠️ Captcha de selección de imágenes detectado")
                # Esperar a que el canvas termine de cargar (puede tardar unos segundos)
                logger.debug("   ⏳ Esperando 4 segundos adicionales para que cargue el canvas...")
                await page.wait_for_timeout(4000)
                last_screenshot = await take_screenshot(page, "captcha_seleccion")

                # Buscar el canvas (es lo más común) o una imagen
                canvas_element = await page.query_selector('canvas')
                img_element = await page.query_selector('img[src*="captcha"]')
                
                if canvas_element:
                    logger.debug("   ✅ Captcha es un canvas, tomando screenshot del elemento")
                    screenshot_bytes = await canvas_element.screenshot()
                    img_path = 'temp_canvas_captcha.png'
                    with open(img_path, 'wb') as f:
                        f.write(screenshot_bytes)
                    logger.debug(f"   ✅ Canvas capturado, tamaño: {len(screenshot_bytes)} bytes")
                    click_element = canvas_element
                elif img_element:
                    logger.debug("   ✅ Captcha es una imagen, descargando...")
                    img_src = await img_element.get_attribute('src')
                    if not img_src:
                        return None, "La imagen del captcha no tiene src", last_screenshot
                    img_data = requests.get(img_src, timeout=10).content
                    img_path = 'temp_image_captcha.jpg'
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                    click_element = img_element
                else:
                    # Si aún no aparece, esperar un poco más y reintentar una vez
                    logger.warning("   ⚠️ No se encontró canvas ni imagen, esperando 2 segundos más...")
                    await page.wait_for_timeout(2000)
                    canvas_element = await page.query_selector('canvas')
                    img_element = await page.query_selector('img[src*="captcha"]')
                    if canvas_element:
                        logger.debug("   ✅ Captcha (canvas) apareció después de espera adicional")
                        screenshot_bytes = await canvas_element.screenshot()
                        img_path = 'temp_canvas_captcha.png'
                        with open(img_path, 'wb') as f:
                            f.write(screenshot_bytes)
                        click_element = canvas_element
                    elif img_element:
                        img_src = await img_element.get_attribute('src')
                        if not img_src:
                            return None, "La imagen del captcha no tiene src", last_screenshot
                        img_data = requests.get(img_src, timeout=10).content
                        img_path = 'temp_image_captcha.jpg'
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                        click_element = img_element
                    else:
                        logger.error("❌ No se encontró canvas ni imagen de captcha después de reintentar")
                        return None, "No se encontró elemento de captcha", last_screenshot

                # Extraer texto de instrucción (mejorado)
                hint_text = "Haz clic en todas las imágenes que correspondan"

                # --- Resolver coordenadas usando API HTTP directamente ---
                coordinates = None

                # Función para llamar a 2captcha API (versión robusta)
                def solve_2captcha_coordinates(image_path, hint):
                    import base64
                    with open(image_path, 'rb') as f:
                        img_base64 = base64.b64encode(f.read()).decode('utf-8')
                    url = "http://2captcha.com/in.php"
                    data = {
                        'key': API_KEY_2CAPTCHA,
                        'method': 'base64',
                        'body': img_base64,
                        'coordinatescaptcha': 1,
                        'textinstructions': hint,
                        'json': 1
                    }
                    try:
                        resp = requests.post(url, data=data, timeout=30)
                        if resp.status_code == 200:
                            result = resp.json()
                            if result.get('status') == 1:
                                captcha_id = result['request']
                                logger.debug(f"   2captcha ID: {captcha_id}, esperando resultado...")
                                start_time = time.time()
                                while time.time() - start_time < 120:  # timeout 2 minutos
                                    time.sleep(5)
                                    res_url = f"http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={captcha_id}&json=1"
                                    res_resp = requests.get(res_url, timeout=10)
                                    if res_resp.status_code == 200:
                                        try:
                                            res_data = res_resp.json()
                                        except:
                                            logger.warning("   Respuesta no JSON de 2captcha")
                                            continue
                                        if res_data.get('status') == 1:
                                            coord_data = res_data['request']
                                            # Puede ser string "x1,y1;x2,y2" o una lista de puntos
                                            if isinstance(coord_data, str):
                                                points = []
                                                for pair in coord_data.split(';'):
                                                    if pair:
                                                        x, y = pair.split(',')
                                                        points.append({'x': int(x), 'y': int(y)})
                                                return points
                                            elif isinstance(coord_data, list):
                                                # Formato: [{"x":290,"y":69}, ...] o [ [290,69], ... ]
                                                points = []
                                                for item in coord_data:
                                                    if isinstance(item, dict):
                                                        points.append({'x': int(item['x']), 'y': int(item['y'])})
                                                    elif isinstance(item, list) and len(item) == 2:
                                                        points.append({'x': int(item[0]), 'y': int(item[1])})
                                                return points
                                            else:
                                                logger.warning(f"   Formato de coordenadas desconocido: {type(coord_data)}")
                                        elif res_data.get('request') == 'CAPCHA_NOT_READY':
                                            continue
                                        else:
                                            break
                            return None
                    except Exception as e:
                        logger.warning(f"Error en 2captcha HTTP: {e}")
                        return None

                # Función para llamar a anticaptcha API (versión robusta)
                def solve_anticaptcha_coordinates(image_path, hint):
                    import base64
                    with open(image_path, 'rb') as f:
                        img_base64 = base64.b64encode(f.read()).decode('utf-8')
                    url = "https://api.anti-captcha.com/createTask"
                    data = {
                        "clientKey": API_KEY_ANTICAPTCHA,
                        "task": {
                            "type": "ImageToCoordinatesTask",
                            "body": img_base64,
                            "comment": hint
                        }
                    }
                    try:
                        resp = requests.post(url, json=data, timeout=30)
                        if resp.status_code == 200:
                            result = resp.json()
                            if result.get('errorId') == 0:
                                task_id = result['taskId']
                                logger.debug(f"   anticaptcha task ID: {task_id}, esperando resultado...")
                                start_time = time.time()
                                while time.time() - start_time < 120:  # timeout 2 minutos
                                    time.sleep(5)
                                    res_url = "https://api.anti-captcha.com/getTaskResult"
                                    res_data = {"clientKey": API_KEY_ANTICAPTCHA, "taskId": task_id}
                                    res_resp = requests.post(res_url, json=res_data, timeout=10)
                                    if res_resp.status_code == 200:
                                        res_result = res_resp.json()
                                        if res_result.get('status') == 'ready':
                                            coords = res_result['solution'].get('coordinates')
                                            if coords:
                                                # anticaptcha puede devolver [{"x":290,"y":69}, ...] o lista de listas
                                                points = []
                                                for item in coords:
                                                    if isinstance(item, dict):
                                                        points.append({'x': int(item['x']), 'y': int(item['y'])})
                                                    elif isinstance(item, list) and len(item) == 2:
                                                        points.append({'x': int(item[0]), 'y': int(item[1])})
                                                return points
                                            else:
                                                logger.warning("   anticaptcha devolvió solución sin coordenadas")
                                                return None
                                        elif res_result.get('status') == 'processing':
                                            continue
                                        else:
                                            break
                            return None
                    except Exception as e:
                        logger.warning(f"Error en anticaptcha HTTP: {e}")
                        return None

                # Intentar con 2captcha
                if API_KEY_2CAPTCHA:
                    logger.debug("   Intentando con 2captcha API HTTP...")
                    coordinates = solve_2captcha_coordinates(img_path, hint_text)
                    if coordinates:
                        logger.debug(f"✅ 2captcha resolvió coordenadas: {coordinates}")

                if not coordinates and API_KEY_ANTICAPTCHA:
                    logger.debug("   Intentando con anticaptcha API HTTP...")
                    coordinates = solve_anticaptcha_coordinates(img_path, hint_text)
                    if coordinates:
                        logger.debug(f"✅ anticaptcha resolvió coordenadas: {coordinates}")
                    else:
                        logger.warning("   anticaptcha no devolvió coordenadas")

                if not coordinates:
                    return None, "No se pudo resolver captcha de coordenadas", last_screenshot

                # Verificar que el elemento de clic siga existente y visible
                try:
                    if canvas_element:
                        click_element = await page.query_selector('canvas')
                    else:
                        click_element = await page.query_selector('img[src*="captcha"]')
                    if not click_element or not await click_element.is_visible():
                        logger.error("❌ El elemento de captcha ya no está visible")
                        return None, "Elemento de captcha desapareció", last_screenshot
                except Exception as e:
                    logger.error(f"❌ Error al verificar elemento de captcha: {e}")
                    return None, "Error al verificar elemento de captcha", last_screenshot

                box = await click_element.bounding_box()
                if not box:
                    logger.error("❌ No se pudo obtener bounding box del contenedor (elemento no visible o eliminado)")
                    return None, "No se pudo obtener posición del captcha", last_screenshot

                # Realizar clics en las coordenadas (convertidas a int)
                for point in coordinates:
                    try:
                        abs_x = box['x'] + int(point['x'])
                        abs_y = box['y'] + int(point['y'])
                        await page.mouse.click(abs_x, abs_y)
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"   ⚠️ Error al hacer clic en coordenada {point}: {e}")
                        continue

                # Buscar botón de confirmar
                confirm_btn = await page.query_selector('button:has-text("Confirmar"), input[value="Confirmar"], button[type="submit"]')
                if confirm_btn:
                    await confirm_btn.click()
                    logger.debug("✅ Clic en botón de confirmar")
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    last_screenshot = await take_screenshot(page, "despues_captcha_coordenadas")
                else:
                    logger.warning("⚠️ No se encontró botón de confirmar, puede que se envíe automáticamente")

                # Después de resolver, esperar un poco y actualizar contenido
                await page.wait_for_timeout(5000)
                content = await safe_get_content(page)

            # ----- PASO 15: Verificación por SMS (con posible redirección a WhatsApp) -----
            logger.debug("📱 [PASO 15] Verificando página de verificación de número...")
            await page.wait_for_timeout(5000)
            content = await safe_get_content(page)

            # Detectar si estamos en la página de WhatsApp
            if "Verificar con WhatsApp" in content or "Enviar código por SMS" in content:
                logger.warning("⚠️ Página de verificación con WhatsApp detectada, seleccionando SMS...")
                last_screenshot = await take_screenshot(page, "pagina_whatsapp")
                
                # Buscar el botón "Enviar código por SMS" usando el id del contenedor
                sms_option = await page.query_selector('#secondary_channel_button input.a-button-input')
                if not sms_option:
                    # Intentar con el contenedor directamente
                    sms_option = await page.query_selector('#secondary_channel_button')
                if not sms_option:
                    # Fallback: buscar por texto usando XPath
                    sms_option = await page.query_selector('xpath=//*[contains(text(), "Enviar código por SMS")]')
                
                if sms_option:
                    # Pequeña espera para asegurar que el elemento esté listo
                    await page.wait_for_timeout(500)
                    await sms_option.click()
                    logger.debug("   ✅ Clic en 'Enviar código por SMS'")
                    await page.wait_for_load_state('networkidle', timeout=15000)
                    last_screenshot = await take_screenshot(page, "despues_seleccion_sms")
                else:
                    logger.warning("   ⚠️ No se encontró la opción de SMS, puede que ya esté en la página de código")
            else:
                logger.debug("   ✅ No se detectó página de WhatsApp, continuando...")

            # Ahora esperar el campo de código
            try:
                code_input = await page.wait_for_selector('#cvf-input-code', state='visible', timeout=30000)
                logger.debug("   📱 Página de ingreso de código SMS detectada")
                sms_code = await get_fivesim_code(order_id)
                if sms_code:
                    await code_input.fill(sms_code)
                    logger.debug(f"   ✅ Código SMS ingresado: {sms_code}")
                    verify_btn = await page.query_selector('input[type="submit"], button:has-text("Verificar"), button:has-text("Verify")')
                    if verify_btn:
                        await verify_btn.click()
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        last_screenshot = await take_screenshot(page, "despues_verificacion_sms")
                    else:
                        logger.warning("   ⚠️ No se encontró botón de verificar")
                else:
                    logger.error("❌ No se pudo obtener código SMS")
                    raise Exception("No se pudo obtener código de verificación SMS")
            except Exception as e:
                # Si no aparece el campo de código, verificar mensajes de error
                error_msg = await page.query_selector('.a-alert-content, .a-alert-error')
                if error_msg:
                    error_text = await error_msg.text_content()
                    logger.error(f"❌ Error en verificación SMS: {error_text}")
                    raise Exception(f"Error en verificación SMS: {error_text}")
                else:
                    logger.warning("⚠️ No se encontró campo de código ni mensaje de error, continuando...")
                    last_screenshot = await take_screenshot(page, "sin_codigo_sms")





            # ----- PASO 18: Verificar errores en la página -----
            logger.debug("🔍 [PASO 18] Buscando mensajes de error...")
            soup = BeautifulSoup(content, 'html.parser')
            error_div = soup.find('div', {'class': re.compile('a-alert-error|a-alert-warning|a-box-error')})
            if error_div:
                error_msg = error_div.get_text(strip=True)
                logger.error(f"   ❌ Error en registro: {error_msg}")
                last_screenshot = await take_screenshot(page, "error_registro")
                raise Exception(f"Error en registro: {error_msg}")





            # ----- PASO 19: Verificar éxito (cuenta creada) -----
            logger.debug("🎉 [PASO 19] Verificando éxito...")
            if 'your-account' in page.url.lower() or 'account' in page.url.lower() or 'welcome' in page.url.lower():
                logger.debug("   ✅ Registro exitoso!")
                cookies = await context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                account_data['cookie_dict'] = cookie_dict
                account_data['cookie_string'] = cookie_string
                logger.debug(f"   🍪 Cookies obtenidas: {len(cookie_dict)} cookies")

                # Sincronizar cookies con la sesión requests
                for name, value in cookie_dict.items():
                    session.cookies.set(name, value, domain=f".{base_urls[country_code].replace('https://','')}")





                # ----- PASO 20: Agregar dirección (opcional) -----
                if add_address_flag:
                    logger.debug("📍 [PASO 20] Agregando dirección...")
                    try:
                        # Navegar a la página de direcciones
                        await page.goto(address_book_urls[country_code], wait_until='networkidle', timeout=20000)
                        await page.wait_for_timeout(2000)
                        # Hacer clic en "Agregar dirección"
                        add_link = await page.query_selector('a[href*="/a/addresses/add"]')
                        if not add_link:
                            add_link = await page.query_selector('a:has-text("Agregar dirección")')
                        if add_link:
                            await add_link.click()
                            await page.wait_for_load_state('networkidle', timeout=15000)
                            await page.wait_for_timeout(2000)
                        else:
                            logger.warning("⚠️ No se encontró enlace para agregar dirección, se usará URL directa")
                            await page.goto(add_address_urls[country_code], wait_until='networkidle', timeout=20000)
                            await page.wait_for_timeout(2000)

                        # Datos de dirección según país (usando USA para MX)
                        address_data = {
                            'MX': {
                                'countryCode': 'US',
                                'fullName': 'John Doe',
                                'phone': f'1{random.randint(1000000000,9999999999)}',
                                'line1': '123 Main Street',
                                'city': 'New York',
                                'state': 'NY',
                                'postalCode': '10001'
                            },
                            'US': {
                                'countryCode': 'US',
                                'fullName': 'John Doe',
                                'phone': f'1{random.randint(1000000000,9999999999)}',
                                'line1': '123 Main Street',
                                'city': 'New York',
                                'state': 'NY',
                                'postalCode': '10001'
                            },
                            # Puedes agregar más países según sea necesario
                        }
                        country_data = address_data.get(country_code, address_data['US'])

                        # Seleccionar país en el dropdown
                        try:
                            country_dropdown = await page.query_selector('span.a-button-text[data-action="a-dropdown-button"]')
                            if country_dropdown:
                                await country_dropdown.click()
                                await page.wait_for_timeout(1000)
                                # Buscar la opción por data-value (US)
                                option = await page.query_selector(f'a[data-value*="US"]')
                                if not option:
                                    option = await page.query_selector('a:has-text("Estados Unidos")')
                                if option:
                                    await option.click()
                                    await page.wait_for_timeout(1000)
                                else:
                                    logger.warning("⚠️ No se encontró la opción Estados Unidos")
                            else:
                                logger.warning("⚠️ No se encontró dropdown de país")
                        except Exception as e:
                            logger.warning(f"⚠️ Error seleccionando país: {e}")

                        # Llenar campos
                        await page.fill('#address-ui-widgets-enterAddressFullName', country_data['fullName'])
                        await page.fill('#address-ui-widgets-enterAddressPhoneNumber', country_data['phone'])
                        await page.fill('#address-ui-widgets-enterAddressLine1', country_data['line1'])
                        await page.fill('#address-ui-widgets-enterAddressCity', country_data['city'])

                        # Seleccionar estado
                        try:
                            state_dropdown = await page.query_selector('span.a-button-text[data-action="a-dropdown-button"]', has_text="Seleccionar")
                            if not state_dropdown:
                                state_dropdown = await page.query_selector('span.a-button-text[data-action="a-dropdown-button"]')
                            if state_dropdown:
                                await state_dropdown.click()
                                await page.wait_for_timeout(1000)
                                state_option = await page.query_selector(f'a[data-value*="{country_data["state"]}"]')
                                if not state_option:
                                    state_option = await page.query_selector(f'a:has-text("{country_data["state"]}")')
                                if state_option:
                                    await state_option.click()
                                    await page.wait_for_timeout(1000)
                                else:
                                    logger.warning(f"⚠️ No se encontró opción de estado {country_data['state']}")
                            else:
                                logger.warning("⚠️ No se encontró dropdown de estado")
                        except Exception as e:
                            logger.warning(f"⚠️ Error seleccionando estado: {e}")

                        await page.fill('#address-ui-widgets-enterAddressPostalCode', country_data['postalCode'])

                        # Hacer clic en el botón de enviar
                        submit_btn = await page.query_selector('input[type="submit"]')
                        if submit_btn:
                            await submit_btn.click()
                            logger.debug("   ✅ Clic en botón de agregar dirección")
                            await page.wait_for_load_state('networkidle', timeout=15000)
                            await page.wait_for_timeout(2000)
                            # Verificar si hay éxito o error
                            success_msg = await page.query_selector('.a-alert-success')
                            if success_msg:
                                account_data['address'] = "Dirección agregada exitosamente"
                                logger.debug("   ✅ Dirección agregada correctamente")
                            else:
                                error_msg = await page.query_selector('.a-alert-error')
                                if error_msg:
                                    error_text = await error_msg.text_content()
                                    account_data['address'] = f"Error al agregar dirección: {error_text}"
                                    logger.warning(f"   ⚠️ {account_data['address']}")
                                else:
                                    account_data['address'] = "Dirección agregada (no se pudo confirmar)"
                                    logger.debug("   ℹ️ No se pudo confirmar, pero se intentó")
                        else:
                            logger.warning("⚠️ No se encontró botón de envío")
                            account_data['address'] = "Error: no se encontró botón de envío"
                    except Exception as e:
                        logger.warning(f"⚠️ Error durante el proceso de agregar dirección: {e}")
                        account_data['address'] = f"Error: {e}"
                else:
                    account_data['address'] = "No se agregó dirección"
                    logger.debug("   ℹ️ Omisión de dirección")

                # ----- PASO 21: Visitar wallet para actualizar cookies -----
                try:
                    logger.debug("💳 [PASO 21] Visitando wallet...")
                    await page.goto(wallet_urls[country_code], wait_until='networkidle', timeout=20000)
                    await page.wait_for_timeout(3000)
                    last_screenshot = await take_screenshot(page, "wallet")
                    cookies = await context.cookies()
                    cookie_dict = {c['name']: c['value'] for c in cookies}
                    cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                    account_data['cookie_dict'] = cookie_dict
                    account_data['cookie_string'] = cookie_string
                    logger.debug(f"   ✅ Cookies actualizadas: {len(cookie_dict)} cookies")
                except Exception as e:
                    logger.warning(f"   ⚠️ Error al visitar wallet: {e}")

                logger.debug("🏁 [FIN] create_amazon_account completado con éxito")
                return account_data, None, last_screenshot
            else:
                logger.error(f"   ❌ Registro fallido, URL final: {page.url}")
                last_screenshot = await take_screenshot(page, "error_registro_final")
                raise Exception(f"Registro fallido, URL: {page.url}")


        except Exception as e:
            logger.error(f"❌ Error en intento {global_attempt}: {e}")
            if global_attempt == max_global_retries:
                if page:
                    last_screenshot = await take_screenshot(page, "error_final")
                return None, str(e), last_screenshot
            else:
                logger.info(f"🔄 Reintentando después de 5 segundos (nueva IP)...")
                if page:
                    await page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
                await asyncio.sleep(5)
                continue
        finally:
            logger.debug("🧹 Limpiando recursos (fin del intento)...")
            if page:
                await page.close()
            if context:
                await context.close()
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            logger.debug("✅ Limpieza completada")

    return None, "Error desconocido", None

































# -------------------------------------------------------------------
# FUNCIÓN PARA API
# -------------------------------------------------------------------
async def generate_cookie_api(country, add_address=True):
    logger.debug(f"🚀 generate_cookie_api llamada con country={country}, add_address={add_address}")
    try:
        if country not in base_urls:
            return {'success': False, 'error': f'País no soportado: {country}', 'country': country, 'screenshot': None}
        account_data, error_msg, screenshot = await create_amazon_account(country, add_address_flag=add_address)
        if account_data:
            return {'success': True, 'data': account_data, 'country': country, 'screenshot': screenshot}
        else:
            return {'success': False, 'error': error_msg, 'country': country, 'screenshot': screenshot}
    except Exception as e:
        logger.exception(f"💥 Excepción en generate_cookie_api: {e}")
        return {'success': False, 'error': str(e), 'country': country, 'screenshot': None}

# -------------------------------------------------------------------
# API FLASK
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app, origins=["https://ciber7erroristaschk.com"], methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"], supports_credentials=True)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://ciber7erroristaschk.com')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'service': 'Amazon Cookie Generator API (dinámico)',
        'endpoints': {
            '/generate': 'POST - Generar cookie (JSON: {"country": "MX", "add_address": true})',
            '/health': 'GET - Verificar estado'
        }
    })

@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'proxy': 'configured' if PROXY_HOST_PORT else 'not configured',
        'captcha': bool(API_KEY_2CAPTCHA or API_KEY_ANTICAPTCHA)
    })

@app.route('/generate', methods=['POST', 'OPTIONS'])
def generate():
    if request.method == 'OPTIONS':
        return '', 200
    if API_KEY:
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer ') or auth[7:] != API_KEY:
            return jsonify({'success': False, 'error': 'No autorizado'}), 401
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Se requiere JSON'}), 400
    country = data.get('country', '').upper()
    add_address = data.get('add_address', True)
    if not country:
        return jsonify({'success': False, 'error': 'Falta el parámetro country'}), 400
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(generate_cookie_api(country, add_address))
        return jsonify(result)
    finally:
        loop.close()

@app.route('/diagnostic', methods=['GET'])
def diagnostic():
    return jsonify({
        'status': 'ok',
        'timestamp': time.time(),
        'config': {
            'proxy': 'configurado' if PROXY_HOST_PORT else 'no configurado',
            'captcha_provider': CAPTCHA_PROVIDER,
            'has_2captcha': bool(API_KEY_2CAPTCHA),
            'has_anticaptcha': bool(API_KEY_ANTICAPTCHA),
            'hero_sms': bool(HERO_SMS_API_KEY),
            'fivesim': bool(FIVESIM_API_KEY),
            'supported_countries': list(base_urls.keys())
        }
    })

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli', action='store_true')
    args = parser.parse_args()

    if args.cli:
        print("🍪 Generador de Cookies Amazon - Modo CLI")
        if not API_KEY_2CAPTCHA and not API_KEY_ANTICAPTCHA:
            print("❌ ERROR: Configura al menos una API de captcha")
            sys.exit(1)
        if not PROXY_HOST_PORT:
            print("❌ ERROR: PROXY_STRING no configurada")
            sys.exit(1)
        while True:
            print("\n--- MENÚ ---")
            print("1. Generar cookie")
            print("2. Salir")
            op = input("Opción: ").strip()
            if op == '1':
                pais = input("Código de país (ej: MX, US): ").strip().upper()
                add_addr = input("¿Agregar dirección? (s/n): ").strip().lower()
                add_flag = add_addr != 'n'
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    res = loop.run_until_complete(generate_cookie_api(pais, add_flag))
                    if res['success']:
                        data = res['data']
                        print(f"\n✅ Cookie generada:")
                        print(f"   Teléfono: {data['phone']}")
                        print(f"   Contraseña: {data['password']}")
                        print(f"   Cookie: {data['cookie_string'][:100]}...")
                    else:
                        print(f"\n❌ Error: {res['error']}")
                        if res.get('screenshot'):
                            print("   📸 Captura de pantalla disponible")
                finally:
                    loop.close()
            elif op == '2':
                break
    else:
        print(f"🚀 Iniciando API en {API_HOST}:{API_PORT}")
        app.run(host=API_HOST, port=API_PORT, debug=False, threaded=True)