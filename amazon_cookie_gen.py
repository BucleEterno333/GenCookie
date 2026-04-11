#!/usr/bin/env python3
"""
Amazon Cookie Generator - Versión API REST optimizada para mínimo consumo de proxy
- Bloqueo de imágenes, CSS, fuentes y recursos no esenciales
- Navegación rápida con domcontentloaded
- Capturas de pantalla reducidas (opcional)
- Timeouts ajustables
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
import io
import requests
from urllib.parse import urljoin, urlencode
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify
from flask_cors import CORS

# Forzar UTF-8 en la salida
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# -------------------------------------------------------------------
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO (con valores por defecto)
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

# ----- Timeouts configurables (en segundos) -----
WAIT_TIMEOUT = int(os.getenv('WAIT_TIMEOUT', '10'))          # Espera general para elementos
NAVIGATION_TIMEOUT = int(os.getenv('NAVIGATION_TIMEOUT', '30'))  # Espera de navegación
ACTION_TIMEOUT = int(os.getenv('ACTION_TIMEOUT', '5'))          # Espera para acciones específicas (clics, llenado)
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '5'))               # Reintentos globales

# Opción para reducir calidad de capturas (si se usa)
SCREENSHOT_QUALITY = int(os.getenv('SCREENSHOT_QUALITY', '30'))  # Calidad JPEG (0-100)

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
        time.sleep(2)
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

import requests


def check_user_credits(token, required=3):
    """Verifica que el usuario tenga al menos 'required' créditos."""
    db_api_url = "https://p01--basedatos--vwr6mdxp7dhn.code.run/api/user/credits"
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(db_api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            credits = data.get('credits', 0)
            if credits >= required:
                return True, credits
            else:
                return False, f"Créditos insuficientes. Tienes {credits}, se requieren {required}."
        else:
            return False, f"Error al verificar créditos: {response.status_code}"
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"



def deduct_credits(token, amount=3):
    """Llama a la API de base de datos para descontar créditos del usuario autenticado."""
    db_api_url = "https://p01--basedatos--vwr6mdxp7dhn.code.run/api/user/use-credits"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(db_api_url, json={'amount': amount}, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('success', False), data.get('newCredits')
        else:
            logger.error(f"Error al descontar créditos: {response.status_code} - {response.text}")
            return False, None
    except Exception as e:
        logger.error(f"Excepción al descontar créditos: {e}")
        return False, None

# -------------------------------------------------------------------
# CAPTCHA RESOLUTION (coordenadas) - VERSIÓN HTTP DIRECTA
# -------------------------------------------------------------------
def solve_2captcha_coordinates(image_path, hint):
    """Resuelve captcha de coordenadas usando 2captcha API HTTP."""
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
                while time.time() - start_time < 120:
                    time.sleep(5)
                    res_url = f"http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={captcha_id}&json=1"
                    res_resp = requests.get(res_url, timeout=10)
                    if res_resp.status_code == 200:
                        try:
                            res_data = res_resp.json()
                        except:
                            continue
                        if res_data.get('status') == 1:
                            coord_data = res_data['request']
                            if isinstance(coord_data, str):
                                points = []
                                for pair in coord_data.split(';'):
                                    if pair:
                                        x, y = pair.split(',')
                                        points.append({'x': int(x), 'y': int(y)})
                                return points
                            elif isinstance(coord_data, list):
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

def solve_anticaptcha_coordinates(image_path, hint):
    """Resuelve captcha de coordenadas usando Anti-Captcha API HTTP."""
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
                while time.time() - start_time < 120:
                    time.sleep(5)
                    res_url = "https://api.anti-captcha.com/getTaskResult"
                    res_data = {"clientKey": API_KEY_ANTICAPTCHA, "taskId": task_id}
                    res_resp = requests.post(res_url, json=res_data, timeout=10)
                    if res_resp.status_code == 200:
                        res_result = res_resp.json()
                        if res_result.get('status') == 'ready':
                            coords = res_result['solution'].get('coordinates')
                            if coords:
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

# -------------------------------------------------------------------
# SMS SERVICES
# -------------------------------------------------------------------
FIVESIM_BASE_URL = "https://5sim.net/v1"

FIVESIM_COUNTRY_MAP = {
    'KG': 'kyrgyzstan',
    'PL': 'poland',
    'CO': 'colombia',
    'LV': 'latvia',
    'PK': 'pakistan',
    'TJ': 'tajikistan',
    'KE': 'kenya',
}


COUNTRY_NAME_TO_CODE = {v: k for k, v in FIVESIM_COUNTRY_MAP.items()}

async def get_fivesim_prices():
    """Obtiene precios de 5sim para amazon con operador 'any', ordenados por precio."""
    if not FIVESIM_API_KEY:
        return {}
    url = "https://5sim.net/v1/guest/prices"
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))
        if response.status_code != 200:
            logger.warning(f"⚠️ No se pudo obtener precios de 5sim: {response.status_code}")
            return {}

        data = response.json()
        prices = {}

        # La estructura es: data[country][product][operator] = {cost, count, rate}
        for country_name, products in data.items():
            if 'amazon' not in products:
                continue
            operators = products['amazon']
            if 'any' not in operators:
                continue
            info = operators['any']
            cost = info.get('cost')
            count = info.get('count', 0)
            if cost is not None and count > 0:
                # Convertir nombre del país a código ISO usando el mapeo inverso
                iso_code = COUNTRY_NAME_TO_CODE.get(country_name)
                if iso_code:
                    prices[iso_code] = float(cost)
                else:
                    logger.debug(f"⚠️ País '{country_name}' no mapeado a ISO, se ignora")

        # Ordenar por precio ascendente (más barato primero)
        sorted_prices = sorted(prices.items(), key=lambda x: x[1])
        logger.debug(f"📊 5sim precios ordenados: {sorted_prices}")
        return dict(sorted_prices)
    except Exception as e:
        logger.warning(f"⚠️ Error obteniendo precios de 5sim: {e}")
        return {}

async def get_fivesim_number(country_code, product='amazon'):
    if not FIVESIM_API_KEY:
        logger.warning("⚠️ No hay API key de 5sim")
        return None
    country = FIVESIM_COUNTRY_MAP.get(country_code)
    if not country:
        logger.error(f"❌ No hay mapeo de país 5sim para {country_code}")
        return None
    url = f"{FIVESIM_BASE_URL}/user/buy/activation/{country}/any/{product}"
    headers = {'Authorization': f'Bearer {FIVESIM_API_KEY}', 'Accept': 'application/json'}
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, timeout=30))
        logger.debug(f"📡 5sim respuesta HTTP {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                phone = data.get('phone')
                order_id = data.get('id')
                if phone and order_id:
                    logger.debug(f"📱 Número 5sim comprado: {phone} (order_id: {order_id})")
                    return phone, order_id
                else:
                    logger.warning(f"⚠️ Respuesta inesperada: {data}")
            except ValueError:
                logger.warning(f"⚠️ Respuesta no JSON: {response.text[:200]}")
        else:
            logger.warning(f"⚠️ Error HTTP {response.status_code}: {response.text[:200]}")
        return None
    except Exception as e:
        logger.warning(f"⚠️ Error comprando número 5sim: {e}")
        return None

async def get_fivesim_code(order_id, timeout=180):
    url = f"{FIVESIM_BASE_URL}/user/check/{order_id}"
    headers = {'Authorization': f'Bearer {FIVESIM_API_KEY}', 'Accept': 'application/json'}
    start_time = time.time()
    loop = asyncio.get_running_loop()
    while time.time() - start_time < timeout:
        try:
            response = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, timeout=30))
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    logger.warning(f"⚠️ 5sim respondió con texto no JSON: {response.text[:200]}")
                    await asyncio.sleep(5)
                    continue
                status = data.get('status')
                if status == 'RECEIVED':
                    sms = data.get('sms', [])
                    if sms:
                        code = sms[0].get('code')
                        if not code:
                            text = sms[0].get('text', '')
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
            logger.debug(f"📱 Error esperando código de 5sim: {e}")
            await asyncio.sleep(5)
    return None


async def cancel_fivesim(order_id):
    """Cancela una activación de 5sim para no cobrar."""
    if not FIVESIM_API_KEY:
        return False
    url = f"{FIVESIM_BASE_URL}/user/cancel/{order_id}"
    headers = {'Authorization': f'Bearer {FIVESIM_API_KEY}', 'Accept': 'application/json'}
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(url, headers=headers, timeout=10))
        if response.status_code == 200:
            logger.debug(f"📱 5sim: activación {order_id} cancelada")
            return True
        else:
            logger.warning(f"⚠️ 5sim cancel falló: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Error cancelando 5sim: {e}")
        return False

async def get_hero_sms_number(country_code, service='am'):
    url = "https://hero-sms.com/stubs/handler_api.php"
    params = {
        'api_key': HERO_SMS_API_KEY,
        'action': 'getNumberV2',
        'service': service,
        'country': country_code,
        'operator': 'any'
    }
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(url, params=params, timeout=30))
        try:
            data = response.json()
            if 'activationId' in data and 'phoneNumber' in data:
                return data['phoneNumber'], data['activationId']
            else:
                logger.warning(f"Hero SMS respuesta inesperada (JSON): {data}")
                return None
        except ValueError:
            error_text = response.text.strip()
            logger.warning(f"Hero SMS respuesta no JSON: {error_text}")
            if error_text == 'NO_NUMBERS':
                logger.warning("Hero SMS: No hay números disponibles para este país/servicio")
            elif error_text == 'BAD_KEY':
                logger.error("Hero SMS: API key inválida")
            elif error_text == 'NO_BALANCE':
                logger.error("Hero SMS: Saldo insuficiente")
            return None
    except Exception as e:
        logger.warning(f"Hero SMS exception: {e}")
        return None
    
async def get_hero_sms_code(activation_id, timeout=180):
    url = "https://hero-sms.com/stubs/handler_api.php"
    params = {
        'api_key': HERO_SMS_API_KEY,
        'action': 'getStatusV2',
        'id': activation_id
    }
    start = time.time()
    loop = asyncio.get_running_loop()
    while time.time() - start < timeout:
        try:
            response = await loop.run_in_executor(None, lambda: requests.get(url, params=params, timeout=30))
            if response.status_code == 200:
                data = response.json()
                if data.get('sms') and data['sms'].get('code'):
                    return data['sms']['code']
            await asyncio.sleep(5)
        except Exception as e:
            logger.debug(f"Hero SMS waiting error: {e}")
            await asyncio.sleep(5)
    return None

async def cancel_hero_sms(activation_id):
    """Cancela una activación de Hero SMS (status=8) para reembolso si no se recibió SMS."""
    if not HERO_SMS_API_KEY:
        return False
    url = "https://hero-sms.com/stubs/handler_api.php"
    params = {
        'api_key': HERO_SMS_API_KEY,
        'action': 'setStatus',
        'id': activation_id,
        'status': 8
    }
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(url, params=params, timeout=10))
        if response.status_code == 200:
            logger.debug(f"📱 Hero SMS: activación {activation_id} cancelada")
            return True
        else:
            logger.warning(f"⚠️ Hero SMS cancel falló: {response.text}")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Error cancelando Hero SMS: {e}")
        return False

SMS_SERVICES = [
    {'name': 'hero', 'enabled': bool(HERO_SMS_API_KEY), 'get_number': get_hero_sms_number, 'get_code': get_hero_sms_code},
    {'name': '5sim', 'enabled': bool(FIVESIM_API_KEY), 'get_number': get_fivesim_number, 'get_code': get_fivesim_code},
]

# ===================================================================
# FUNCIÓN PRINCIPAL PARA OBTENER NÚMERO (CORREGIDA)
# ===================================================================
async def get_phone_number(account_country, force_service=None, force_country=None):
    """
    Obtiene un número de teléfono.
    Si force_service y force_country se proporcionan, intenta solo ese servicio/país.
    De lo contrario, sigue el orden por precio de cada servicio.
    """
    # Prefijos para extraer número local (dígitos después del código país)
    prefix_len = {'ID': 2, 'MX': 2, 'US': 1, 'CA': 1, 'UK': 2, 'DE': 2, 'FR': 2,
                  'IT': 2, 'ES': 2, 'JP': 2, 'AU': 2, 'IN': 2}
    
    prefix_len_plus = {'ID': 3, 'MX': 3, 'US': 2, 'CA': 2, 'UK': 3, 'DE': 3, 'FR': 3,
                  'IT': 3, 'ES': 3, 'JP': 3, 'AU': 3, 'IN': 3, 'KG': 3, 'PL': 3, 'CO': 3, 'LV': 3, 'PK': 3, 'TJ': 3, 'KE': 3}

    # Mapeo de códigos de país a números para Hero SMS
    hero_country_map = {
        'BR': 73,   # Brazil +55 $0.03
        'CM': 41,   # Cameroon +237 $0.03
        'MY': 7,    # Malaysia +60 $0.035
        'KZ': 2,    # Kazakhstan +7 $0.035
        'ID': 6,    # Indonesia +62 $0.045
        'MA': 37,   # Morocco +212 $0.045
        'KG': 11,   # Kyrgyzstan +996 $0.045
        'CO': 33,   # Colombia +57 $0.05
        'MX': 54,   # México +52 $0.08
    }

    # Orden de países por precio (barato a caro) para Hero
    # hero_order = ['CM', 'BR', 'MY', 'KZ', 'ID', 'MA' Da error, 'KG', 'CO', 'MX']
    hero_order = ['KZ', 'ID', 'KG', 'CO', 'MX']  # Se quitó MA por error de mapeo

    # Orden manual para 5sim (si no se pueden obtener precios)
    FIVESIM_MANUAL_ORDER = ['CO', 'LV', 'PK', 'TJ', 'KE', 'MX']

    # Para 5sim, obtener precios reales
    fivesim_prices = await get_fivesim_prices()
    if fivesim_prices:
        fivesim_order = list(fivesim_prices.keys())  # ya ordenado por precio
    else:
        fivesim_order = FIVESIM_MANUAL_ORDER

    # Si se forzó un servicio y país, intentar solo eso
    if force_service and force_country:
        logger.debug(f"🔒 Forzando servicio={force_service}, país={force_country}")
        # Buscar el servicio
        target_service = None
        for s in SMS_SERVICES:
            if s['name'] == force_service and s['enabled']:
                target_service = s
                break
        if not target_service:
            logger.warning(f"   ❌ Servicio {force_service} no disponible")
            return None

        try:
            if force_service == 'hero':
                country_num = hero_country_map.get(force_country)
                if not country_num:
                    logger.debug(f"   No hay mapeo Hero para {force_country}")
                    return None
                result = await target_service['get_number'](country_num, service='am')
                if result:
                    phone_full, service_id = result
                    local_len = prefix_len.get(force_country, 0)
                    if local_len and len(phone_full) > local_len:
                        phone_local = phone_full[local_len:]
                        phone_local = re.sub(r'\D', '', phone_local)
                    else:
                        phone_local = phone_full
                    return {
                        'full': f'+{phone_full}',
                        'local': phone_local,
                        'service_id': service_id,
                        'service_name': force_service,
                        'purchase_country': force_country
                    }
            elif force_service == '5sim':
                result = await target_service['get_number'](force_country, product='amazon')
                if result:
                    phone_full, service_id = result
                    local_len = prefix_len_plus.get(force_country, 0)
                    if local_len and len(phone_full) > local_len:
                        phone_local = phone_full[local_len:]
                        phone_local = re.sub(r'\D', '', phone_local)
                    else:
                        phone_local = phone_full
                    return {
                        'full': phone_full,
                        'local': phone_local,
                        'service_id': service_id,
                        'service_name': force_service,
                        'purchase_country': force_country
                    }
        except Exception as e:
            logger.warning(f"   Error obteniendo número forzado: {e}")
        return None

    # Si no hay fuerza, recorrer servicios normalmente
    for service in SMS_SERVICES:
        if not service['enabled']:
            continue
        logger.debug(f"Intentando con {service['name']}...")

        # Elegir orden de países según servicio
        if service['name'] == '5sim':
            country_order = fivesim_order
        elif service['name'] == 'hero':
            country_order = hero_order
        else:
            country_order = [account_country]

        for purchase_country in country_order:
            logger.debug(f"   Probando país {purchase_country}...")
            try:
                if service['name'] == 'hero':
                    purchase_country_num = hero_country_map.get(purchase_country)
                    if not purchase_country_num:
                        logger.debug(f"   No hay mapeo Hero SMS para {purchase_country}")
                        continue
                    result = await service['get_number'](purchase_country_num, service='am')
                    if result:
                        phone_full, service_id = result
                        local_len = prefix_len.get(purchase_country, 0)
                        if local_len and len(phone_full) > local_len:
                            phone_local = phone_full[local_len:]
                            phone_local = re.sub(r'\D', '', phone_local)
                        else:
                            phone_local = phone_full
                        return {
                            'full': f'+{phone_full}',
                            'local': phone_local,
                            'service_id': service_id,
                            'service_name': service['name'],
                            'purchase_country': purchase_country
                        }
                elif service['name'] == '5sim':
                    result = await service['get_number'](purchase_country, product='amazon')
                    if result:
                        phone_full, service_id = result
                        local_len = prefix_len_plus.get(purchase_country, 0)
                        if local_len and len(phone_full) > local_len:
                            phone_local = phone_full[local_len:]
                            phone_local = re.sub(r'\D', '', phone_local)
                        else:
                            phone_local = phone_full
                        return {
                            'full': phone_full,
                            'local': phone_local,
                            'service_id': service_id,
                            'service_name': service['name'],
                            'purchase_country': purchase_country
                        }
                # Otros servicios (no implementados)
                else:
                    result = await service['get_number'](account_country, service='amazon')
                    if result:
                        phone_full, service_id = result
                        phone_local = re.sub(r'\D', '', phone_full)
                        return {
                            'full': phone_full,
                            'local': phone_local,
                            'service_id': service_id,
                            'service_name': service['name'],
                            'purchase_country': account_country
                        }
            except Exception as e:
                logger.warning(f"   Error con {service['name']} en {purchase_country}: {e}")
                continue
    return None

async def wait_for_sms_code(service_name, service_id, page, max_retries=3, timeout_per_retry=30):
    for attempt in range(max_retries):
        logger.debug(f"📱 Esperando código SMS (intento {attempt+1}/{max_retries})...")
        code = None
        for s in SMS_SERVICES:
            if s['name'] == service_name and s['enabled']:
                code = await s['get_code'](service_id, timeout=timeout_per_retry)
                break
        if code:
            return code
        try:
            resend_link = await page.query_selector('a#cvf-resend-link')
            if resend_link:
                await resend_link.click()
                logger.debug("   🔄 Clic en 'Reenviar código'")
                await page.wait_for_timeout(5000)
            else:
                logger.warning("   ⚠️ No se encontró enlace de reenviar")
        except Exception as e:
            logger.warning(f"   ⚠️ Error al hacer clic en reenviar: {e}")
    return None

# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA CAPTURAR PANTALLA (optimizada)
# -------------------------------------------------------------------
async def take_screenshot(page, step_name):
    try:
        screenshot_bytes = await page.screenshot(type='jpeg', quality=SCREENSHOT_QUALITY)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        logger.debug(f"📸 Screenshot tomado en paso: {step_name} (tamaño: {len(screenshot_bytes)} bytes)")
        return screenshot_b64
    except Exception as e:
        logger.warning(f"⚠️ Error tomando screenshot en paso {step_name}: {e}")
        return None

async def safe_get_content(page, timeout=20):
    """Obtiene el contenido de la página con manejo de errores."""
    try:
        await page.wait_for_function('document.readyState === "complete"', timeout=timeout*1000)
        await page.wait_for_timeout(500)
        return await page.content()
    except Exception as e:
        logger.warning(f"⚠️ Error en safe_get_content: {e}")
        await page.wait_for_timeout(2000)
        return await page.content()

# -------------------------------------------------------------------
# FUNCIONES OPTIMIZADAS PARA PLAYWRIGHT (con bloqueo de recursos)
# -------------------------------------------------------------------
async def block_resources(route):
    """Bloquea solo recursos pesados, deja CSS y JS para funcionalidad."""
    resource_type = route.request.resource_type
    if resource_type in ['image', 'font', 'media']:
        await route.abort()
    else:
        await route.continue_()

async def block_heavy_resources(route):
    """Bloquea todo excepto HTML, JS (para que el DOM funcione)."""
    resource_type = route.request.resource_type
    if resource_type in ['image', 'font', 'media', 'stylesheet']:
        await route.abort()
    else:
        await route.continue_()

async def smart_goto(page, url, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT*1000):
    start = time.time()
    logger.debug(f"🌐 Navegando a {url} (wait_until={wait_until})")
    await page.route('**/*', block_resources)
    await page.goto(url, wait_until=wait_until, timeout=timeout)
    elapsed = time.time() - start
    logger.debug(f"   ✅ Navegación completada en {elapsed:.2f}s")

async def smart_click(page, selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=False):
    start = time.time()
    logger.debug(f"🖱️ Intentando clic en selector: {selector}")
    try:
        element = await page.wait_for_selector(selector, state='visible', timeout=timeout)
        if wait_for_navigation:
            async with page.expect_navigation(timeout=NAVIGATION_TIMEOUT*1000):
                await element.click()
        else:
            await element.click()
        elapsed = time.time() - start
        logger.debug(f"   ✅ Clic en {selector} completado en {elapsed:.2f}s")
        return True
    except Exception as e:
        logger.debug(f"   ❌ Clic en {selector} falló: {e}")
        return False

async def smart_fill(page, selector, value, timeout=ACTION_TIMEOUT*1000):
    start = time.time()
    logger.debug(f"✍️ Llenando campo {selector} con valor: {value[:30]}...")
    try:
        element = await page.wait_for_selector(selector, state='visible', timeout=timeout)
        await element.fill(value)
        elapsed = time.time() - start
        logger.debug(f"   ✅ Campo llenado en {elapsed:.2f}s")
        return True
    except Exception as e:
        logger.debug(f"   ❌ Llenado falló: {e}")
        return False

async def wait_for_text(page, text, timeout=WAIT_TIMEOUT*1000):
    start = time.time()
    logger.debug(f"⌛ Esperando texto: {text[:50]}")
    try:
        await page.wait_for_function(f'document.body.innerText.includes("{text}")', timeout=timeout)
        elapsed = time.time() - start
        logger.debug(f"   ✅ Texto encontrado en {elapsed:.2f}s")
        return True
    except Exception:
        elapsed = time.time() - start
        logger.debug(f"   ❌ Texto no encontrado después de {elapsed:.2f}s")
        return False

# -------------------------------------------------------------------
# FUNCIÓN PRINCIPAL DE CREACIÓN DE CUENTA (OPTIMIZADA)
# -------------------------------------------------------------------
async def create_amazon_account(country_code, add_address_flag=True):
    logger.debug(f"🏁 Iniciando creación de cuenta para {country_code}")

    for global_attempt in range(1, MAX_RETRIES + 1):
        logger.debug(f"🔄 Intento global {global_attempt}/{MAX_RETRIES}")
        playwright = None
        browser = None
        context = None
        page = None
        session = None
        last_screenshot = None

        account_data = {
            'phone': None,
            'password': None,
            'name': None,
            'address': None,
            'cookie_string': None,
            'cookie_dict': None,
            'country': country_code,
        }

        try:
            # ----- PASO 1: Configurar sesión requests -----
            logger.debug("📦 Configurando sesión requests...")
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
            logger.debug("🔄 Probando proxy...")
            ok, ip = test_proxy(session)
            if not ok:
                logger.error(f"   ❌ Proxy no funciona: {ip}")
                raise Exception(f"Proxy error: {ip}")
            logger.debug(f"   ✅ Proxy OK - IP pública: {ip}")

            # ----- PASO 3: Obtener número de teléfono temporal -----
            logger.debug("📱 Obteniendo número de teléfono temporal...")
            phone_info = await get_phone_number(country_code)
            if not phone_info:
                raise Exception("No se pudo obtener número de teléfono de ningún servicio")
            phone_number = phone_info['local']
            service_id = phone_info['service_id']
            service_name = phone_info['service_name']
            purchase_country = phone_info.get('purchase_country', country_code)
            logger.debug(f"   ✅ Número obtenido: {phone_number} (servicio: {service_name}, ID: {service_id})")
            account_data['phone'] = phone_number
            account_data['purchase_country'] = purchase_country

            # ----- PASO 4: Generar credenciales -----
            logger.debug("🔑 Generando credenciales...")
            password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
            first_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            last_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            fullname = f"{first_name} {last_name}"
            account_data['password'] = password
            account_data['name'] = fullname
            logger.debug(f"   👤 Nombre: {fullname}")
            logger.debug(f"   🔐 Contraseña: {password}")

            # ----- PASO 5: Iniciar Playwright -----
            logger.debug("🎬 Iniciando Playwright...")
            playwright = await async_playwright().start()
            logger.debug("   ✅ Playwright iniciado")

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
            logger.debug("🚀 Lanzando browser...")
            browser = await playwright.chromium.launch(**launch_options)
            logger.debug("   ✅ Browser lanzado")

            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=random.choice(USER_AGENTS),
                locale='es-MX' if country_code == 'MX' else 'en-US',
                timezone_id='America/Mexico_City' if country_code == 'MX' else 'America/New_York'
            )

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
            logger.debug("   ✅ Contexto y página creados")

            # ----- PASO 7: Navegar a la URL base con bloqueo de recursos -----
            base_url = base_urls[country_code]
            await page.route('**/*', block_heavy_resources)   # Bloquea CSS temporalmente
            await page.goto(base_url, wait_until='commit', timeout=NAVIGATION_TIMEOUT*1000)
            await page.wait_for_selector('a[data-nav-role="signin"]', timeout=WAIT_TIMEOUT*1000*2)
            await page.unroute('**/*', block_heavy_resources)
            await page.route('**/*', block_resources)

            # ----- PASO 7.5: Manejar posible página de bienvenida "Continuar a Compras" -----
            logger.debug("🛒 [PASO 7.5] Verificando página de bienvenida o redirección...")
            continue_shopping_selectors = [
                'input[value="Continuar a Compras"]',
                'button:has-text("Continuar a Compras")',
                'a:has-text("Continuar a Compras")',
                'input[value="Continue to Shopping"]',
                'button:has-text("Continue to Shopping")',
                'input[value="Seguir comprando"]',
                'button:has-text("Seguir comprando")'
            ]
            for selector in continue_shopping_selectors:
                try:
                    btn = await page.wait_for_selector(selector, state='visible', timeout=200)
                    if btn:
                        logger.debug(f"   ✅ Botón de continuar encontrado: {selector}")
                        await btn.click()
                        await page.wait_for_load_state('domcontentloaded', timeout=NAVIGATION_TIMEOUT*1000)
                        logger.debug("   ✅ Continuar a compras clickeado")
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue
            else:
                logger.debug("   ℹ️ No se detectó página de bienvenida, continuando normal")

            logger.debug("👤 Buscando enlace de inicio de sesión...")
            selector = 'a[data-nav-role="signin"]'
            if not await smart_click(page, selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=True):
                raise Exception("No se encontró enlace de inicio de sesión")
            last_screenshot = await take_screenshot(page, "after_login_click")

            # ----- PASO 9: Ingresar número de teléfono -----
            logger.debug("📱 Ingresando número de teléfono...")
            phone_field_selector = 'input#ap_email, input[name="email"], input[type="email"], input[type="tel"]'
            if not await smart_fill(page, phone_field_selector, phone_info['full'], timeout=ACTION_TIMEOUT*1000):
                raise Exception("No se encontró campo para ingresar número de teléfono")
            last_screenshot = await take_screenshot(page, "phone_llenado")

            # ----- PASO 10: Hacer clic en Continuar -----
            logger.debug("🖱️ Haciendo clic en Continuar...")
            continue_selectors = ['input.a-button-input', 'button#continue']
            continue_clicked = False
            for selector in continue_selectors:
                if await smart_click(page, selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=True):
                    continue_clicked = True
                    break
            if not continue_clicked:
                raise Exception("No se encontró botón Continuar")
            last_screenshot = await take_screenshot(page, "despues_continuar")

            # ----- PASO 10.5: Manejar números ya registrados (bucle de cambio) -----
            max_phone_attempts = 3
            phone_attempt = 1
            phone_success = False
            current_service = phone_info['service_name']
            current_country = phone_info['purchase_country']

            while phone_attempt <= max_phone_attempts and not phone_success:
                # Verificar si la URL contiene "claim?" (número ya registrado)
                if "claim?" in page.url.lower():
                    logger.warning(f"⚠️ Número ya registrado (intento {phone_attempt}/{max_phone_attempts}). Intentando cambiar...")
                    
                    # 1. Intentar localizar el enlace "Cambiar" con diferentes selectores
                    change_link = None
                    change_selectors = [
                        '#ap_change_login_claim',                           # ID directo
                        'a:has-text("Cambiar")',                            # Texto en español
                        'a:has-text("Change")',                             # Texto en inglés
                        'a[href*="ap/signin"][href*="prepopulatedLoginId"]' # URL con parámetros
                    ]
                    for sel in change_selectors:
                        try:
                            change_link = await page.wait_for_selector(sel, timeout=WAIT_TIMEOUT*1000)
                            if change_link:
                                logger.debug(f"   ✅ Enlace 'Cambiar' encontrado con selector: {sel}")
                                break
                        except Exception as e:
                            logger.debug(f"   ⚠️ Selector {sel} falló: {e}")
                            continue
                    
                    # 2. Si no se encontró con los selectores, buscar la URL del enlace en el HTML
                    if not change_link:
                        logger.debug("   🔍 No se encontró enlace con selectores, extrayendo URL del HTML...")
                        page_content = await page.content()
                        # Buscar el href del enlace con id="ap_change_login_claim"
                        import re
                        match = re.search(r'<a\s+id="ap_change_login_claim"[^>]*href="([^"]+)"', page_content)
                        if match:
                            change_url = match.group(1).replace('&amp;', '&')
                            logger.debug(f"   🌐 URL extraída: {change_url}")
                            # Navegar directamente a esa URL
                            await page.goto(change_url, wait_until='domcontentloaded')
                            # Esperar a que aparezca el campo de teléfono
                            await page.wait_for_selector(phone_field_selector, state='visible', timeout=WAIT_TIMEOUT*1000)
                            # Indicar que hemos cambiado (no usamos change_link pero el flujo continúa)
                            change_link = True  # Bandera para indicar que se realizó el cambio
                        else:
                            logger.warning("   ❌ No se pudo extraer la URL del enlace 'Cambiar'")
                            raise Exception("No se encontró enlace para cambiar número")
                    
                    # 3. Si tenemos un enlace (ya sea por selector o por navegación directa)
                    if change_link:
                        # Si el enlace se obtuvo por selector, hacer clic normalmente
                        if hasattr(change_link, 'click'):
                            await change_link.click()
                            await page.wait_for_load_state('domcontentloaded')
                            # Esperar que aparezca de nuevo el campo de teléfono
                            await page.wait_for_selector(phone_field_selector, state='visible', timeout=WAIT_TIMEOUT*1000)
                        # Si ya navegamos directamente, ya estamos en la página correcta
                        
                        # Cancelar la activación anterior
                        if phone_info and service_id:
                            if service_name == 'hero':
                                await cancel_hero_sms(service_id)
                            elif service_name == '5sim':
                                await cancel_fivesim(service_id)
                        
                        # Obtener un nuevo número (mismo servicio/país)
                        phone_info = await get_phone_number(country_code, force_service=current_service, force_country=current_country)
                        if not phone_info:
                            logger.warning("   ❌ No se pudo obtener otro número, pasando al siguiente intento global.")
                            raise Exception("No hay números disponibles para este país/servicio")
                        phone_number = phone_info['local']
                        service_id = phone_info['service_id']
                        service_name = phone_info['service_name']
                        purchase_country_used = phone_info['purchase_country']
                        account_data['phone'] = phone_number
                        account_data['purchase_country'] = purchase_country_used
                        
                        # Rellenar el nuevo número
                        await smart_fill(page, phone_field_selector, phone_info['full'])
                        # Hacer clic en continuar nuevamente
                        continue_clicked = False
                        for selector in continue_selectors:
                            if await smart_click(page, selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=True):
                                continue_clicked = True
                                break
                        if not continue_clicked:
                            raise Exception("No se encontró botón Continuar después de cambiar número")
                        
                        phone_attempt += 1
                        continue
                    else:
                        raise Exception("No se pudo cambiar de número")
                else:
                    phone_success = True

            if not phone_success:
                raise Exception("Se agotaron los intentos de cambio de número")



            # ----- PASO 11: Página intermedia "Proceder a crear una cuenta" -----
            logger.debug("🔍 Verificando página intermedia...")

            # Selector principal (el único que debería aparecer)
            primary_selector = 'span#intention-submit-button input.a-button-input'

            # Intentar hacer clic en el botón (si existe)
            clicked = await smart_click(page, primary_selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=False)

            if clicked:
                # Si se hizo clic, esperar que aparezca el formulario de registro
                try:
                    await page.wait_for_selector('#ap_customer_name', state='visible', timeout=WAIT_TIMEOUT*1000)
                    logger.debug("   ✅ Formulario de registro cargado después del clic")
                except Exception as e:
                    raise Exception(f"Timeout esperando campo de nombre después del clic: {e}")
            else:
                # No se encontró el botón, verificar si es error de Amazon
                logger.debug("   ⚠️ No se encontró el botón 'Proceder a crear una cuenta'")
                # Obtener el texto de la página (o buscar elementos de error)
                page_content = await page.content()
                if "Lo sentimos" in page_content or "no podemos crear tu cuenta" in page_content or "Lo sentimos, no podemos crear tu cuenta" in page_content:
                    logger.warning("   ❌ Página de error de Amazon detectada (cuenta no permitida). Terminando intento.")
                    raise Exception("Amazon bloqueó la creación de cuenta (mensaje 'Lo sentimos')")
                else:
                    # No hay error visible, esperar unos segundos a que quizás el formulario aparezca automáticamente
                    logger.debug("   ℹ️ No se detectó error. Esperando 4 segundos a que el formulario cargue automáticamente...")
                    await page.wait_for_timeout(4000)
                    # Verificar si el formulario de registro ya está visible
                    try:
                        await page.wait_for_selector('#ap_customer_name', state='visible', timeout=2000)
                        logger.debug("   ✅ Formulario de registro cargado automáticamente")
                    except Exception:
                        # Si después de la espera no aparece, lanzar excepción
                        raise Exception("No se pudo acceder al formulario de registro después de Continuar")

            # Captura de pantalla
            last_screenshot = await take_screenshot(page, "despues_proceder")





            # ----- PASO 12: Llenar formulario de registro -----
            logger.debug("📝 Llenando formulario completo...")
            last_screenshot = await take_screenshot(page, "formulario_antes_llenar")

            # Nombre
            name_selectors = ['input#ap_customer_name', 'input[name="customerName"]']
            name_filled = False
            for sel in name_selectors:
                if await smart_fill(page, sel, fullname):
                    name_filled = True
                    break
            if not name_filled:
                logger.warning("⚠️ No se pudo llenar campo de nombre, puede estar precargado")

            # Contraseña
            pwd_selectors = ['input#ap_password', 'input[name="password"]']
            pwd_filled = False
            for sel in pwd_selectors:
                if await smart_fill(page, sel, password):
                    pwd_filled = True
                    break
            if not pwd_filled:
                raise Exception("No se pudo llenar campo de contraseña")

            # Confirmación
            confirm_selectors = ['input#ap_password_check', 'input[name="passwordCheck"]']
            for sel in confirm_selectors:
                await smart_fill(page, sel, password)

            # ----- PASO 13: Botón de registro final -----
            logger.debug("🎯 Buscando botón de registro final...")
            final_btn_selectors = [
                'input#continue', 'input.a-button-input', 'button[type="submit"]',
                'input[value*="Crear cuenta"]', 'button:has-text("Crear cuenta")',
                'input[value*="Create account"]', 'button:has-text("Create account")'
            ]
            clicked_final = False
            for selector in final_btn_selectors:
                if await smart_click(page, selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=True):
                    clicked_final = True
                    break
            if not clicked_final:
                logger.warning("⚠️ No se encontró botón de registro final, puede que ya se haya enviado")
            last_screenshot = await take_screenshot(page, "despues_registro")

            # ----- PASO 14: Detectar captcha -----
            logger.debug("🔍 Verificando captcha después del envío...")
            if await wait_for_text(page, "Resuelve esta adivinanza", timeout=3*1000) or await wait_for_text(page, "Elija todo", timeout=1*1000):
                logger.warning("⚠️ Captcha de selección de imágenes detectado")
                await page.wait_for_timeout(5000)
                last_screenshot = await take_screenshot(page, "captcha_seleccion")
                canvas_element = await page.query_selector('canvas')
                img_element = await page.query_selector('img[src*="captcha"]')
                click_element = None
                if canvas_element:
                    logger.debug("   ✅ Captcha es un canvas, tomando screenshot del elemento")
                    screenshot_bytes = await canvas_element.screenshot()
                    img_path = 'temp_canvas_captcha.png'
                    with open(img_path, 'wb') as f:
                        f.write(screenshot_bytes)
                    click_element = canvas_element
                elif img_element:
                    logger.debug("   ✅ Captcha es una imagen, descargando...")
                    img_src = await img_element.get_attribute('src')
                    if not img_src:
                        logger.error("La imagen del captcha no tiene src")
                        raise Exception("Imagen de captcha sin src")
                    img_data = requests.get(img_src, timeout=10).content
                    img_path = 'temp_image_captcha.jpg'
                    with open(img_path, 'wb') as f:
                        f.write(img_data)
                    click_element = img_element
                else:
                    logger.warning("   ⚠️ No se encontró canvas ni imagen, esperando otros 5 segundos más...")
                    await page.wait_for_timeout(9000)
                    canvas_element = await page.query_selector('canvas')
                    img_element = await page.query_selector('img[src*="captcha"]')
                    if canvas_element:
                        screenshot_bytes = await canvas_element.screenshot()
                        img_path = 'temp_canvas_captcha.png'
                        with open(img_path, 'wb') as f:
                            f.write(screenshot_bytes)
                        click_element = canvas_element
                    elif img_element:
                        img_src = await img_element.get_attribute('src')
                        img_data = requests.get(img_src, timeout=10).content
                        img_path = 'temp_image_captcha.jpg'
                        with open(img_path, 'wb') as f:
                            f.write(img_data)
                        click_element = img_element
                    else:
                        logger.error("❌ No se encontró canvas ni imagen de captcha después de reintentar")
                        raise Exception("No se pudo encontrar elemento de captcha")

                hint_text = "Haz clic en todas las imágenes que correspondan"
                coordinates = None
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
                if not coordinates:
                    raise Exception("No se pudo resolver captcha de coordenadas")

                # Realizar clics
                box = await click_element.bounding_box()
                if box:
                    for point in coordinates:
                        try:
                            abs_x = box['x'] + int(point['x'])
                            abs_y = box['y'] + int(point['y'])
                            await page.mouse.click(abs_x, abs_y)
                            await asyncio.sleep(0.3)
                        except Exception as e:
                            logger.warning(f"   ⚠️ Error al hacer clic: {e}")
                else:
                    logger.warning("No se pudo obtener bounding box del captcha")

                # Botón confirmar
                confirm_btn = await page.query_selector('button:has-text("Confirmar"), input[value="Confirmar"], button[type="submit"]')
                if confirm_btn:
                    await confirm_btn.click()
                    logger.debug("✅ Clic en botón de confirmar")
                    await page.wait_for_load_state('domcontentloaded', timeout=NAVIGATION_TIMEOUT*1000)
                else:
                    logger.warning("⚠️ No se encontró botón de confirmar")
                await page.wait_for_timeout(2000)

            # ----- PASO 15: Verificación por SMS -----
            logger.debug("📱 [PASO 15] Verificando página de verificación de número...")
            await page.wait_for_timeout(5000)
            content = await safe_get_content(page)

            if "Verificar con WhatsApp" in content or "Enviar código por SMS" in content:
                logger.warning("⚠️ Página de verificación con WhatsApp detectada, seleccionando SMS...")
                sms_option = await page.query_selector('#secondary_channel_button input.a-button-input')
                if not sms_option:
                    sms_option = await page.query_selector('#secondary_channel_button')
                if not sms_option:
                    sms_option = await page.query_selector('xpath=//*[contains(text(), "Enviar código por SMS")]')
                if sms_option:
                    await page.wait_for_timeout(500)
                    await sms_option.click()
                    logger.debug("   ✅ Clic en 'Enviar código por SMS'")
                    await page.wait_for_load_state('load', timeout=15000)
                else:
                    logger.warning("   ⚠️ No se encontró la opción de SMS, puede que ya esté en la página de código")

            # Esperar el campo de código
            try:
                code_input = await page.wait_for_selector('#cvf-input-code', state='visible', timeout=30000)
                logger.debug("   📱 Página de ingreso de código SMS detectada")
            except Exception as e:
                error_msg = await page.query_selector('.a-alert-content, .a-alert-error')
                if error_msg:
                    error_text = await error_msg.text_content()
                    if "Hemos enviado tu OTP" in error_text:
                        logger.debug("   ℹ️ Mensaje de envío detectado, esperando campo de código...")
                        await page.wait_for_timeout(3000)
                        code_input = await page.wait_for_selector('#cvf-input-code', state='visible', timeout=30000)
                    else:
                        logger.error(f"❌ Error en verificación SMS: {error_text}")
                        raise Exception(f"Error en verificación SMS: {error_text}")
                else:
                    raise

            # Obtener el código SMS con timeout de 30 segundos y cancelación si no llega
            sms_code = None
            if service_name == 'hero':
                sms_code = await get_hero_sms_code(service_id, timeout=30)
                if not sms_code:
                    await cancel_hero_sms(service_id)
                    raise Exception("Timeout esperando código SMS de Hero")
            elif service_name == '5sim':
                sms_code = await get_fivesim_code(service_id, timeout=30)
                if not sms_code:
                    await cancel_fivesim(service_id)
                    raise Exception("Timeout esperando código SMS de 5sim")
            else:
                sms_code = await wait_for_sms_code(service_name, service_id, page, max_retries=1, timeout_per_retry=20)
                if not sms_code:
                    raise Exception(f"Timeout esperando código SMS de {service_name}")

            if sms_code:
                code_input = await page.wait_for_selector('#cvf-input-code', state='visible', timeout=ACTION_TIMEOUT*1000)
                await code_input.fill(sms_code)
                logger.debug(f"   ✅ Código SMS ingresado: {sms_code}")
                verify_btn = await page.query_selector('input[type="submit"], button:has-text("Verificar"), button:has-text("Verify")')
                if verify_btn:
                    await verify_btn.click()
                    await page.wait_for_load_state('domcontentloaded', timeout=NAVIGATION_TIMEOUT*1000)
                else:
                    logger.warning("   ⚠️ No se encontró botón de verificar")
            else:
                raise Exception("No se pudo obtener código de verificación SMS")

            # ----- PASO 16: Verificar éxito -----
            if 'your-account' in page.url.lower() or 'account' in page.url.lower() or 'welcome' in page.url.lower():
                logger.debug("   ✅ Registro exitoso!")
                cookies = await context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                account_data['cookie_dict'] = cookie_dict
                account_data['cookie_string'] = cookie_string
                logger.debug(f"   🍪 Cookies obtenidas: {len(cookie_dict)} cookies")

                # ----- PASO 17: Agregar dirección (opcional) -----
                if add_address_flag:
                    logger.debug("📍 Agregando dirección...")
                    try:
                        await page.unroute('**/*', block_resources)
                        await smart_goto(page, add_address_urls[country_code], wait_until='domcontentloaded', timeout=20000)
                        await page.wait_for_selector('#address-ui-widgets-enterAddressLine1, #address-ui-widgets-enterAddressFullName', timeout=15000)
                        last_screenshot = await take_screenshot(page, "add_address_form")

                        address_data = {
                            'US': {
                                'fullName': 'John Doe',
                                'phone': f'1{random.randint(1000000000, 9999999999)}',
                                'line1': '123 Main Street',
                                'city': 'New York',
                                'state': 'NY',
                                'postalCode': '10001'
                            },
                            'MX': {
                                'street': 'Calzada Ignacio Zaragoza 1584',
                                'postal_code': '09100',
                                'city': 'Ciudad de México',
                                'state': 'CDMX',
                                'phone': f"55{random.randint(10000000, 99999999)}"
                            }
                        }

                        target_country = 'MX'
                        if target_country != country_code:
                            logger.debug(f"🌎 Cambiando país a {target_country} (desde {country_code})")
                            dropdown_btn = await page.wait_for_selector('span.a-button-text[data-action="a-dropdown-button"]', timeout=5000)
                            await dropdown_btn.click()
                            await page.wait_for_timeout(1000)
                            first_letter = 'E' if target_country == 'US' else 'M'
                            await page.keyboard.type(first_letter)
                            await page.wait_for_timeout(1000)
                            click_x = 500
                            click_y = 300
                            await page.mouse.click(click_x, click_y)
                            await page.wait_for_timeout(2000)
                            logger.debug(f"   ✅ País cambiado a {target_country} mediante coordenadas")
                        else:
                            logger.debug(f"   🇲🇽 Usando país actual {country_code} para dirección")

                        if target_country == 'US':
                            data = address_data['US']
                            await smart_fill(page, '#address-ui-widgets-enterAddressFullName', data['fullName'])
                            await smart_fill(page, '#address-ui-widgets-enterAddressPhoneNumber', data['phone'])
                            await smart_fill(page, '#address-ui-widgets-enterAddressLine1', data['line1'])
                            city_input = await page.query_selector('#address-ui-widgets-enterAddressCity-input, #address-ui-widgets-enterAddressCity input')
                            if city_input:
                                await city_input.fill(data['city'])
                            else:
                                await smart_fill(page, 'input[aria-label*="Ciudad"]', data['city'])
                            try:
                                state_dropdown = await page.wait_for_selector('#address-ui-widgets-enterAddressStateOrRegion .a-button, .a-dropdown-button', timeout=5000)
                                await state_dropdown.click()
                                await page.wait_for_selector('.a-dropdown-options', state='visible', timeout=5000)
                                await page.keyboard.type(data['state'][0])
                                await page.wait_for_timeout(500)
                                await page.mouse.click(click_x, click_y + 100)
                                logger.debug(f"   ✅ Estado seleccionado: {data['state']}")
                            except Exception as e:
                                logger.warning(f"   ⚠️ No se pudo seleccionar estado: {e}")
                            await smart_fill(page, '#address-ui-widgets-enterAddressPostalCode', data['postalCode'])
                        else:   # México
                            data = address_data['MX']
                            await smart_fill(page, '#address-ui-widgets-enterAddressLine1', data['street'])
                            await smart_fill(page, '#address-ui-widgets-enterAddressPostalCode', data['postal_code'])
                            validate_btn = await page.wait_for_selector('#address-ui-widgets-enterAddressPostalCode-submit', timeout=5000)
                            if validate_btn:
                                await validate_btn.click()
                                await page.wait_for_timeout(3000)

                        submit_btn = await page.query_selector('span#address-ui-widgets-form-submit-button input[type="submit"], input[value="Agregar dirección"]')
                        if submit_btn:
                            await submit_btn.click()
                            await page.wait_for_timeout(3000)
                            error_elem = await page.query_selector('.a-alert-error, .a-alert-warning')
                            if error_elem:
                                submit_btn2 = await page.query_selector('span#address-ui-widgets-form-submit-button input[type="submit"], input[value="Agregar dirección"]')
                                if submit_btn2:
                                    async with page.expect_navigation(timeout=NAVIGATION_TIMEOUT*1000):
                                        await submit_btn2.click()
                                    logger.debug("   ✅ Segundo clic realizado, navegación detectada")
                                else:
                                    logger.warning("   ⚠️ Botón desapareció después del primer clic")
                            else:
                                logger.debug("   ✅ Dirección agregada sin error")
                        else:
                            logger.warning("   ⚠️ No se encontró botón de envío")

                        if "addresses" in page.url:
                            account_data['address'] = "Dirección agregada exitosamente"
                            logger.debug("   ✅ Dirección agregada")
                        else:
                            account_data['address'] = f"Redirección inesperada: {page.url}"
                    except Exception as e:
                        logger.warning(f"⚠️ Error agregando dirección: {e}")
                        account_data['address'] = f"Error: {e}"
                    finally:
                        await page.route('**/*', block_resources)
                else:
                    account_data['address'] = "No se agregó dirección"

                return account_data, None, last_screenshot
            else:
                raise Exception(f"Registro fallido, URL: {page.url}")

        except Exception as e:
            logger.error(f"❌ Error en intento {global_attempt}: {e}")
            if global_attempt == MAX_RETRIES:
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
            logger.debug("🧹 Limpiando recursos...")
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
        'service': 'Amazon Cookie Generator API (optimizado - mínimo consumo)',
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
        'captcha': bool(API_KEY_2CAPTCHA or API_KEY_ANTICAPTCHA),
        'resource_blocking': 'enabled'
    })

@app.route('/generate', methods=['POST', 'OPTIONS'])
def generate():
    if request.method == 'OPTIONS':
        return '', 200

    # Obtener el header de autorización
    auth_header = request.headers.get('Authorization', '')
    user_token = None
    if auth_header.startswith('Bearer '):
        user_token = auth_header[7:]   # extrae el token del usuario

    # Si el servicio tiene una API_KEY configurada, verificar que coincida con el header
    if API_KEY:
        expected_auth = f'Bearer {API_KEY}'
        if auth_header != expected_auth:
            return jsonify({'success': False, 'error': 'No autorizado'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Se requiere JSON'}), 400
    country = data.get('country', '').upper()
    add_address = data.get('add_address', True)
    if not country:
        return jsonify({'success': False, 'error': 'Falta el parámetro country'}), 400

    # Verificar créditos si hay token de usuario
    if user_token:
        ok, msg = check_user_credits(user_token, 3)
        if not ok:
            return jsonify({'success': False, 'error': msg}), 402
    # Si no hay token, podría ser una llamada desde el bot (que ya descuenta aparte) o desde otro servicio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(generate_cookie_api(country, add_address))
        if result['success'] and user_token:
            success, new_credits = deduct_credits(user_token, 3)
            if not success:
                logger.error("No se pudieron descontar créditos después de generar cookie")
            else:
                result['remaining_credits'] = new_credits
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
            'supported_countries': list(base_urls.keys()),
            'timeouts': {
                'WAIT_TIMEOUT': WAIT_TIMEOUT,
                'NAVIGATION_TIMEOUT': NAVIGATION_TIMEOUT,
                'ACTION_TIMEOUT': ACTION_TIMEOUT,
                'MAX_RETRIES': MAX_RETRIES
            },
            'resource_blocking': True,
            'screenshot_quality': SCREENSHOT_QUALITY
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
        print("🍪 Generador de Cookies Amazon - Modo CLI (optimizado - mínimo consumo)")
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
        print(f"🚀 Iniciando API optimizada (mínimo consumo) en {API_HOST}:{API_PORT}")
        app.run(host=API_HOST, port=API_PORT, debug=False, threaded=True)