#!/usr/bin/env python3
"""
Amazon Cookie Generator - Versión API REST optimizada para mínimo consumo de proxy
- Bloqueo de imágenes, CSS, fuentes y recursos no esenciales
- Navegación rápida con domcontentloaded
- Capturas de pantalla reducidas (opcional)
- Timeouts ajustables
- MEJORAS: FunCaptcha con reintentos internos (10 intentos, misma IP)
- Resolución de FunCaptcha con 2captcha + AntiCaptcha (fallback, múltiples surl)
- Detección de actividad inusual
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
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY', '')
API_BASE_URL = os.getenv('API_BASE_URL', '')

# ----- Timeouts configurables (en segundos) -----
WAIT_TIMEOUT = int(os.getenv('WAIT_TIMEOUT', '10'))          # Espera general para elementos
NAVIGATION_TIMEOUT = int(os.getenv('NAVIGATION_TIMEOUT', '60'))  # Espera de navegación
ACTION_TIMEOUT = int(os.getenv('ACTION_TIMEOUT', '5'))          # Espera para acciones específicas (clics, llenado)
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '10'))               # Reintentos globales

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
# ÓRDENES DE PAÍSES PARA SMS (usados en get_phone_number y en verificación SMS)
# -------------------------------------------------------------------
# HERO_COUNTRY_ORDER = ['CM', 'BR', 'KZ', 'ID', 'MA', 'KG', 'CO', 'MX']

HERO_COUNTRY_ORDER = ['CM', 'BR', 'ID', 'MA', 'KG', 'CO', 'MX']
FIVESIM_MANUAL_ORDER = ['CO', 'LV', 'PK', 'TJ', 'KE', 'MX']

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

# Almacén de sesiones exitosas (proxy + timestamp)
# Estructura: { "session_id": {"last_used": timestamp, "success_count": int} }
GOOD_SESSIONS = {}
SESSION_LIFETIME = 3600  # segundos (1 hora)

def add_good_session(session_id):
    """Registra una sesión como exitosa (sin captcha)."""
    GOOD_SESSIONS[session_id] = {
        "last_used": time.time(),
        "success_count": GOOD_SESSIONS.get(session_id, {}).get("success_count", 0) + 1
    }
    logger.debug(f"✅ Sesión {session_id} marcada como buena (total: {len(GOOD_SESSIONS)})")

def get_best_session():
    """Devuelve el session_id más reciente y exitoso, o None."""
    if not GOOD_SESSIONS:
        return None
    # Ordenar por último uso (más reciente primero) y luego por éxito
    best = max(GOOD_SESSIONS.items(), key=lambda x: (x[1]["last_used"], x[1]["success_count"]))
    session_id = best[0]
    # Limpiar sesiones vencidas
    now = time.time()
    expired = [sid for sid, data in GOOD_SESSIONS.items() if now - data["last_used"] > SESSION_LIFETIME]
    for sid in expired:
        del GOOD_SESSIONS[sid]
        logger.debug(f"🗑️ Sesión {sid} expirada")
    return session_id


def is_service_enabled():
    """Consulta el estado del interruptor en CheckerCT."""
    try:
        headers = {'x-api-key': SERVICE_API_KEY}
        response = requests.get(f"{API_BASE_URL}/admin/service-status-for-generator", headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('enabled', True)
        else:
            logger.warning(f"No se pudo obtener estado: {response.status_code}")
            return True  # Por defecto activo si falla
    except Exception as e:
        logger.warning(f"Error consultando estado: {e}")
        return True
    
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
    """Verifica que el usuario tenga al menos 'required' créditos y devuelve su rol."""
    db_api_url = f"{API_BASE_URL}/user/credits"
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(db_api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            credits = data.get('credits', 0)
            role = data.get('role', 'user')
            if credits >= required:
                return True, credits, role
            else:
                return False, f"Créditos insuficientes. Tienes {credits}, se requieren {required}.", role
        else:
            return False, f"Error al verificar créditos: {response.status_code}", None
    except Exception as e:
        return False, f"Error de conexión: {str(e)}", None

def deduct_credits(token, amount=3):
    """Llama a la API de base de datos para descontar créditos del usuario autenticado."""
    db_api_url = f"{API_BASE_URL}/user/use-credits"
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





async def log_current_url(page, step_name):
    """Registra la URL actual de la página en los logs."""
    try:
        current_url = page.url
        logger.debug(f"📍 [{step_name}] URL actual: {current_url}")
        return current_url
    except Exception as e:
        logger.warning(f"⚠️ No se pudo obtener URL en paso {step_name}: {e}")
        return None









# ===================================================================
# FUNCIONES PARA RESOLVER CAPTCHA (FunCaptcha y coordenadas) - MEJORADAS 2
# ===================================================================

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
        resp = requests.post(url, data=data, timeout=60)
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


            else:
                logger.warning(f"   2captcha error: {result}")
                return None
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
                                # ----- AQUI ESTA LA MEJORA: aceptar distintos formatos -----
                                if isinstance(coords, list):
                                    for item in coords:
                                        if isinstance(item, dict):
                                            # Formato: [{'x': 1, 'y': 2}, ...]
                                            points.append({'x': int(item['x']), 'y': int(item['y'])})
                                        elif isinstance(item, list) and len(item) == 2:
                                            # Formato: [[1,2], [3,4], ...]  <--- ESTE ES EL NUEVO
                                            points.append({'x': int(item[0]), 'y': int(item[1])})
                                        else:
                                            logger.warning(f"   Formato de coordenada desconocido: {item}")
                                elif isinstance(coords, str):
                                    # Formato: "x,y;x,y;..."
                                    for pair in coords.split(';'):
                                        if pair:
                                            x, y = pair.split(',')
                                            points.append({'x': int(x), 'y': int(y)})
                                else:
                                    logger.warning(f"   Formato de coordenadas desconocido: {type(coords)}")
                                
                                if points:
                                    logger.debug(f"   ✅ Coordenadas parseadas: {points}")
                                    return points
                                else:
                                    logger.warning("   anticaptcha devolvió coordenadas pero no se pudieron parsear")
                                    return None
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
def solve_funcaptcha_2captcha(page_url, site_key, surl=None):
    """Resuelve FunCaptcha usando 2captcha, probando múltiples configuraciones."""
    if not API_KEY_2CAPTCHA:
        return None

    # Lista de configuraciones a probar (surl)
    configs_to_try = [
        {'surl': None, 'desc': 'sin surl'},
        {'surl': surl, 'desc': f'surl={surl}'} if surl else None,
        {'surl': 'https://amazon-api.arkoselabs.com', 'desc': 'surl=https://amazon-api.arkoselabs.com'},
        {'surl': 'https://client-api.arkoselabs.com', 'desc': 'surl=https://client-api.arkoselabs.com'}
    ]
    configs_to_try = [c for c in configs_to_try if c is not None]

    for config in configs_to_try:
        data = {
            'key': API_KEY_2CAPTCHA,
            'method': 'funcaptcha',
            'publickey': site_key,
            'pageurl': page_url,
            'json': 1
        }
        if config['surl']:
            data['surl'] = config['surl']
        
        logger.debug(f"   Probando 2captcha con {config['desc']}")
        try:
            resp = requests.post('http://2captcha.com/in.php', data=data, timeout=30)
            result = resp.json()
            if result.get('status') != 1:
                logger.warning(f"   2captcha error: {result}")
                continue
            captcha_id = result['request']
            logger.debug(f"   FunCaptcha ID: {captcha_id}, esperando...")
            start_time = time.time()
            while time.time() - start_time < 120:
                time.sleep(5)
                res = requests.get(f'http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={captcha_id}&json=1', timeout=10)
                if res.status_code != 200:
                    continue
                res_data = res.json()
                if res_data.get('status') == 1:
                    token = res_data['request']
                    logger.debug(f"   ✅ Token obtenido con {config['desc']}")
                    return token
                elif res_data.get('request') == 'CAPCHA_NOT_READY':
                    continue
                else:
                    break
        except Exception as e:
            logger.warning(f"   Error en intento con {config['desc']}: {e}")
            continue
    return None

def solve_funcaptcha_anticaptcha(page_url, site_key, surl=None):
    """Resuelve FunCaptcha usando AntiCaptcha, con la clase correcta (FunCaptchaTaskProxyless)."""
    if not API_KEY_ANTICAPTCHA:
        return None
    try:
        # Intentar con la clase sin proxy (más rápida)
        from anticaptchaofficial.funcaptchaproxyless import FunCaptchaTaskProxyless
        solver = FunCaptchaTaskProxyless()
    except ImportError:
        try:
            # Fallback a la versión con proxy (más lenta)
            from anticaptchaofficial.funcaptchaproxyon import funcaptchaProxyOn
            solver = funcaptchaProxyOn()
            logger.debug("   Usando AntiCaptcha con proxy (funcaptchaProxyOn)")
        except ImportError as e:
            logger.warning(f"AntiCaptcha library not installed: {e}. Install with: pip install anticaptchaofficial")
            return None

    surls_to_try = [None, surl, 'https://amazon-api.arkoselabs.com', 'https://client-api.arkoselabs.com']
    for test_surl in surls_to_try:
        try:
            solver.set_verbose(0)
            solver.set_key(API_KEY_ANTICAPTCHA)
            solver.set_website_url(page_url)
            solver.set_website_key(site_key)
            if test_surl:
                solver.set_data('surl', test_surl)
            logger.debug(f"   Probando AntiCaptcha con surl={test_surl}")
            token = solver.solve_and_return_solution()
            if token:
                logger.debug(f"   ✅ Token obtenido con AntiCaptcha (surl={test_surl})")
                return token
            else:
                logger.warning(f"   AntiCaptcha error: {solver.error_code} (surl={test_surl})")
        except Exception as e:
            logger.warning(f"   Error con AntiCaptcha (surl={test_surl}): {e}")
            continue
    return None

async def extract_site_key_robust(page):
    """
    Extrae el site_key de la página 'Confirma tu identidad' usando múltiples estrategias,
    incluyendo esperar a que el iframe cargue su contenido.
    Retorna (site_key, surl)
    """
    site_key = None
    surl = None

    # --- Estrategia 0: Esperar a que el iframe principal tenga un src válido ---
    iframe = None
    for _ in range(10):  # hasta 10 segundos
        iframe = await page.query_selector('#cvf-aamation-challenge-iframe')
        if iframe:
            src = await iframe.get_attribute('src')
            if src and src != 'about:blank':
                break
        await page.wait_for_timeout(1000)
    else:
        logger.debug("   No se encontró iframe con src válido después de esperar")

    # --- Estrategia 1: Buscar en el script de ACIC (data-external-id) ---
    page_content = await page.content()
    # UUID con guiones
    uuid_match = re.search(r'"data-external-id":\s*"([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})"', page_content, re.IGNORECASE)
    if uuid_match:
        site_key = uuid_match.group(1)
        logger.debug(f"   Site_key (UUID) desde script: {site_key}")
    else:
        # Alfanumérico largo (20+ caracteres)
        alnum_match = re.search(r'"data-external-id":\s*"([A-Za-z0-9]{20,})"', page_content)
        if alnum_match:
            site_key = alnum_match.group(1)
            logger.debug(f"   Site_key (alfanumérico) desde script: {site_key}")

    # --- Estrategia 2: Buscar en el iframe (atributo o src) ---
    if iframe:
        # Atributo data-external-id
        if not site_key:
            site_key = await iframe.get_attribute('data-external-id')
            if site_key:
                logger.debug(f"   Site_key desde iframe data-external-id: {site_key}")
        # Parámetro pk en src
        src = await iframe.get_attribute('src')
        if src:
            match = re.search(r'[?&]pk=([A-Za-z0-9]{20,})', src)
            if match:
                site_key = match.group(1)
                logger.debug(f"   Site_key desde src pk: {site_key}")
            # Extraer surl del src si es URL completa
            surl_match = re.search(r'surl=([^&]+)', src)
            if surl_match:
                surl_candidate = surl_match.group(1)
                if surl_candidate.startswith('http'):
                    surl = surl_candidate
                    logger.debug(f"   Surl desde src: {surl}")
                else:
                    logger.debug(f"   Surl no válido: {surl_candidate}")

    # --- Estrategia 3: Buscar en frames anidados (game-core-frame) ---
    for frame in page.frames:
        if 'game-core' in frame.name or 'arkoselabs' in frame.url:
            try:
                # Buscar data-external-id dentro del frame
                ext_id = await frame.evaluate('() => document.querySelector("[data-external-id]")?.getAttribute("data-external-id")')
                if ext_id and not site_key:
                    site_key = ext_id
                    logger.debug(f"   Site_key desde frame interno: {site_key}")
                # Buscar en el src del frame
                frame_url = frame.url
                if frame_url:
                    match = re.search(r'[?&]pk=([A-Za-z0-9]{20,})', frame_url)
                    if match and not site_key:
                        site_key = match.group(1)
                        logger.debug(f"   Site_key desde frame url pk: {site_key}")
                    # También buscar surl en el frame
                    surl_match = re.search(r'surl=([^&]+)', frame_url)
                    if surl_match and surl_match.group(1).startswith('http'):
                        surl = surl_match.group(1)
                        logger.debug(f"   Surl desde frame: {surl}")
            except Exception as e:
                logger.debug(f"   Error accediendo a frame: {e}")

    # --- Estrategia 4: Si aún no hay site_key, intentar obtenerlo de la URL de la página (a veces viene en 'public_key') ---
    if not site_key:
        current_url = page.url
        match = re.search(r'[?&]public_key=([A-Za-z0-9-]+)', current_url)
        if match:
            site_key = match.group(1)
            logger.debug(f"   Site_key desde URL: {site_key}")

    return site_key, surl













async def handle_captcha_if_present(page, step_name="captcha"):
    """
    Detecta y resuelve captchas de Amazon.
    Para captcha de coordenadas, puede resolver múltiples veces (si aparece "Necesarios: X").
    Para FunCaptcha, intenta múltiples estrategias.
    """
    logger.debug(f"🔍 Verificando captcha en paso: {step_name}")
    await page.wait_for_timeout(3000)
    # ---------- 1. CAPTCHA DE COORDENADAS SIMPLIFICADO ----------
    content = await page.content()
    coordinate_indicators = ["Resuelve esta adivinanza", "Elija todo", "Selecciona todas las imágenes", "Seleccione todo"]
    if any(indicator in content for indicator in coordinate_indicators):
        logger.warning("⚠️ Captcha de coordenadas detectado")
        
        max_global_attempts = 100
        attempt_count = 0
        
        while attempt_count < max_global_attempts:
            attempt_count += 1
            logger.debug(f"   Intento global #{attempt_count}")
            
            # Intentar resolver el canvas actual (4 peticiones, comparación)
            success = await solve_coordinate_captcha(page, "coord", round_num=attempt_count)
            
            if not success:
                # No se obtuvo consenso: refrescar canvas
                logger.warning("   No hay consenso entre respuestas, refrescando canvas...")
                await click_refresh_button(page)
                await page.wait_for_timeout(3000)
                continue
            
            # Si solve_coordinate_captcha retornó True (hizo clic), esperar un momento y verificar si hubo error o cambio
            await page.wait_for_timeout(1500)
            
            # Verificar mensajes de error
            error_incorrecto = await page.query_selector('.a-alert-content:has-text("Incorrecto"), div:has-text("Incorrecto")')
            error_timeout = await page.query_selector('.a-alert-content:has-text("superado el límite de tiempo"), div:has-text("límite de tiempo")')
            if error_incorrecto or error_timeout:
                tipo = "incorrectas" if error_incorrecto else "timeout"
                logger.warning(f"   ❌ Error detectado: coordenadas {tipo}, esperando 6seg al nuevo canvas...")
                await page.wait_for_timeout(6000)
                continue
            
            # Esperar cambio de canvas o pantalla de éxito (hasta 10 segundos)
            change = await wait_for_canvas_change(page, timeout=8)
            if change == 'sms' or change == 'register':
                logger.debug("   ✅ Captcha completado! Pantalla SMS/registro alcanzada.")
                return True
            elif change == 'login':
                raise Exception("AMAZON_REDIRECTED_TO_LOGIN")
            elif change == 'new_canvas':
                logger.debug("   Nuevo canvas detectado, continuando...")
                # No necesitamos leer progreso, simplemente seguimos el bucle
                continue
            else:
                logger.warning("   No se detectó cambio ni éxito, probando próximo canvas...")
                await page.wait_for_timeout(5000)
                continue
        
        raise Exception(f"Demasiados intentos ({max_global_attempts}) sin completar el captcha de coordenadas")
    # ---------- 2. FUNCAPTCHA (ARKOSE) ----------
    title = await page.title()

    if "Confirma tu identidad" in title or "Verify your identity" in title:
        logger.debug("   Página 'Confirma tu identidad' detectada")
        await page.wait_for_timeout(3000)


        # Verificar si realmente hay un FunCaptcha (iframe de Arkose o script ACIC)
        page_content = await page.content()
        has_arkose = bool(re.search(r'acic\.setupACIC', page_content)) or \
                     bool(await page.query_selector('#cvf-aamation-challenge-iframe'))
        
        if not has_arkose:
            # No es un FunCaptcha, es probablemente la página de verificación de número (WhatsApp)
            logger.debug("   No se detectó FunCaptcha real. Asumiendo que es página de verificación SMS/WhatsApp.")
            return False

        # --- Extracción inicial (puede fallar) ---
        site_key, surl = await extract_site_key_robust(page)
        if site_key:
            logger.debug(f"   Intentando resolver FunCaptcha con site_key: {site_key}")
            token = solve_funcaptcha_2captcha(page.url, site_key, surl)
            if not token and API_KEY_ANTICAPTCHA:
                token = solve_funcaptcha_anticaptcha(page.url, site_key, surl)
            if token:
                await page.evaluate(f"""
                    document.getElementById('cvf_aamation_response_token').value = '{token}';
                    document.getElementById('cvf-aamation-challenge-form').submit();
                """)
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                return True
            else:
                logger.warning("   Falló resolución directa, buscando botón...")
        else:
            logger.debug("   No se encontró site_key, buscando botón 'Iniciar rompecabezas'...")

        # --- Función interna para buscar botón en todos los frames ---
        async def find_button_in_frames(frame_list):
            for frame in frame_list:
                for sel in [
                    'button:has-text("Iniciar rompecabezas")',
                    'button[aria-label="Iniciar rompecabezas"]',
                    'button:has-text("Start puzzle")',
                    'button[aria-label="Start puzzle"]',
                    '.button:has-text("Iniciar rompecabezas")'
                ]:
                    try:
                        btn = await frame.query_selector(sel)
                        if btn:
                            return frame, btn
                    except:
                        continue
                if frame.child_frames:
                    res = await find_button_in_frames(frame.child_frames)
                    if res:
                        return res
            return None, None

        # --- Buscar botón con espera activa (hasta 20 segundos) ---
        start_button = None
        target_frame = None
        for _ in range(20):
            target_frame, start_button = await find_button_in_frames(page.frames)
            if start_button:
                break
            await page.wait_for_timeout(1000)

        if start_button:
            logger.debug("   ✅ Botón 'Iniciar rompecabezas' encontrado, haciendo clic...")
            await start_button.click()
            await page.wait_for_timeout(5000)

            # Esperar a que el iframe principal tenga src
            iframe = await page.wait_for_selector('#cvf-aamation-challenge-iframe', timeout=15000)
            src = await iframe.get_attribute('src')
            if not src or src == 'about:blank':
                for _ in range(10):
                    src = await iframe.get_attribute('src')
                    if src and src != 'about:blank':
                        break
                    await page.wait_for_timeout(1000)

            # Re‑extraer site_key después del clic
            site_key, surl = await extract_site_key_robust(page)
            if not site_key:
                # Intentar extraer del iframe directamente
                if iframe:
                    site_key = await iframe.get_attribute('data-external-id')
                    if not site_key and src:
                        match = re.search(r'[?&]pk=([A-Za-z0-9]{20,})', src)
                        if match:
                            site_key = match.group(1)
            if not site_key:
                screenshot = await take_screenshot(page, "funcaptcha_no_sitekey_after_click")
                raise Exception("FUNCAPTCHA_NO_SITEKEY")

            logger.debug(f"   🔑 Site_key obtenido tras clic: {site_key}")
            token = solve_funcaptcha_2captcha(page.url, site_key, surl)
            if not token and API_KEY_ANTICAPTCHA:
                token = solve_funcaptcha_anticaptcha(page.url, site_key, surl)
            if token:
                await page.evaluate(f"""
                    document.getElementById('cvf_aamation_response_token').value = '{token}';
                    document.getElementById('cvf-aamation-challenge-form').submit();
                """)
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                logger.debug("   ✅ FunCaptcha resuelto tras clic")
                return True
            else:
                screenshot = await take_screenshot(page, "funcaptcha_no_token_after_click")
                raise Exception("FUNCAPTCHA_NO_TOKEN")
        else:
            # No se encontró botón en 20 segundos
            logger.warning("   ❌ No se encontró botón 'Iniciar rompecabezas' después de 20 segundos. Lanzando excepción.")
            screenshot = await take_screenshot(page, "funcaptcha_button_not_found")
            raise Exception("FUNCAPTCHA_NOT_DETECTED")

    return False




# ===================================================================
# NUEVA FUNCIÓN: Hacer clic en botón de refrescar captcha
# ===================================================================
async def click_refresh_button(page):
    """Busca y hace clic en el botón 'Obtenga un nuevo rompecabezas' con timeout de 2 segundos."""
    refresh_selectors = [
        'button#amzn-btn-refresh-internal',
        'button:has-text("Obtenga un nuevo rompecabezas")',
        'button:has-text("New puzzle")',
        'button.btn-icon',
        'button[aria-label="Obtener un nuevo rompecabezas"]',
        'button[aria-label="New puzzle"]'
    ]
    for selector in refresh_selectors:
        try:
            btn = await page.wait_for_selector(selector, timeout=2000)
            if btn and await btn.is_visible():
                await btn.click()
                logger.debug(f"   🔄 Clic en botón de refrescar ({selector})")
                await page.wait_for_timeout(2000)  # espera que cargue
                return True
        except Exception:
            continue
    logger.debug("   ⚠️ No se encontró botón de refrescar, continuando sin refrescar")

    error_incorrecto = await page.query_selector('.a-alert-content:has-text("Incorrecto"), div:has-text("Incorrecto. Vuelva a intentarlo.")')
    if error_incorrecto:
        logger.warning("❌ Error detectado: coordenadas incorrectas. Reintentando internamente...")
    raise Exception("AMAZON_CAPTCHA_ERROR")


    return False




# ===================================================================
# FUNCIÓN MODIFICADA: solve_coordinate_captcha con 4 peticiones y validación
# ===================================================================
async def solve_coordinate_captcha(page, step_name="coordinate", round_num=1):
    """
    Lanza N peticiones (ej. 8) y recolecta respuestas.
    En cuanto se obtengan M respuestas válidas (5 puntos y 5 celdas distintas) que coincidan,
    cancela el resto y hace clic.
    Parámetros configurables abajo.
    """
    # ========== CONFIGURACIÓN ==========
    NUM_REQUESTS = 8          # número de peticiones paralelas
    MIN_MATCHES = 3           # coincidencias requeridas
    TIMEOUT = 50              # segundos máximo total
    # ==================================

    logger.debug(f"   Resolviendo captcha: {NUM_REQUESTS} peticiones, buscando {MIN_MATCHES} coincidencias (timeout {TIMEOUT}s)")

    # --- Obtener canvas y bounding box ---
    try:
        canvas = await page.wait_for_selector('canvas', timeout=20000)
        if not canvas:
            raise Exception("Canvas no encontrado")
        screenshot_bytes = await canvas.screenshot()
        img_path = f'temp_canvas_{round_num}.png'
        with open(img_path, 'wb') as f:
            f.write(screenshot_bytes)
        box = await canvas.bounding_box()
        if not box or box['width'] == 0:
            raise Exception("Bounding box inválida")
    except Exception as e:
        logger.error(f"Error canvas: {e}")
        await take_screenshot(page, f"{step_name}_error")
        raise Exception(f"Error canvas: {e}")

    hint = "Haz clic en todas las imágenes que contengan el objeto indicado"

    async def fetch_one():
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, solve_anticaptcha_coordinates, img_path, hint)

    # --- Función para convertir puntos a celdas (grid 3x3) ---
    def coords_to_cells(points, canvas_size=333, cell_size=105, gap=6):
        cells = set()
        cell_total = cell_size + gap
        for p in points:
            col = p['x'] // cell_total
            row = p['y'] // cell_total
            if col > 2: col = 2
            if row > 2: row = 2
            cells.add(row * 3 + col)
        return cells

    # --- Variables para recolectar resultados ---
    valid_responses = []          # lista de (celdas_tuple, puntos)
    tasks = [asyncio.create_task(fetch_one()) for _ in range(NUM_REQUESTS)]
    pending = tasks.copy()
    start_time = time.time()
    best_cells_tuple = None
    best_points = None

    # --- Bucle de espera dinámica ---
    while pending and (time.time() - start_time) < TIMEOUT:
        # Esperar la primera tarea que termine (timeout 1s para no saturar)
        done, pending = await asyncio.wait(pending, timeout=1, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                points = task.result()
            except Exception as e:
                logger.debug(f"   Tarea falló: {e}")
                continue
            # Validar: exactamente 5 puntos y 5 celdas distintas
            if points and len(points) == 5:
                cells = coords_to_cells(points)
                if len(cells) == 5:
                    cells_tuple = tuple(sorted(cells))
                    logger.debug(f"   Respuesta válida: celdas {cells_tuple}")
                    valid_responses.append((cells_tuple, points))
                    # Contar frecuencias
                    from collections import Counter
                    counter = Counter(cell_set for cell_set, _ in valid_responses)
                    most_common, count = counter.most_common(1)[0]
                    if count >= MIN_MATCHES:
                        logger.debug(f"   ✅ Alcanzadas {count} coincidencias. Usando celdas {most_common}")
                        best_cells_tuple = most_common
                        # Obtener los puntos de la primera respuesta que tenga esas celdas
                        for c, pts in valid_responses:
                            if c == best_cells_tuple:
                                best_points = pts
                                break
                        # Cancelar todas las tareas pendientes
                        for t in pending:
                            t.cancel()
                        pending = []
                        break
                else:
                    logger.debug(f"   Respuesta descartada: {len(points)} puntos pero {len(cells)} celdas distintas")
            else:
                logger.debug(f"   Respuesta descartada: {len(points) if points else 0} puntos")
        if best_points:
            break

    # Cancelar tareas restantes si aún hay
    for t in pending:
        t.cancel()

    # Si no se alcanzó consenso
    if not best_points:
        logger.warning(f"   No se alcanzaron {MIN_MATCHES} coincidencias tras {len(valid_responses)} respuestas válidas")
        return False

    # --- Hacer clic en las coordenadas del consenso ---
    logger.debug(f"   Haciendo clic en celdas: {best_cells_tuple}")
    for point in best_points:
        abs_x = box['x'] + point['x']
        abs_y = box['y'] + point['y']
        await page.mouse.click(abs_x, abs_y)
        await asyncio.sleep(0.2)

    confirm_btn = await page.query_selector('button:has-text("Confirmar"), input[value="Confirmar"], button[type="submit"]')
    if confirm_btn:
        await confirm_btn.click()
        logger.debug("   Botón Confirmar clickeado")
        await page.wait_for_load_state('domcontentloaded', timeout=10000)
        await page.wait_for_timeout(2000)
        return True
    else:
        logger.warning("   No se encontró botón Confirmar, asumiendo éxito")
        return True  
async def wait_for_sms_code_with_retry(service_name, service_id, page, timeout_total=120, resend_interval=40):
    """
    Espera el código SMS hasta timeout_total segundos.
    Cada resend_interval segundos intenta hacer clic en el enlace de reenviar (si existe).
    Retorna el código o None.
    """
    start = time.time()
    last_resend = start  
    while time.time() - start < timeout_total:
        # Intentar obtener el código del servicio
        code = None
        for s in SMS_SERVICES:
            if s['name'] == service_name and s['enabled']:
                # Verificar cada 3 segundos (no saturar)
                code = await s['get_code'](service_id, timeout=3)
                if code:
                    return code
                break
        # Si ha pasado el intervalo de reenvío, intentar hacer clic
        if time.time() - last_resend >= resend_interval:
            try:
                resend_link = await page.query_selector('a#cvf-resend-link')
                if resend_link and await resend_link.is_visible():
                    await resend_link.click()
                    logger.debug(f"🔄 Reenviado código a los {int(time.time()-start)}s")
                    last_resend = time.time()
            except Exception as e:
                logger.debug(f"Error al reenviar: {e}")
        await asyncio.sleep(3)
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
    Si force_service está presente, solo intenta ese servicio.
    Si force_country está presente, intenta ese país primero y luego el resto del orden (sin duplicados).
    De lo contrario, sigue el orden por precio de cada servicio.
    """
    # Prefijos para extraer número local (dígitos después del código país)
    prefix_len = {'ID': 2, 'MX': 2, 'US': 1, 'CA': 1, 'UK': 2, 'DE': 2, 'FR': 2,
                  'IT': 2, 'ES': 2, 'JP': 2, 'AU': 2, 'IN': 2}
    prefix_len_plus = {'ID': 3, 'MX': 3, 'US': 2, 'CA': 2, 'UK': 3, 'DE': 3, 'FR': 3,
                  'IT': 3, 'ES': 3, 'JP': 3, 'AU': 3, 'IN': 3, 'KG': 3, 'PL': 3, 'CO': 3, 'LV': 3, 'PK': 3, 'TJ': 3, 'KE': 3}

    # Mapeo de códigos de país a números para Hero SMS
    hero_country_map = {
        'BR': 73,   # Brazil +55
        'CM': 41,   # Cameroon +237
        'MY': 7,    # Malaysia +60
        'KZ': 2,    # Kazakhstan +7
        'ID': 6,    # Indonesia +62
        'MA': 37,   # Morocco +212
        'KG': 11,   # Kyrgyzstan +996
        'CO': 33,   # Colombia +57
        'MX': 54,   # México +52
    }

    # Orden de países por precio (barato a caro) para Hero
    hero_order = HERO_COUNTRY_ORDER 


    # Para 5sim, obtener precios reales
    fivesim_prices = await get_fivesim_prices()
    if fivesim_prices:
        fivesim_order = list(fivesim_prices.keys())  # ya ordenado por precio
    else:
        fivesim_order = FIVESIM_MANUAL_ORDER

    # -------------------------------------------------------------------
    # Caso 1: Se fuerza un servicio y un país específico
    # -------------------------------------------------------------------
    if force_service and force_country:
        logger.debug(f"🔒 Forzando servicio={force_service}, país={force_country} (primero, luego resto del orden)")
        target_service = None
        for s in SMS_SERVICES:
            if s['name'] == force_service and s['enabled']:
                target_service = s
                break
        if not target_service:
            logger.warning(f"   ❌ Servicio {force_service} no disponible")
            return None

        # Construir la lista de países a probar: primero el forzado, luego el resto del orden sin duplicados
        if force_service == 'hero':
            full_order = hero_order
        elif force_service == '5sim':
            full_order = fivesim_order
        else:
            full_order = [account_country]

        # Crear lista ordenada: force_country primero, luego los demás en el orden original (sin repetir)
        countries_to_try = [force_country]
        for c in full_order:
            if c != force_country:
                countries_to_try.append(c)

        for purchase_country in countries_to_try:
            logger.debug(f"   Probando país {purchase_country} (servicio forzado {force_service})...")
            try:
                if force_service == 'hero':
                    country_num = hero_country_map.get(purchase_country)
                    if not country_num:
                        logger.debug(f"   No hay mapeo Hero para {purchase_country}")
                        continue
                    result = await target_service['get_number'](country_num, service='am')
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
                            'service_name': force_service,
                            'purchase_country': purchase_country
                        }
                elif force_service == '5sim':
                    result = await target_service['get_number'](purchase_country, product='amazon')
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
                            'service_name': force_service,
                            'purchase_country': purchase_country
                        }
            except Exception as e:
                logger.warning(f"   Error con {force_service} en {purchase_country}: {e}")
                continue
        return None

    # -------------------------------------------------------------------
    # Caso 2: Se fuerza solo el servicio (sin país): iterar sobre todos los países de ese servicio
    # -------------------------------------------------------------------
    if force_service and not force_country:
        logger.debug(f"🔒 Forzando solo servicio={force_service} (probando todos los países en orden)")
        target_service = None
        for s in SMS_SERVICES:
            if s['name'] == force_service and s['enabled']:
                target_service = s
                break
        if not target_service:
            logger.warning(f"   ❌ Servicio {force_service} no disponible")
            return None

        # Obtener el orden de países para ese servicio
        if force_service == 'hero':
            country_order = hero_order
        elif force_service == '5sim':
            country_order = fivesim_order
        else:
            country_order = [account_country]

        for purchase_country in country_order:
            logger.debug(f"   Probando país {purchase_country} (servicio forzado {force_service})...")
            try:
                if force_service == 'hero':
                    country_num = hero_country_map.get(purchase_country)
                    if not country_num:
                        continue
                    result = await target_service['get_number'](country_num, service='am')
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
                            'service_name': force_service,
                            'purchase_country': purchase_country
                        }
                elif force_service == '5sim':
                    result = await target_service['get_number'](purchase_country, product='amazon')
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
                            'service_name': force_service,
                            'purchase_country': purchase_country
                        }
            except Exception as e:
                logger.warning(f"   Error con {force_service} en {purchase_country}: {e}")
                continue
        return None

    # -------------------------------------------------------------------
    # Caso 3: Sin fuerza: iterar sobre servicios y países normalmente
    # -------------------------------------------------------------------
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


async def get_captcha_progress(page):
    """
    Extrae el texto de progreso del captcha de coordenadas.
    Retorna (resolved, needed) como enteros. Si no encuentra, devuelve (0, 3).
    """
    content = await page.content()
    # Español
    match = re.search(r'Resueltos:\s*(\d+)\s*(?:de|Necesarios:)\s*(\d+)', content, re.IGNORECASE)
    if match:
        resolved = int(match.group(1))
        needed = int(match.group(2))
        logger.debug(f"📊 Progreso captcha (ES): {resolved}/{needed}")
        return resolved, needed
    # Inglés
    match_en = re.search(r'Solved:\s*(\d+)\s*(?:of|Needed:)\s*(\d+)', content, re.IGNORECASE)
    if match_en:
        resolved = int(match_en.group(1))
        needed = int(match_en.group(2))
        logger.debug(f"📊 Captcha progress (EN): {resolved}/{needed}")
        return resolved, needed
    # No encontrado, asumir inicio
    logger.debug("📊 No se pudo leer el progreso, se asume 0/3")
    return 0, 3

async def wait_for_canvas_change(page, previous_canvas_id=None, timeout=5):
    """
    Espera a que el canvas cambie o aparezca éxito/error.
    Retorna:
      'new_canvas' - canvas diferente
      'sms' - campo de código
      'register' - formulario de registro
      'login' - página de login
      'error' - mensaje "Incorrecto..."
      None - timeout
    """
    start = time.time()
    if previous_canvas_id is None:
        canvas = await page.query_selector('canvas')
        if canvas:
            previous_canvas_id = await canvas.get_attribute('data-challenge-id')
            if not previous_canvas_id:
                box = await canvas.bounding_box()
                previous_canvas_id = f"{box['x']}_{box['y']}_{box['width']}_{box['height']}" if box else None
                logger.debug(f"   ID canvas inicial (bounding): {previous_canvas_id}")

    while time.time() - start < timeout:
        # 1. Error
        error_elem = await page.query_selector('.a-alert-content:has-text("Incorrecto"), div:has-text("Incorrecto. Vuelva a intentarlo.")')
        if error_elem:
            logger.debug("   ❌ Mensaje de error detectado")
            return 'error'

        # 2. SMS
        if await page.query_selector('#cvf-input-code, #cvf-input-otp, input[name="otpCode"]'):
            logger.debug("   📱 Campo SMS detectado")
            return 'sms'
        # 3. Registro
        if await page.query_selector('#ap_customer_name'):
            logger.debug("   📝 Formulario de registro detectado")
            return 'register'
        # 4. Login
        if await page.query_selector('#ap_email'):
            logger.warning("   🚫 Redirigido a login")
            return 'login'
        # 5. Cambio de canvas
        canvas = await page.query_selector('canvas')
        if canvas:
            current_id = await canvas.get_attribute('data-challenge-id')
            if not current_id:
                box = await canvas.bounding_box()
                current_id = f"{box['x']}_{box['y']}_{box['width']}_{box['height']}" if box else None
            if previous_canvas_id and current_id and current_id != previous_canvas_id:
                logger.debug(f"   🎨 Nuevo canvas detectado (ID antiguo: {previous_canvas_id[:30]}... nuevo: {current_id[:30]}...)")
                return 'new_canvas'
        await page.wait_for_timeout(500)
    logger.debug("   ⏱️ Timeout esperando cambio")
    return None

# --------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA CAPTURAR PANTALLA (optimizada)
# -------------------------------------------------------------------
async def take_screenshot(page, step_name):
    try:
        current_url = page.url
        screenshot_bytes = await page.screenshot(type='jpeg', quality=SCREENSHOT_QUALITY)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        logger.debug(f"📸 Screenshot tomado en paso: {step_name} | URL: {current_url[:100]} (tamaño: {len(screenshot_bytes)} bytes)")
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
# FUNCIÓN PRINCIPAL DE CREACIÓN DE CUENTA (OPTIMIZADA CON REINTENTOS INTERNOS)
# -------------------------------------------------------------------
async def create_amazon_account(country_code, add_address_flag=True, max_retries=None, max_internal_retries=10):
      # Si no se pasa max_retries, usar el global
    retries = max_retries if max_retries is not None else MAX_RETRIES
    logger.debug(f"🏁 Iniciando creación de cuenta para {country_code} (reintentos: {retries})")

    for global_attempt in range(1, retries + 1):
        logger.debug(f"🔄 Intento global {global_attempt}/{retries}")
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
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-features=BlockInsecurePrivateNetworkRequests',
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

            # ----- BUCLE DE REINTENTO INTERNO (para FunCaptcha, misma IP, hasta 10 intentos) -----
            internal_attempt = 0
            registration_success = False
            last_error = None

            while internal_attempt < max_internal_retries and not registration_success:
                internal_attempt += 1
                logger.debug(f"🔄 Intento interno {internal_attempt}/{max_internal_retries} (misma IP)")

                if internal_attempt > 1:
                    # Cerrar página actual y abrir una nueva en el mismo contexto
                    await page.close()
                    page = await context.new_page()
                    await page.route('**/*', block_resources)

                try:


                    
                    # ----- PASO 7: Navegar a la URL base con reintentos -----
                    base_url = base_urls[country_code]
                    max_nav_retries = 3
                    nav_success = False
                    last_error = None
                    for nav_attempt in range(1, max_nav_retries + 1):
                        try:
                            await page.route('**/*', block_heavy_resources)
                            await page.goto(base_url, wait_until='domcontentloaded', timeout=60000)
                            await page.wait_for_selector('a[data-nav-role="signin"]', timeout=15000)
                            nav_success = True
                            break
                        except Exception as nav_err:
                            last_error = nav_err
                            logger.warning(f"Navegación intento {nav_attempt} falló: {nav_err}")
                            if nav_attempt == max_nav_retries:
                                raise
                            await asyncio.sleep(5)
                            # Recargar la página (si ya existe) o crear una nueva
                            await page.close()
                            page = await context.new_page()
                            await page.route('**/*', block_heavy_resources)
                    if not nav_success:
                        raise Exception(f"No se pudo cargar la página después de {max_nav_retries} intentos: {last_error}")
                    
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


                    async def handle_registered_number(page, phone_info, service_id, service_name, country_code, 
                                   phone_field_selector, continue_selectors, account_data, 
                                   max_attempts=10):
                        """
                        Maneja el escenario donde el número actual ya está registrado en Amazon.
                        Busca el enlace 'Cambiar', obtiene un nuevo número (probando otros países si es necesario),
                        lo ingresa y hace clic en Continuar.
                        
                        Retorna (new_phone_info, new_service_id, new_service_name, new_purchase_country)
                        o lanza excepción si no se puede cambiar.
                        """
                        for attempt in range(1, max_attempts + 1):
                            logger.debug(f"   Intentando cambiar número (intento {attempt}/{max_attempts})...")
                            
                            # Verificar si la URL contiene "claim?" (número ya registrado) - en paso 10.3 ya estamos en esa página,
                            # pero en paso 15 puede ser diferente; por eso verificamos.
                            if "claim?" not in page.url.lower():
                                # Podría ser que ya estemos en la pantalla de verificación SMS con un número registrado
                                # pero no haya redirigido a claim; buscamos mensajes de error.
                                page_content = await page.content()
                                if "número de teléfono ya está en uso" in page_content or "already in use" in page_content:
                                    logger.debug("   Mensaje de número ya registrado detectado en la página.")
                                else:
                                    # Si no hay indicador claro, asumimos que no es necesario cambiar (salimos)
                                    logger.debug("   No se detectó número ya registrado, saliendo sin cambios.")
                                    return phone_info, service_id, service_name, phone_info.get('purchase_country')
                            
                            # --- Buscar enlace "Cambiar" ---
                            change_link = None
                            change_selectors = [
                                '#ap_change_login_claim',
                                'a:has-text("Cambiar")',
                                'a:has-text("Change")',
                                'a[href*="ap/signin"][href*="prepopulatedLoginId"]'
                            ]
                            for sel in change_selectors:
                                try:
                                    change_link = await page.wait_for_selector(sel, timeout=3000)
                                    if change_link:
                                        logger.debug(f"   ✅ Enlace 'Cambiar' encontrado con selector: {sel}")
                                        await change_link.click()
                                        logger.debug(f"   ✅ Enlace 'Cambiar' clickeado")

                                        break
                                except Exception:
                                    continue
                            
                            # Si no se encontró con selectores, extraer URL del HTML
                            if not change_link:
                                logger.debug("   🔍 No se encontró enlace con selectores, extrayendo URL del HTML...")
                                page_content = await page.content()
                                match = re.search(r'<a\s+id="ap_change_login_claim"[^>]*href="([^"]+)"', page_content)
                                if match:
                                    change_url = match.group(1).replace('&amp;', '&')
                                    logger.debug(f"   🌐 URL extraída: {change_url}")
                                    await page.goto(change_url, wait_until='domcontentloaded')
                                    await page.wait_for_selector(phone_field_selector, state='visible', timeout=10000)
                                    change_link = True  # Indicar que ya navegamos
                                else:
                                    logger.warning("   ❌ No se pudo encontrar el enlace 'Cambiar'")
                                    if attempt == max_attempts:
                                        raise Exception("No se pudo encontrar enlace para cambiar número después de varios intentos")
                                    else:
                                        continue
                            
                            # Cancelar la activación anterior del número
                            if service_id:
                                try:
                                    if service_name == 'hero':
                                        await cancel_hero_sms(service_id)
                                    elif service_name == '5sim':
                                        await cancel_fivesim(service_id)
                                except Exception as e:
                                    logger.debug(f"   ⚠️ Error cancelando número anterior: {e}")
                            
                            # Obtener nuevo número (mismo servicio, sin forzar país -> probará todos los países del servicio)
                            current_service = service_name
                            new_phone = await get_phone_number(country_code, force_service=current_service, force_country=None)
                            if not new_phone:
                                logger.warning(f"   ❌ No se pudo obtener otro número (intento {attempt})")
                                if attempt == max_attempts:
                                    raise Exception("No hay números disponibles para este servicio después de varios intentos")
                                else:
                                    continue
                            
                            # Actualizar variables del nuevo número
                            new_phone_info = new_phone
                            new_service_id = new_phone_info['service_id']
                            new_service_name = new_phone_info['service_name']
                            new_purchase_country = new_phone_info['purchase_country']
                            logger.debug(f"   ✅ Nuevo número obtenido: {new_phone_info['full']} (país: {new_purchase_country})")
                            
                            # Actualizar account_data
                            account_data['phone'] = new_phone_info['local']
                            account_data['purchase_country'] = new_purchase_country
                            
                            # Rellenar el nuevo número en el campo
                            phone_field = await page.wait_for_selector(phone_field_selector, timeout=10000)
                            await phone_field.fill('')
                            await phone_field.fill(new_phone_info['full'])
                            
                            # Hacer clic en Continuar
                            continue_clicked = False
                            for selector in continue_selectors:
                                if await smart_click(page, selector, timeout=5000, wait_for_navigation=True):
                                    continue_clicked = True
                                    break
                            if not continue_clicked:
                                logger.warning("   No se encontró botón Continuar, reintentando...")
                                if attempt == max_attempts:
                                    raise Exception("No se pudo hacer clic en Continuar después de cambiar número")
                                else:
                                    continue
                            
                            # Éxito: retornar la nueva información
                            return new_phone_info, new_service_id, new_service_name, new_purchase_country
                        
                        # Si sale del bucle sin éxito
                        raise Exception("No se pudo cambiar el número registrado después de varios intentos")


                    # ----- PASO 10.3: Manejar números ya registrados (bucle de cambio) -----
                    if "claim?" in page.url.lower():

                        logger.warning("⚠️ Número ya registrado detectado en el paso de registro.")
                        page_content = await page.content()
                        if "Lo sentimos" in page_content or "no podemos crear tu cuenta" in page_content:
                            logger.warning("   ❌ Página de error de Amazon detectada (Lo sentimos, no podemos crear tu cuenta). Lanzando excepción para reintento  .")
                            raise Exception("AMAZON_ERROR_LOSENTIMOS")
                        try:

                            phone_info, service_id, service_name, purchase_country = await handle_registered_number(
                                page, phone_info, service_id, service_name, country_code,
                                phone_field_selector, continue_selectors, account_data
                            )
                            # Actualizar también variables externas
                            account_data['phone'] = phone_info['local']
                            account_data['purchase_country'] = purchase_country
                            # Ahora ya tenemos un nuevo número, continuar con el flujo normal
                        except Exception as e:
                            logger.error(f"Error cambiando número registrado: {e}")
                            raise


                    # ----- PASO 10.5: Resolver captcha si aparece antes del envío -----
                    await handle_captcha_if_present(page, step_name="pre_submit")

                    # ----- PASO 11: Página intermedia "Proceder a crear una cuenta" -----
                    logger.debug("🔍 Verificando página intermedia...")

                    # Selector principal (el único que debería aparecer)
                    primary_selector = 'span#intention-submit-button input.a-button-input'

                    # Intentar hacer clic en el botón (si existe)
                    clicked = await smart_click(page, primary_selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=False)

                    if clicked:
                        # Si se hizo clic, esperar que aparezca el formulario de registro
                        try:
                            await page.wait_for_function('document.querySelector("#ap_customer_name") !== null', timeout=15000)
                            logger.debug("   ✅ Formulario de registro cargado después del clic")
                        except Exception as e:
                            raise Exception(f"Timeout esperando campo de nombre después del clic: {e}")
                    else:
                        # No se encontró el botón, verificar si es error de Amazon o redirección a login
                        logger.debug("   ⚠️ No se encontró el botón 'Proceder a crear una cuenta'")
                        # Obtener la URL actual y el contenido
                        current_url = page.url
                        page_content = await page.content()
                        
                        # Detectar si estamos en la página de login (campo de email)
                        is_login_page = await page.query_selector('#ap_email') is not None
                        
                        if is_login_page:
                            logger.warning("   🔄 Redirigido a la página de inicio de sesión antes de mandar forms. Reiniciando proceso interno.")
                            # Limpiar cookies? No, mejor lanzar excepción para que el bucle interno reinicie
                            raise Exception("AMAZON_REDIRECTED_TO_LOGIN")
                        elif "Lo sentimos" in page_content or "no podemos crear tu cuenta" in page_content:
                            logger.warning("   ❌ Página de error de Amazon detectada (Lo sentimos, no podemos crear tu cuenta). Lanzando excepción para reintento  .")
                            raise Exception("AMAZON_ERROR_LOSENTIMOS")
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















        





                    async def enviar_formulario_registro():
                        """Llena nombre, contraseñas, envía formulario y maneja reintentos/errores.
                           Retorna True si se llega a la página de verificación SMS."""
                        logger.debug("📝 Enviando formulario de registro (con reintentos)...")
                        # ---- Llenar nombre (solo una vez) ----
                        name_selectors = ['input#ap_customer_name', 'input[name="customerName"]']
                        name_filled = False
                        for sel in name_selectors:
                            if await smart_fill(page, sel, fullname):
                                name_filled = True
                                break
                        if not name_filled:
                            logger.warning("⚠️ No se pudo llenar campo de nombre, puede estar precargado")

                        # Asegurar existencia de campos de contraseña
                        await page.wait_for_selector('input#ap_password', state='visible', timeout=5000)
                        await page.wait_for_selector('input#ap_password_check', state='visible', timeout=5000)

                        # ---- Bucle de reintentos de ENVÍO (hasta 3 intentos) ----
                        max_submit_attempts = 3
                        submit_success = False
                        for submit_attempt in range(1, max_submit_attempts + 1):
                            if submit_attempt > 1:
                                logger.debug(f"   Reintentando envío (intento {submit_attempt})")
                                # Re-llenar contraseñas
                                await smart_fill(page, 'input#ap_password', password)
                                await smart_fill(page, 'input#ap_password_check', password)
                                await smart_fill(page, 'input[name="passwordCheck"]', password)
                            else:
                                await smart_fill(page, 'input#ap_password', password)
                                await smart_fill(page, 'input#ap_password_check', password)
                                await smart_fill(page, 'input[name="passwordCheck"]', password)

                            # Verificar contraseña
                            filled_pwd = await page.input_value('input#ap_password')
                            if not filled_pwd or len(filled_pwd) < 6:
                                continue

                            # Hacer clic en botón final
                            final_btn_selectors = [
                                'input#continue', 'input.a-button-input', 'button[type="submit"]',
                                'input[value*="Crear cuenta"]', 'button:has-text("Crear cuenta")',
                                'input[value*="Create account"]', 'button:has-text("Create account")'
                            ]
                            clicked = False
                            for sel in final_btn_selectors:
                                if await smart_click(page, sel, timeout=10000, wait_for_navigation=True):
                                    clicked = True
                                    break
                            if not clicked:
                                logger.warning("   No se encontró botón final")

                            await page.wait_for_timeout(3000)

                            # Resolver captcha post-submit
                            await handle_captcha_if_present(page, step_name="post_submit")

                            # Analizar errores
                            content = await page.content()
                            if "Detectamos actividad inusual" in content:
                                logger.warning("   🚫 ACTIVIDAD INUSUAL -> reinicio GLOBAL")
                                raise Exception("AMAZON_BLOCKED_ACCOUNT")
                            if "incorrecto o no válido" in content or "Introduzca un número de móvil válido" in content:
                                logger.warning(f"   NÚMERO INVÁLIDO (intento {submit_attempt}) -> rellenando número")
                                phone_field = await page.wait_for_selector(phone_field_selector, timeout=3000)
                                if phone_field:
                                    await phone_field.fill('')
                                    await phone_field.fill(phone_info['full'])
                                continue
                            if "Mínimo 6 caracteres requeridos" in content or "Minimo 6 caracteres requeridos" in content:
                                logger.warning(f"   CONTRASEÑA VACÍA (intento {submit_attempt}) -> reintentando")
                                continue
                            if "El número de teléfono móvil ya está en uso" in content or "El número de teléfono móvil ya está registrado" in content:
                                logger.warning("   NÚMERO YA REGISTRADO -> buscando botón 'Continuar con este número'")
                                continue_btn_selectors = [
                                    'button:has-text("Continuar con este número")',
                                    'input[value="Continuar con este número"]',
                                    'a:has-text("Continuar con este número")',
                                    'button:has-text("Continue with this number")'
                                ]
                                clicked = False
                                for sel in continue_btn_selectors:
                                    if await smart_click(page, sel, timeout=5000, wait_for_navigation=True):
                                        clicked = True
                                        break
                                if not clicked:
                                    logger.warning("   No se encontró botón, se asume que ya está en la página de verificación")
                                await page.wait_for_load_state('domcontentloaded', timeout=15000)
                                await page.wait_for_timeout(3000)
                                submit_success = True
                                break
                            # No hay errores
                            submit_success = True
                            break

                        if not submit_success:
                            raise Exception("No se pudo enviar el formulario de registro después de varios intentos")
                        return True





                    # ... (después de la página intermedia y captura de pantalla) ...
                    await enviar_formulario_registro()
                    last_screenshot = await take_screenshot(page, "despues_registro")










                    # =================================================================
                    # PASO 15: VERIFICACIÓN POR SMS (CON REINTENTOS POR PAÍS Y NÚMERO)
                    # =================================================================
                    logger.debug("📱 Verificación SMS con reintentos por país y número...")
                    await page.wait_for_timeout(5000)

                    # --- Obtener el servicio actual (hero o 5sim) y su lista de países ordenada ---
                    current_service = phone_info['service_name']
                    countries_to_try = []
                    if current_service == 'hero':
                        countries_to_try = HERO_COUNTRY_ORDER
                    elif current_service == '5sim':
                        # Para 5sim, obtener precios reales para ordenar por costo
                        fivesim_prices = await get_fivesim_prices()
                        if fivesim_prices:
                            countries_to_try = list(fivesim_prices.keys())
                        else:
                            countries_to_try = FIVESIM_MANUAL_ORDER
                    else:
                        countries_to_try = [country_code]

                    # Determinar el índice inicial del país (el que se usó actualmente)
                    current_country = phone_info['purchase_country']
                    try:
                        start_index = countries_to_try.index(current_country)
                    except ValueError:
                        start_index = 0

                    max_countries_to_try = min(3, len(countries_to_try))   # máximo 3 países diferentes
                    max_number_attempts_per_country = 2                    # intentos por país

                    sms_success = False
                    countries_tested = 0
                    country_idx = start_index

                    while countries_tested < max_countries_to_try and not sms_success:
                        test_country = countries_to_try[country_idx % len(countries_to_try)]
                        logger.debug(f"🌍 Probando país: {test_country} (intento de país {countries_tested+1}/{max_countries_to_try})")

                        for num_att in range(1, max_number_attempts_per_country + 1):
                            logger.debug(f"   📞 Intento de número #{num_att} para país {test_country}")

                            # Si no es el primer intento de este país, obtener un nuevo número
                            if num_att > 1 or (num_att == 1 and test_country != current_country):
                                # Cancelar el número anterior si existe
                                if 'service_id' in locals() and service_id:
                                    try:
                                        if current_service == 'hero':
                                            await cancel_hero_sms(service_id)
                                        elif current_service == '5sim':
                                            await cancel_fivesim(service_id)
                                    except Exception as e:
                                        logger.debug(f"   ⚠️ Error cancelando número anterior: {e}")

                                # Obtener nuevo número forzando servicio y país
                                new_phone_info = await get_phone_number(country_code, force_service=current_service, force_country=test_country)
                                if not new_phone_info:
                                    logger.warning(f"   ❌ No se pudo obtener número para país {test_country}")
                                    break   # pasar al siguiente país

                                # Actualizar variables
                                phone_info = new_phone_info
                                account_data['phone'] = phone_info['local']
                                service_id = phone_info['service_id']
                                service_name = phone_info['service_name']
                                purchase_country = phone_info['purchase_country']
                                logger.debug(f"   ✅ Nuevo número obtenido: {phone_info['full']} (país: {purchase_country})")

                                # --- Navegar de nuevo al formulario de registro (cambiar número) ---
                                # Buscar enlace "Cambiar"
                                change_link_found = False
                                for sel in ['a:has-text("Cambiar")', 'a[href*="/ap/register?"]', 'a[href*="sign_in_otp_change"]']:
                                    try:
                                        change_link = await page.wait_for_selector(sel, timeout=5000)
                                        if change_link:
                                            await change_link.click()
                                            await page.wait_for_load_state('domcontentloaded', timeout=15000)
                                            change_link_found = True
                                            break
                                    except:
                                        continue
                                if not change_link_found:
                                    logger.warning("   ⚠️ No se encontró enlace 'Cambiar', asumiendo que ya estamos en la pantalla de número")

                                # Rellenar nuevo número
                                phone_field = await page.wait_for_selector(phone_field_selector, timeout=10000)
                                await phone_field.fill('')
                                await phone_field.fill(phone_info['full'])
                                # Hacer clic en Continuar
                                continue_clicked = False
                                for sel in ['input.a-button-input', 'button#continue']:
                                    if await smart_click(page, sel, wait_for_navigation=True):
                                        continue_clicked = True
                                        break
                                if not continue_clicked:
                                    raise Exception("No se encontró botón Continuar después de cambiar número")

                                # Esperar la página intermedia "Proceder a crear una cuenta"
                                await page.wait_for_timeout(3000)
                                primary_selector = 'span#intention-submit-button input.a-button-input'
                                if not await smart_click(page, primary_selector, wait_for_navigation=False):
                                    await page.wait_for_timeout(4000)

                                # Reenviar el formulario de registro
                                await enviar_formulario_registro()
                                # Después de esto, la página debería estar en la pantalla de verificación SMS (con el nuevo número)

                            # --- Ahora esperar el código SMS ---
                            # Manejar posible página de WhatsApp
                            content = await safe_get_content(page)
                            if "Verificar con WhatsApp" in content or "Enviar código por SMS" in content:
                                logger.warning("📱 WhatsApp detectado, seleccionando SMS...")
                                sms_option = await page.query_selector('#secondary_channel_button input.a-button-input')
                                if not sms_option:
                                    sms_option = await page.query_selector('#secondary_channel_button')
                                if sms_option:
                                    await sms_option.click()
                                    logger.debug("   Clic en 'Enviar código por SMS'")
                                    await page.wait_for_load_state('load', timeout=15000)

                            # Esperar campo de código
                            try:
                                code_input = await page.wait_for_selector('#cvf-input-code', state='visible', timeout=30000)
                            # Dentro del bucle for num_att in range(1, max_number_attempts_per_country + 1):
                            # ... después de intentar obtener code_input ...
                            except Exception as e:
                                error_msg = await page.query_selector('.a-alert-content, .a-alert-error')
                                if error_msg:
                                    error_text = await error_msg.text_content()
                                    if "No se puede enviar un mensaje SMS" in error_text or "Verifica a través de WhatsApp" in error_text:
                                        logger.warning(f"⚠️ SMS no disponible para {test_country} (intento {num_att})")
                                        # Hacer clic en "Verificar usando WhatsApp" para poder acceder al enlace "Cambiar"
                                        whatsapp_btn = await page.query_selector('#secondary_channel_button input.a-button-input')
                                        if not whatsapp_btn:
                                            whatsapp_btn = await page.query_selector('#secondary_channel_button')
                                        if whatsapp_btn:
                                            await whatsapp_btn.click()
                                            logger.debug("   ✅ Clic en 'Verificar usando WhatsApp'")
                                            await page.wait_for_load_state('load', timeout=15000)
                                            await page.wait_for_timeout(3000)
                                        else:
                                            logger.warning("   ⚠️ No se encontró botón de WhatsApp, continuando...")
                                        
                                        # Ahora buscar el enlace "Cambiar" y hacer clic (para cambiar de número)
                                        change_link = None
                                        for sel in ['a:has-text("Cambiar")', 'a[href*="/ap/register?"]', 'a[href*="sign_in_otp_change"]']:
                                            try:
                                                change_link = await page.wait_for_selector(sel, timeout=5000)
                                                if change_link:
                                                    await change_link.click()
                                                    logger.debug("   🔄 Enlace 'Cambiar' clickeado")
                                                    await page.wait_for_load_state('domcontentloaded', timeout=15000)
                                                    break
                                            except:
                                                continue
                                        if not change_link:
                                            logger.warning("   ⚠️ No se encontró enlace 'Cambiar', se usará la navegación directa...")
                                            # Opcional: navegar a la URL de registro directamente (menos fiable)
                                        
                                        # Cancelar el número actual
                                        try:
                                            if service_name == 'hero':
                                                await cancel_hero_sms(service_id)
                                            elif service_name == '5sim':
                                                await cancel_fivesim(service_id)
                                        except Exception as cancel_err:
                                            logger.debug(f"   ⚠️ Error cancelando número: {cancel_err}")
                                        
                                        # No llamamos a cambiar_numero_y_reiniciar, simplemente hacemos continue
                                        # para que el bucle externo (num_att) intente con otro número del mismo país
                                        # Nota: al hacer continue, saltamos el resto del código de este intento y volvemos al inicio del for,
                                        # donde se incrementará num_att y se obtendrá un nuevo número (porque num_att > 1 o test_country != current_country)
                                        continue
                                    else:
                                        logger.error(f"❌ Error inesperado: {error_text}")
                                        raise Exception(f"Error en verificación SMS: {error_text}")
                                else:
                                    raise Exception(f"Campo de código no apareció: {e}")

                            # Esperar código SMS (con reenvío automático)
                            sms_code = await wait_for_sms_code_with_retry(service_name, service_id, page, timeout_total=120, resend_interval=40)
                            if sms_code:
                                # Limpiar campo e ingresar código
                                await code_input.fill('')
                                await code_input.fill(sms_code)
                                logger.debug(f"   ✅ Código SMS ingresado: {sms_code}")
                                verify_btn = await page.query_selector('input[type="submit"], button:has-text("Verificar"), button:has-text("Verify")')
                                if verify_btn:
                                    await verify_btn.click()
                                    await page.wait_for_load_state('domcontentloaded', timeout=15000)
                                    if 'your-account' in page.url.lower() or 'account' in page.url.lower():
                                        logger.debug("   ✅ Registro exitoso después de SMS.")
                                        sms_success = True
                                        break
                                    else:
                                        logger.warning("   Código incorrecto o no redirigió, reintentando...")
                                        continue
                                else:
                                    logger.warning("   No se encontró botón de verificar")
                            else:
                                logger.warning(f"⏰ No se recibió código en 2 minutos (intento {num_att})")
                                # Falló este número, continuar con el siguiente número del mismo país

                        # Incrementar contador de países probados y pasar al siguiente país
                        countries_tested += 1
                        country_idx += 1

                    if not sms_success:
                        raise Exception("Verificación SMS fallida después de probar varios países y números")





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

                        registration_success = True
                        return account_data, None, last_screenshot
                    else:
                        raise Exception(f"Registro fallido, URL: {page.url}")

                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    # Capturamos cualquier excepción relacionada con FunCaptcha para reintentar internamente
                    if "SMS_TIME_OUT" in error_str or "AMAZON_CAPTCHA_ERROR" in error_str or "FUNCAPTCHA_NO_SITEKEY" in error_str or "FUNCAPTCHA_NO_TOKEN" in error_str or "FUNCAPTCHA_NOT_DETECTED" in error_str or "AMAZON_REDIRECTED_TO_LOGIN" in error_str or "AMAZON_SINENLACE_TRASCAMBIAR" in error_str or "AMAZON_ERROR_LOSENTIMOS" in error_str or "UNKNOWN_STATE_AFTER_CAPTCHA" in error_str or "SMS_UNAVAILABLE_RETRY" in error_str:
                        logger.warning(f"Fallo recuperable (intento interno {internal_attempt}), reiniciando en nueva pestaña...")
                        continue
                    else:
                        # Otro error, salir del bucle interno y propagar
                        logger.error(f"Error no recuperable en intento interno {internal_attempt}: {e}")
                        raise

            if not registration_success:
                raise last_error

        except Exception as e:
            logger.error(f"❌ Error en intento global {global_attempt}: {e}")
            if global_attempt == retries:
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
async def generate_cookie_api(country, add_address=True, max_retries=None, max_internal_retries=10):
    logger.debug(f"🚀 generate_cookie_api llamada con country={country}, add_address={add_address}, max_retries={max_retries}")
    try:
        if country not in base_urls:
            return {'success': False, 'error': f'País no soportado: {country}', 'country': country, 'screenshot': None}
        account_data, error_msg, screenshot = await create_amazon_account(country, add_address_flag=add_address, max_retries=max_retries, max_internal_retries=max_internal_retries)
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
CORS(app, origins=['https://ciberterroristaschk.shop', 'https://silver-chinchilla-366445.hostingersite.com'], methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"], supports_credentials=True)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://silver-chinchilla-366445.hostingersite.com')
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
    max_retries = data.get('max_retries', None)   # Nuevo parámetro opcional
    max_internal_retries = data.get('max_internal_retries', 10)   # nuevo parámetro
    if not country:
        return jsonify({'success': False, 'error': 'Falta el parámetro country'}), 400

    # Verificar créditos si hay token de usuario
    if user_token:
        ok, msg, role = check_user_credits(user_token, 4)
        if not ok:
            return jsonify({'success': False, 'error': msg}), 402
    # Si no hay token, podría ser una llamada desde el bot (que ya descuenta aparte) o desde otro servicio
    else:
        # Si no hay token, es una llamada desde el bot (que ya descuenta aparte)
        role = None  # No sabemos el rol, pero el bot ya maneja créditos

    # Verificar interruptor global (solo si no es admin)
    if role != 'admin':
        enabled = is_service_enabled()
        if not enabled:
            return jsonify({'success': False, 'error': 'Servicio deshabilitado temporalmente. Contacta al administrador.'}), 503
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(generate_cookie_api(country, add_address, max_retries, max_internal_retries))
        if result['success'] and user_token:
            success, new_credits = deduct_credits(user_token, 4) # Descontar 4 créditos por la generación de cookie (ajustable)
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
                        print(f"   Cookie: {data['cookie_string']}")
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