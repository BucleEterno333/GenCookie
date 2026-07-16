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

from asyncio.log import logger
from curses.ascii import US
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
import capsolver
from curl_cffi import requests as curl_requests
import concurrent.futures
import itertools
import os
from typing import Tuple, List, Dict, Optional
from faker import Faker
import urllib.parse
from bs4 import BeautifulSoup
import threading



# Forzar UTF-8 en la salida
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# -------------------------------------------------------------------
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO (con valores por defecto)
# -------------------------------------------------------------------
CAPTCHA_PROVIDER = os.getenv('CAPTCHA_PROVIDER', '2captcha')
CAPSOLVER_API_KEY = os.getenv('CAPSOLVER_API_KEY', '')
API_KEY_2CAPTCHA = os.getenv('API_KEY_2CAPTCHA', '')
API_KEY_ANTICAPTCHA = os.getenv('API_KEY_ANTICAPTCHA', '')
PROXY_STRING = os.getenv('PROXY_STRING', '')
HERO_SMS_API_KEY = os.getenv('HERO_SMS_API_KEY', '')
HERO_SMS_COUNTRY = os.getenv('HERO_SMS_COUNTRY', 'us')
HERO_SMS_OPERATOR = os.getenv('HERO_SMS_OPERATOR', 'any') 
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8080'))
API_KEY = os.getenv('API_KEY', '')
BOT_API_KEY = os.getenv('BOT_API_KEY', '')
FIVESIM_API_KEY = os.getenv('FIVESIM_API_KEY', '')
SERVICE_API_KEY = os.getenv('SERVICE_API_KEY', '')
API_BASE_URL = os.getenv('API_BASE_URL', '')
HERO_SMS_API_KEY_BACKUP  = os.getenv('HERO_SMS_API_KAYY', '')
HERO_SMS_API_KEY_BACKUP2  = os.getenv('HERO_SMS_API_KOYYY', '')
HERO_SMS_KEYS = [k for k in [HERO_SMS_API_KEY, HERO_SMS_API_KEY_BACKUP, HERO_SMS_API_KEY_BACKUP2 ] if k]

# ----- Timeouts configurables (en segundos) -----
WAIT_TIMEOUT = int(os.getenv('WAIT_TIMEOUT', '10'))          # Espera general para elementos
NAVIGATION_TIMEOUT = int(os.getenv('NAVIGATION_TIMEOUT', '60'))  # Espera de navegación
ACTION_TIMEOUT = int(os.getenv('ACTION_TIMEOUT', '5'))          # Espera para acciones específicas (clics, llenado)
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '10'))               # Reintentos globales

SERVICE_BLOCKED_UNTIL = 0
SERVICE_BLOCKED_REASON = None  # 'sms_temp' o 'admin'

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


TIMEOUT_SMS = int(os.getenv('TIMEOUT_SMS', '300'))   # <--- NUEVA LÍNEA


_SMS_API = "https://hero-sms.com/stubs/handler_api.php"
PROXY_LIST = []

# 5 APIs de mail temporal con sus formatos específicos
_MAIL_APIS = [
    {
        "name": "tmailor",
        "base": "https://tmailor.com/api",
        "create": lambda: (
            "POST",
            "https://tmailor.com/api",
            {"action": "newemail", "curentToken": "", "fbToken": None}
        ),
        "inbox": lambda token: (
            "POST",
            "https://tmailor.com/api",
            {"action": "listinbox", "accesstoken": token, "fbToken": None, "curentToken": token}
        ),
        "read": lambda token, msg_id: (
            "POST",
            "https://tmailor.com/api",
            {"action": "read", "accesstoken": token, "email_code": msg_id["id"], "email_token": msg_id["email_id"], "fbToken": None, "curentToken": token}
        ),
        "get_email": lambda data: data.get("email"),
        "get_token": lambda data: data.get("accesstoken"),
        "has_messages": lambda data: bool(data.get("data")),
        "get_messages": lambda data: list(data.get("data", {}).values()),
        "get_msg_id": lambda msg: {"id": msg["id"], "email_id": msg["email_id"]},
        "get_body": lambda data: data.get("data", {}).get("body", ""),
        "check_errors": lambda data: None,
    },
    {
        "name": "mailtm",
        "base": "https://api.mail.tm",
        "create": lambda: (
            "POST",
            "https://api.mail.tm/accounts",
            {"address": None, "password": "Pass1234!"},
            {"Content-Type": "application/json"}
        ),
        "inbox": lambda token: (
            "GET",
            f"https://api.mail.tm/messages?page=1",
            None,
            {"Authorization": f"Bearer {token}"}
        ),
        "read": lambda token, msg_id: (
            "GET",
            f"https://api.mail.tm/messages/{msg_id['id']}",
            None,
            {"Authorization": f"Bearer {token}"}
        ),
        "get_email": lambda data: data.get("address"),
        "get_token": lambda data: data.get("token") or data.get("jwt"),
        "has_messages": lambda data: bool(data.get("hydra:member") or data.get("data")),
        "get_messages": lambda data: data.get("hydra:member") or data.get("data", []),
        "get_msg_id": lambda msg: {"id": msg["id"]},
        "get_body": lambda data: data.get("text") or data.get("body", ""),
        "check_errors": lambda data: None,
        "pre_create": lambda sess: None,
    },
    {
        "name": "10minutemail",
        "base": "https://10minutemail.com",
        "create": lambda: (
            "GET",
            "https://10minutemail.com/session/address",
            None,
            None
        ),
        "inbox": lambda token: (
            "GET",
            f"https://10minutemail.com/messages/messagesAfter/0",
            None,
            None
        ),
        "read": lambda token, msg_id: (
            "GET",
            f"https://10minutemail.com/messages/{msg_id['id']}",
            None,
            None
        ),
        "get_email": lambda data: data.get("address") or data.get("mail"),
        "get_token": lambda data: data.get("token") or data.get("session"),
        "has_messages": lambda data: isinstance(data, list) and len(data) > 0,
        "get_messages": lambda data: data if isinstance(data, list) else [],
        "get_msg_id": lambda msg: {"id": msg.get("id", msg.get("messageId", 0))},
        "get_body": lambda data: data.get("body") or data.get("html", ""),
        "check_errors": lambda data: None,
    },
    {
        "name": "guerrillamail",
        "base": "https://www.guerrillamail.com",
        "create": lambda: (
            "GET",
            "https://www.guerrillamail.com/ajax.php?f=get_email_address&ip=127.0.0.1&agent=Mozilla",
            None,
            None
        ),
        "inbox": lambda token: (
            "GET",
            f"https://www.guerrillamail.com/ajax.php?f=get_email_list&offset=0&sid_token={token}",
            None,
            None
        ),
        "read": lambda token, msg_id: (
            "GET",
            f"https://www.guerrillamail.com/ajax.php?f=fetch_email&email_id={msg_id['id']}&sid_token={token}",
            None,
            None
        ),
        "get_email": lambda data: data.get("email_addr"),
        "get_token": lambda data: data.get("sid_token"),
        "has_messages": lambda data: bool(data.get("list")),
        "get_messages": lambda data: data.get("list", []),
        "get_msg_id": lambda msg: {"id": msg.get("mail_id")},
        "get_body": lambda data: data.get("mail_body") or data.get("body", ""),
        "check_errors": lambda data: None,
    },
]


# Orden de países para Hero SMS (barato a caro, según tu preferencia)
HERO_COUNTRY_ORDER = ['CA', 'KZ', 'ID', 'MA', 'KG', 'CO', 'MX', 'BR', 'CM']

FIVESIM_MANUAL_ORDER = ['CO', 'LV', 'PK', 'TJ', 'KE', 'MX']

# Mapeo de código de país ISO a número que espera Hero SMS
hero_country_map = {
    'CA': 36,    # Canadá +1
    'US': 187,   # USA +1
    'BR': 73,    # Brasil +55
    'CM': 41,    # Camerún +237
    'MY': 7,     # Malasia +60
    'KZ': 2,     # Kazajistán +7
    'ID': 6,     # Indonesia +62
    'MA': 37,    # Marruecos +212
    'KG': 11,    # Kirguistán +996
    'CO': 33,    # Colombia +57
    'MX': 54,    # México +52
}


# ========== EXCEPCIONES PERSONALIZADAS ==========
class SMSAccountBannedTemporarily(Exception):
    """Al menos una key de SMS está en ban temporal (CHANNELS_LIMIT)"""
    pass

class CAPSolverNoBalance(Exception):
    """La key de CapSolver tiene saldo insuficiente"""
    pass

class SMSNoBalance(Exception):
    """Todas las keys de SMS tienen saldo insuficiente (NO_BALANCE)"""
    pass

def verify_with_retry(phone, country_code, retries=3):
    """
    Verifica un número con reintentos en caso de error.
    Retorna True (registrado), False (disponible) o None (fallo total).
    """
    for attempt in range(1, retries + 1):
        result = is_phone_registered_sync(phone, country_code)
        if result is not None:
            return result  # Éxito: True o False
        logger.warning(f"   ⚠️ Intento {attempt}/{retries} falló para {phone}, reintentando en 2s...")
        time.sleep(2)
    return None  # Fallo total

def _is_banned_response(text: str) -> bool:
    """Detecta si la respuesta de Hero SMS es un BANNED."""
    try:
        data = json.loads(text)
        return data.get('title') == 'BANNED'
    except:
        return False

def extract_hidden_inputs(html):
    """Extrae todos los inputs ocultos de un formulario HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    hidden = {}
    for inp in soup.find_all('input', type='hidden'):
        name = inp.get('name')
        value = inp.get('value', '')
        if name:
            hidden[name] = value
    return hidden

def get_current_ip(sess):
    """Obtiene la IP actual"""
    try:
        ip = sess.get("https://api.ipify.org?format=json", timeout=10).json().get("ip", "Desconocida")
        return ip
    except:
        try:
            ip = sess.get("http://ipinfo.io/ip", timeout=10).text.strip()
            return ip
        except:
            return "No se pudo obtener IP"


def gen_profile() -> dict:
    """Genera perfil falso"""
    fake = Faker("en_US")
    first, last = fake.first_name(), fake.last_name()
    us = random.choice([
        {"street": "Broadway", "city": "Los Angeles", "state": "CA", "zip": "90001", "area": "213"},
        {"street": "Michigan Ave", "city": "Detroit", "state": "MI", "zip": "48226", "area": "313"},
        {"street": "Collins Ave", "city": "Denver", "state": "CO", "zip": "80202", "area": "303"},
        {"street": "Congress Ave", "city": "Austin", "state": "TX", "zip": "78701", "area": "512"},
        {"street": "Las Vegas Blvd", "city": "Las Vegas", "state": "NV", "zip": "89101", "area": "702"},
        {"street": "King St", "city": "Honolulu", "state": "HI", "zip": "96813", "area": "808"},
        {"street": "Canal St", "city": "New Orleans", "state": "LA", "zip": "70112", "area": "504"},
        {"street": "Broad St", "city": "Charlotte", "state": "NC", "zip": "28202", "area": "704"},
        {"street": "Rodeo Dr", "city": "Beverly Hills", "state": "CA", "zip": "90210", "area": "310"},
        {"street": "Park Ave", "city": "Phoenix", "state": "AZ", "zip": "85003", "area": "602"},
    ])
    ua = f"Mozilla/5.0 (Linux; Android {random.randint(10, 14)}; {random.choice(['Pixel 8', 'SM-S918B', 'SM-A556B', 'Redmi Note 12', 'Pixel 7a', 'moto g52', 'OnePlus 12', 'Galaxy A54'])}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(134, 147)}.0.0.0 Mobile Safari/537.36"
    return {
        "first_name": first, "last_name": last,
        "full_name": f"{first} {last}",
        "phone": f"{us['area']}555{random.randint(1000, 9999)}",
        "street": f"{random.randint(100, 999)} {us['street']}",
        "city": us["city"], "state": us["state"], "zip": us["zip"],
        "user_agent": ua,
    }


def find(string: str, start: str, end: str, strip: bool = True) -> str:
    """Extrae texto entre dos delimitadores"""
    try:
        result = string.split(start, 1)[1].split(end, 1)[0]
        return result.strip() if strip else result
    except (IndexError, AttributeError):
        raise ValueError(f"Capture failed: '{start}' -> '{end}' not found")


def capR(pattern: str, text: str) -> str:
    """Extrae con regex"""
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Extract failed: '{pattern}' not found")
    return match.group(1)


def capS(api_key: str, images: list, question: str) -> dict:
    """Resuelve captcha WAF"""
    capsolver.api_key = api_key
    return capsolver.solve({"type": "AwsWafClassification", "question": f"aws:grid:{question}", "images": images})

def bypass_waf(sess, captcha_url, aamation_id, client_ctx, json_opt, solver_key) -> str:
    """Bypassea WAF Amazon con reintentos internos ante errores de red."""
    import urllib.parse
    for attempt in range(5):
        try:
            j4 = sess.get(f"{captcha_url}/problem?kind=visual&domain=www.amazon.com&locale=en-US&problem=gridcaptcha-v2-5-0.1-0&num_solutions_required=1&id={aamation_id}").json()
            target = json.loads(j4["assets"]["target"])[0]
            images_raw = json.loads(j4["assets"]["images"])
            try:
                solved = capS(solver_key, images_raw, target).get("objects", [])
            except Exception as e:
                error_str = str(e)
                if "AuthenticationError" in error_str or "balance is insufficient" in error_str:
                    # Lanzar excepción específica para desactivar el servicio
                    raise CAPSolverNoBalance("CapSolver sin saldo o clave inválida")
                else:
                    logger.debug(f"* CapSolver Exception: {e}")
                    continue
            j5 = sess.post(f"{captcha_url}/verify", json={
                "state": {"iv": j4["state"]["iv"], "payload": j4["state"]["payload"]},
                "key": j4["key"], "hmac_tag": j4["hmac_tag"],
                "client_solution": solved,
                "metrics": {"solve_time_millis": random.randint(5000, 8000)},
                "locale": "en-us"
            }).json()
            if not j5.get("captcha_voucher"):
                logger.debug(f"* Captcha Failed => Attempt {attempt + 1}/5")
                continue
            captcha_jwt = j5["captcha_voucher"]
            jwt_client_id = json.loads(base64.urlsafe_b64decode(captcha_jwt.split(".")[1] + "=="))["client_id"]
            json6 = json.dumps({"challengeType": "WAF_ADVERSARIAL_SYNTHETIC_GRID_V2_LEVEL_1", "data": f'"{captcha_jwt}"'}, separators=(",", ":"))
            action_type = json.loads(sess.get(f"https://www.amazon.com/aaut/verify/cvf/{jwt_client_id}?context={urllib.parse.quote(client_ctx)}&options={urllib.parse.quote(json_opt)}&response={urllib.parse.quote(json6)}").headers.get("amz-aamation-resp")).get("actionType")
            logger.debug(f"* WAF Attempt {attempt + 1}/5 => {action_type}")
            if action_type == "PASS":
                return jwt_client_id
            
        except CAPSolverNoBalance:
            raise   # <--- NUEVA LÍNEA: propaga esta excepción
        except Exception as e:
            logger.debug(f"* WAF attempt {attempt+1} error: {e}")
            continue  # Reintenta en el siguiente intento
    raise Exception("WAF Failed After 5 Attempts")
# ===================================================================
# FUNCIÓN PARA CONTROLAR EL SERVICIO (activar/desactivar)
# ===================================================================
def set_service_enabled(enabled: bool) -> bool:
    global SERVICE_BLOCKED_UNTIL, SERVICE_BLOCKED_REASON

    if enabled:
        SERVICE_BLOCKED_UNTIL = 0
        SERVICE_BLOCKED_REASON = None
    else:
        # Si se desactiva, establecer un bloqueo en memoria (fallback)
        SERVICE_BLOCKED_UNTIL = time.time() + 3600  # 1 hora
        SERVICE_BLOCKED_REASON = 'capsolver_balance'  # o 'admin'

    try:
        headers = {
            'x-bot-key': BOT_API_KEY,
            'Content-Type': 'application/json'
        }
        payload = {'enabled': enabled}
        response = requests.post(f"{API_BASE_URL}/admin/bot/toggle-service", json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ Servicio de generación {'activado' if enabled else 'desactivado'} correctamente")
            return True
        else:
            logger.error(f"❌ Error al cambiar estado del servicio: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error al cambiar estado del servicio: {e}")
        return False
# ===================================================================
# get_number MODIFICADA CON LA NUEVA LÓGICA
# ===================================================================
def get_number(keys, country_code: str = None) -> Tuple[str, str, str]:
    """
    Prueba todas las keys SOLO EN EL PRIMER PAÍS de la lista (CA si no se especifica).
    Recolecta errores y al final:
      - Si alguna key tiene CHANNELS_LIMIT -> lanza SMSAccountBannedTemporarily.
      - Si todas tienen NO_BALANCE -> lanza SMSNoBalance.
      - Otros casos -> excepción genérica.
    """
    if isinstance(keys, str):
        keys = [keys]

    # Si no se especifica país, usar el primero de la lista (CA)
    if country_code:
        countries_to_try = [country_code]  # solo el país forzado
    else:
        countries_to_try = [HERO_COUNTRY_ORDER[0]]  # solo el primer país

    key_errors = {}

    for iso_code in countries_to_try:
        hero_country_num = hero_country_map.get(iso_code)
        if not hero_country_num:
            continue

        key_index = 0
        while key_index < len(keys):
            key = keys[key_index]
            logger.debug(f"  📞 Intentando país {iso_code} (código {hero_country_num}) con key {key[:4]}...")
            url = f"{_SMS_API}?api_key={key}&action=getNumber&service=am&country={hero_country_num}"
            try:
                r = requests.get(url, timeout=30).text

                if _is_banned_response(r):
                    if "CHANNELS_LIMIT" in r:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "CHANNELS_LIMIT")
                    else:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "BANNED")
                    logger.warning(f"⚠️ Key {key[:4]} baneada para {iso_code}: {r[:80]}")
                    key_index += 1
                    continue

                if r.startswith("ACCESS_NUMBER"):
                    _, activation_id, phone = r.split(":")
                    phone = phone.strip()
                    phone = phone.lstrip("1") if phone.startswith("1") and len(phone) == 11 else phone
                    logger.debug(f"  ✅ Número obtenido: {phone} (país {iso_code}) con key {key[:4]}")
                    return activation_id, phone, iso_code
                else:
                    if "NO_BALANCE" in r:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "NO_BALANCE")
                    elif "CHANNELS_LIMIT" in r:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "CHANNELS_LIMIT")
                    else:
                        key_errors[key] = _prioritize_error(key_errors.get(key), r[:80])
                    logger.debug(f"  ❌ Falló para {iso_code} con key {key[:4]}: {r[:80]}")
                    key_index += 1
            except Exception as e:
                logger.debug(f"  ❌ Error en {iso_code} con key {key[:4]}: {e}")
                key_index += 1

        logger.debug(f"  🔄 Agotadas todas las keys para {iso_code}")

    # ========== ANÁLISIS FINAL DE ERRORES ==========
    if not key_errors:
        raise Exception("No se pudo obtener número con ninguna key (sin errores específicos)")

    total_keys = len(keys)
    no_balance_count = sum(1 for err in key_errors.values() if "NO_BALANCE" in err)
    channels_limit_count = sum(1 for err in key_errors.values() if "CHANNELS_LIMIT" in err)

    # Caso 1: Todas las keys tienen NO_BALANCE
    if no_balance_count == total_keys:
        logger.error("❌ Todas las keys tienen NO_BALANCE. Apagando servicio indefinidamente.")
        raise SMSNoBalance("Saldo insuficiente en todas las cuentas de SMS. Avisar a administradores para recargar.")

    # Caso 2: Al menos una key tiene CHANNELS_LIMIT (y no todas son NO_BALANCE)
    if channels_limit_count > 0:
        logger.error(f"❌ Al menos una key tiene CHANNELS_LIMIT ({channels_limit_count} keys). Apagando servicio por 30 minutos.")
        raise SMSAccountBannedTemporarily("Al menos una cuenta de SMS está temporalmente baneada (límite de canales). El servicio se desactivará por 30 minutos.")

    # Caso 3: Otros errores (sin NO_BALANCE ni CHANNELS_LIMIT)
    error_summary = ", ".join([f"{key[:4]}: {err}" for key, err in key_errors.items()])
    raise Exception(f"No se pudo obtener número. Errores: {error_summary}")
def _prioritize_error(old: Optional[str], new: str) -> str:
    """Prioriza NO_BALANCE > CHANNELS_LIMIT > otros."""
    if not old:
        return new
    if "NO_BALANCE" in old:
        return old
    if "NO_BALANCE" in new:
        return new
    if "CHANNELS_LIMIT" in old:
        return old
    if "CHANNELS_LIMIT" in new:
        return new
    return new  # si ninguno es grave, devolver el nuevo



def get_code(keys, activation_id: str, timeout: int = TIMEOUT_SMS) -> str:
    if isinstance(keys, str):
        keys = [keys]

    for key in keys:
        start = time.time()
        while time.time() - start < timeout:
            url = f"{_SMS_API}?api_key={key}&action=getStatus&id={activation_id}"
            try:
                r = requests.get(url, timeout=30).text
                if _is_banned_response(r):
                    logger.warning(f"⚠️ Key {key[:4]} baneada en get_code, probando siguiente...")
                    break   # prueba la siguiente key
                if r.startswith("STATUS_OK"):
                    return r.split(":")[1].strip()
                if r == "STATUS_CANCEL":
                    raise Exception("SMS activation canceled")
                if "NO_BALANCE" in r:
                    logger.warning(f"⚠️ Key {key[:4]} sin saldo, probando siguiente...")
                    break
            except Exception as e:
                logger.debug(f"Error en get_code con key {key[:4]}: {e}")
            time.sleep(5)
    raise Exception("SMS timeout con todas las keys")


def set_status(keys, activation_id: str, status: int) -> None:
    if isinstance(keys, str):
        keys = [keys]

    for key in keys:
        url = f"{_SMS_API}?api_key={key}&action=setStatus&status={status}&id={activation_id}"
        try:
            r = requests.get(url, timeout=30).text
            if _is_banned_response(r):
                logger.warning(f"⚠️ Key {key[:4]} baneada en set_status, probando siguiente...")
                continue
            # Si no hubo error, asumimos éxito
            logger.debug(f"set_status con key {key[:4]} ejecutado (status {status})")
            return
        except Exception as e:
            logger.warning(f"Error en set_status con key {key[:4]}: {e}")
    logger.error("❌ No se pudo setStatus con ninguna key")

def _api_request(sess, method, url, json_data=None, headers=None, timeout=15):
    """Hace request a API de mail"""
    if headers is None:
        headers = {}
    
    if json_data:
        res = sess.request(method, url, json=json_data, headers=headers, timeout=timeout)
    else:
        res = sess.request(method, url, headers=headers, timeout=timeout)
    
    return res


def new_mail(sess, result_container):
    """Crea email temporal y guarda el resultado en el contenedor"""
    try:
        for api in _MAIL_APIS:
            try:
                method, url, data, *extra = api["create"]()
                headers = extra[0] if extra else {}
                
                res = _api_request(sess, method, url, data, headers)
                logger.debug(f"API {api['name']} - create status: {res.status_code}, body: {res.text[:200]}")

                if res.status_code not in [200, 201]:
                    continue
                
                resp_data = res.json()
                
                email = api["get_email"](resp_data)
                token = api["get_token"](resp_data)
                
                if email and token:
                    result_container["email"] = email
                    result_container["token"] = token
                    result_container["api"] = api["name"]
                    logger.debug(f"* Email creado: {email} ({api['name']})")
                    return
            except:
                continue
        result_container["error"] = "No se pudo crear email"
    except Exception as e:
        result_container["error"] = str(e)

def mail_code(sess, token: str, api_name: str, timeout: int = 120) -> str:
    """Obtiene código OTP del email"""
    # Buscar la API
    api = None
    for a in _MAIL_APIS:
        if a["name"] == api_name:
            api = a
            break
    
    if not api:
        raise Exception(f"API {api_name} no encontrada")
    
    logger.debug(f"* Esperando mail en {api['name']}...")
    
    for i in range(timeout // 5):
        time.sleep(5)
        try:
            method, url, data, *extra = api["inbox"](token)
            headers = extra[0] if extra else {}
            
            res = _api_request(sess, method, url, data, headers)
            logger.debug(f"API {api_name} - inbox status: {res.status_code}, body: {res.text[:200]}")  # <--- LÍNEA NUEVA

            resp_data = res.json()
            
            if not api["has_messages"](resp_data):
                if i % 6 == 0:
                    logger.debug(f"  Esperando... ({i*5}s)")
                continue
            
            messages = api["get_messages"](resp_data)
            if not messages:
                continue
            
            msg = messages[0]
            msg_id = api["get_msg_id"](msg)
            
            method, url, data, *extra = api["read"](token, msg_id)
            headers = extra[0] if extra else {}
            
            res2 = _api_request(sess, method, url, data, headers)
            logger.debug(f"API {api_name} - read status: {res2.status_code}, body: {res2.text[:200]}")  # <--- NUEVO
            body = str(api["get_body"](res2.json()))
            
            # Buscar OTP
            patterns = [
                r'class="data">(\d{6})</td>',
                r'">(\d{6})</',
                r'\b(\d{6})\b',
                r'OTP[:\s]*(\d{6})',
                r'code[:\s]*(\d{6,8})',
                r'verification[:\s]*(\d{6,8})',
                r'(\d{6})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, body, re.IGNORECASE)
                if match:
                    otp = match.group(1)
                    logger.debug(f"* OTP encontrado: {otp}")
                    return otp
            
        except Exception as e:
            logger.debug(f"  Error: {str(e)[:80]}")
            continue




    
    raise Exception(f"Mail OTP timeout en {api['name']}")

from playwright.async_api import async_playwright


import asyncio
from playwright.sync_api import sync_playwright  # o async, pero usaremos sync para simplicidad

import traceback
from playwright.sync_api import sync_playwright


def is_phone_registered_sync(phone_number: str, country_code: str = 'MX') -> Optional[bool]:
    """
    Verifica si un número ya está registrado en Amazon.
    Versión mejorada con reintentos, detección por texto y manejo de errores.
    Retorna: True=registrado, False=nuevo, None=error
    """
    logger.debug(f"📞 Verificando número {phone_number}...")
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("❌ Playwright no instalado")
        return None

    base_url = "https://www.amazon.com.mx"
    proxy_config = None
    if PROXY_HOST_PORT:
        proxy_config = {'server': f'http://{PROXY_HOST_PORT}'}
        if PROXY_AUTH:
            user, pwd = PROXY_AUTH.split(':', 1)
            proxy_config['username'] = user
            proxy_config['password'] = pwd

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            with sync_playwright() as p:
                launch_opts = {
                    'headless': True,
                    'args': [
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security'
                    ]
                }
                if proxy_config:
                    launch_opts['proxy'] = proxy_config

                browser = p.chromium.launch(**launch_opts)
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36'
                )
                page = context.new_page()

                # 1. Ir a amazon.com.mx
                logger.debug(f"   🌐 Navegando a {base_url}...")
                page.goto(base_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)

                # 2. Hacer clic en "Cuenta y Listas"
                logger.debug("   👤 Haciendo clic en #nav-link-accountList...")
                try:
                    page.click('#nav-link-accountList', timeout=15000)
                    page.wait_for_timeout(2000)
                except Exception as e:
                    logger.warning(f"   ⚠️ No se pudo hacer clic en #nav-link-accountList: {e}")
                    browser.close()
                    if attempt < max_attempts:
                        time.sleep(2)
                        continue
                    return None

                # 3. Llenar el campo de email
                logger.debug(f"   📱 Ingresando número: {phone_number}")
                try:
                    email_field = page.wait_for_selector('#ap_email, #ap_email_login', state='visible', timeout=10000)
                    if not email_field:
                        raise Exception("No se encontró campo de email")
                    email_field.fill(phone_number)
                    page.wait_for_timeout(1000)
                    page.click('#continue', timeout=5000)
                except Exception as e:
                    logger.warning(f"   ⚠️ Error al llenar email: {e}")
                    browser.close()
                    if attempt < max_attempts:
                        time.sleep(2)
                        continue
                    return None

                # 4. Esperar y detectar estado por texto
                page.wait_for_timeout(6000)
                content = page.content()

                # Detección por texto exacto
                if "Parece que eres nuevo en Amazon." in content:
                    logger.debug(f"   ✅ Número {phone_number} NUEVO (disponible)")
                    browser.close()
                    return False

                if "¿Ya tienes una cuenta?" in content or "Para iniciar sesión, ingresa tu contraseña." in content:
                    logger.debug(f"   ✅ Número {phone_number} YA REGISTRADO")
                    browser.close()
                    return True

                # Fallback a selectores
                if page.query_selector('#ap_password'):
                    logger.debug(f"   ✅ Número {phone_number} YA REGISTRADO (selector)")
                    browser.close()
                    return True

                if page.query_selector('#ap_customer_name'):
                    logger.debug(f"   ✅ Número {phone_number} NUEVO (selector)")
                    browser.close()
                    return False

                # Si no se detecta nada, asumir nuevo
                logger.warning(f"   ⚠️ Estado desconocido, asumiendo NUEVO")
                browser.close()
                return False

        except Exception as e:
            logger.error(f"❌ Error en intento {attempt}/{max_attempts} para {phone_number}: {e}")
            if attempt < max_attempts:
                time.sleep(2)
            else:
                return None

    return None  # Fallo total

async def is_phone_registered(phone_number, country_code='US'):
    """
    Verifica si un número de teléfono ya está registrado en Amazon.
    Retorna True si está registrado, False si es nuevo.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=random.choice(USER_AGENTS)
        )
        page = await context.new_page()
        
        # Ir a la página de login
        await page.goto("https://www.amazon.com/ap/signin")
        
        # Llenar el campo de email con el número (con prefijo internacional)
        await page.fill('#ap_email', phone_number)
        await page.click('#continue')
        
        # Esperar a que la página se estabilice
        await page.wait_for_timeout(3000)
        
        # Detectar si estamos en la página de registro (nuevo usuario)
        # o en la página de contraseña (usuario existente)
        content = await page.content()
        
        # Caso 1: si aparece el campo de contraseña, ya está registrado
        if await page.query_selector('#ap_password'):
            await browser.close()
            return True
        
        # Caso 2: si aparece el formulario de registro, es nuevo
        if await page.query_selector('#ap_customer_name'):
            await browser.close()
            return False
        
        # Caso 3: si aparece mensaje "No hemos podido encontrar una cuenta", no está registrado
        if "No hemos podido encontrar una cuenta" in content or "We cannot find an account" in content:
            await browser.close()
            return False
        
        # Caso 4: si hay captcha o algo inesperado, asumimos que no está registrado (o reintentamos)
        await browser.close()
        return False  # Por defecto, nuevo




def safe_request(sess, method, url, data=None, json_data=None, headers=None, max_retries=3, backoff=2):
    """
    Realiza una petición HTTP con reintentos en caso de errores SSL/red.
    """
    if headers is None:
        headers = {}
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            if method.upper() == 'GET':
                response = sess.get(url, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                if json_data is not None:
                    response = sess.post(url, json=json_data, headers=headers, timeout=30)
                else:
                    response = sess.post(url, data=data, headers=headers, timeout=30)
            else:
                raise ValueError(f"Método no soportado: {method}")

            # Si la respuesta es exitosa, devolverla
            if response.status_code in [200, 201, 302, 303]:
                return response
            else:
                logger.warning(f"Intento {attempt}: status {response.status_code} - {response.text[:100]}")
                # Si es error 4xx/5xx que no sea transitorio, lanzar excepción para no reintentar
                if response.status_code in [400, 401, 403, 404, 405, 406, 410]:
                    raise Exception(f"Error HTTP {response.status_code}: {response.text[:200]}")

        except Exception as e:
            last_exception = e
            logger.warning(f"Intento {attempt} falló: {e}")
            if attempt < max_retries:
                wait = backoff ** attempt
                logger.debug(f"Reintentando en {wait}s...")
                time.sleep(wait)
            else:
                raise Exception(f"Fallo después de {max_retries} intentos: {last_exception}")

    raise Exception("No se pudo completar la petición")

# ===================================================================
def process(capsolver_key, hero_keys, email=None, mail_token=None, mail_api=None,
            activation_id=None, sms_phone=None, proxy=None, t=None, country_code='BR'):
    """
    Genera una cuenta de Amazon usando el método rápido (curl_cffi + Capsolver).
    Propaga SMSAccountBannedTemporarily, CAPSolverNoBalance y SMSNoBalance.
    Al detectar actividad inusual (PERMANENT_UNUSUAL_ACTIVITY), reintenta con el
    mismo número (creando nueva sesión, lo que renueva la IP si el proxy es rotativo).
    """
    if t is None:
        t = time.time()

    max_intentos = 50
    max_num_intentos = 5
    MAX_REG_RETRIES = 20

    for intento in range(1, max_intentos + 1):
        # Si se pasa un proxy, se usará (puede ser rotativo, como smartproxy)
        # No es necesario modificar el proxy, solo crear nueva sesión en cada reintento.
        for num_attempt in range(1, max_num_intentos + 1):
            # ---------- OBTENER NÚMERO ----------
            try:
                activation_id, sms_phone, purchase_country = get_number(hero_keys)
                logger.debug(f"📞 Número obtenido: {sms_phone} (país {purchase_country})")
            except (SMSAccountBannedTemporarily, SMSNoBalance) as e:
                raise
            except Exception as e:
                logger.warning(f"⚠️ No se pudo obtener número: {e}")
                time.sleep(2)
                continue

            amazon_cc = {
                'CA': 'CA', 'US': 'US', 'MX': 'MX', 'BR': 'BR',
                'CM': 'CM', 'ID': 'ID', 'MA': 'MA', 'KG': 'KG', 'CO': 'CO', 'KZ': 'KZ'
            }.get(purchase_country, 'US')
            logger.debug(f"Usando código de país para Amazon: {amazon_cc}")

            registration_success = False

            # ---------- BUCLE DE REINTENTOS PARA EL MISMO NÚMERO ----------
            for reg_retry in range(1, MAX_REG_RETRIES + 1):
                try:
                    logger.debug(f"\n{'='*60}")
                    logger.debug(f"INTENTO EXTERNO #{intento} - NUM # {num_attempt} - REG RETRY #{reg_retry}")
                    logger.debug(f"{'='*60}")

                    info = gen_profile()
                    assoc_handle = "anywhere_v2_us"
                    arb = "88b7dd8f-6e15-491a-87df-9351dcbfc80f"
                    password = "dfbc1992"

                    # ---------- CREAR SESIÓN (nueva en cada reintento) ----------
                    sess = curl_requests.Session()
                    sess.impersonate = "chrome"
                    sess.headers.update({
                        "User-Agent": info["user_agent"],
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Upgrade-Insecure-Requests": "1",
                        "sec-ch-ua": '"Chromium";v="147", "Not?A_Brand";v="99"',
                        "sec-ch-ua-mobile": "?1",
                        "sec-ch-ua-platform": '"Android"',
                        "DNT": "1",
                    })

                    if proxy:
                        # Si el proxy es rotativo, cada nueva sesión obtendrá una IP diferente
                        sess.proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}

                    # ---------- EMAIL EN PARALELO ----------
                    mail_result = {}
                    mail_thread = threading.Thread(target=new_mail, args=(sess, mail_result))
                    mail_thread.start()

                    sess.get(f"https://www.amazon.com/ax/claim?arb={arb}")
                    mail_thread.join(timeout=10)

                    if "error" in mail_result:
                        raise Exception(f"Error creando email: {mail_result['error']}")

                    email = mail_result.get("email")
                    mail_token = mail_result.get("token")
                    mail_api = mail_result.get("api")

                    if not email:
                        raise Exception("No se pudo obtener email")

                    logger.debug(f"Email listo: {email} ({mail_api})")

                    # ---------- PRIMER POST ----------
                    data1 = {"arb": arb, "email": email, "claimCollectionLayoutType": "unifiedAuthClaimCollection"}
                    req1 = safe_request(
                        sess,
                        "POST",
                        "https://www.amazon.com/ap/register?openid.mode=checkid_setup"
                        "&openid.ns=http://specs.openid.net/auth/2.0"
                        "&openid.identity=http://specs.openid.net/auth/2.0/identifier_select"
                        "&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select"
                        "&openid.assoc_handle=anywhere_v2_us"
                        "&openid.return_to=https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button",
                        data=data1,
                        headers={"Referer": "https://www.amazon.com/ap/register", "Origin": "https://www.amazon.com"},
                        max_retries=3
                    )

                    if req1 is None or req1.status_code != 200 or "appActionToken" not in req1.text:
                        raise Exception("req1 falló")

                    appActionToken = find(req1.text, 'name="appActionToken" value="', '"')
                    workflowState = find(req1.text, 'name="workflowState" value="', '"')
                    openid_return_to = find(req1.text, 'name="openid.return_to" value="', '"')
                    prevRID = find(req1.text, 'name="prevRID" value="', '"')

                    # ---------- REGISTRO ----------
                    data2 = {
                        "appActionToken": appActionToken,
                        "appAction": "REGISTER",
                        "shouldShowPersistentLabels": "true",
                        "openid.return_to": openid_return_to,
                        "prevRID": prevRID,
                        "workflowState": workflowState,
                        "customerName": info["full_name"],
                        "email": email,
                        "password": password,
                        "showPasswordChecked": "true"
                    }

                    req2 = safe_request(
                        sess,
                        "POST",
                        "https://www.amazon.com/ap/register",
                        data=data2,
                        headers={"Referer": req1.url, "Origin": "https://www.amazon.com"},
                        max_retries=3
                    )

                    # ---------- DETECTAR ERRORES PERMANENTES ----------
                    if "already an account" in req2.text:
                        logger.debug("Email ya registrado")
                        raise Exception("PERMANENT_EMAIL_ALREADY_USED")

                    if "detected unusual activity" in req2.text:
                        logger.debug("Actividad inusual - Rotando proxy")
                        raise Exception("PERMANENT_UNUSUAL_ACTIVITY")

                    # ---------- WAF ----------
                    verifyToken = None
                    if "data-context" in req2.text and "data-external-id" in req2.text:
                        logger.debug("* Resolviendo WAF...")
                        verifyToken = find(req2.text, 'name="verifyToken" value="', '"')
                        dataExternalId = capR(r'"data-external-id":\s*"([^"]+)"', req2.text)
                        anti_csrf = find(req2.text, "name='anti-csrftoken-a2z' value='", "'")

                        json3 = json.dumps({
                            "clientData": json.dumps({
                                "sessionId": sess.cookies.get("session-id", ""),
                                "marketplaceId": "ATVPDKIKX0DER",
                                "clientUseCase": "/ap/register"
                            }, separators=(",", ":")),
                            "challengeType": "WAF_ADVERSARIAL_SYNTHETIC_GRID_V2_LEVEL_1",
                            "locale": "en-US",
                            "externalId": dataExternalId,
                            "enableHeaderFooter": False,
                            "enableBypassMechanism": False,
                            "enableModalView": False,
                            "eventTrigger": None,
                            "aaExternalToken": None,
                            "forceJsFlush": False,
                            "aamationToken": None,
                        }, separators=(",", ":"))

                        req3 = sess.get(f"https://www.amazon.com/aaut/verify/cvf?options={urllib.parse.quote(json3)}")
                        clientSideContext = json.loads(req3.headers.get("amz-aamation-resp")).get("clientSideContext")
                        aamation_id = capR(r'"id"\s*:\s*"([^"]+)"', req3.text)
                        captcha_url = capR(r'<script src="(https://ait\.[^"]+)/captcha\.js"', req3.text)
                        jwt_client_id = bypass_waf(sess, captcha_url, aamation_id, clientSideContext, json3, capsolver_key)

                        if not jwt_client_id:
                            raise Exception("WAF bypass falló")

                        logger.debug("WAF PASS")

                        data4 = {
                            "anti-csrftoken-a2z": anti_csrf,
                            "cvf_aamation_response_token": jwt_client_id,
                            "cvf_captcha_captcha_action": "verifyAamationChallenge",
                            "cvf_aamation_error_code": "",
                            "clientContext": sess.cookies.get("ubid-main"),
                            "openid.pape.max_auth_age": "900",
                            "openid.return_to": "https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button",
                            "forceMobileLayout": "1",
                            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
                            "openid.assoc_handle": assoc_handle,
                            "openid.mode": "checkid_setup",
                            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
                            "pageId": assoc_handle,
                            "openid.ns": "http://specs.openid.net/auth/2.0",
                            "shouldShowPersistentLabels": "true",
                            "verifyToken": verifyToken
                        }

                        req4 = safe_request(
                            sess,
                            "POST",
                            "https://www.amazon.com/ap/cvf/verify",
                            data=data4,
                            headers={
                                "Content-Type": "application/x-www-form-urlencoded",
                                "Referer": req2.url,
                                "Origin": "https://www.amazon.com"
                            },
                            max_retries=3
                        )

                        verifyToken = find(req4.text, 'name="verifyToken" value="', '"')
                        if not verifyToken:
                            verifyToken = find(req2.text, 'name="verifyToken" value="', '"')
                            if not verifyToken:
                                raise Exception("No se pudo obtener verifyToken")

                    # ---------- OTP EMAIL ----------
                    base_openid = {
                        "forceMobileLayout": "1",
                        "openid.assoc_handle": assoc_handle,
                        "openid.mode": "checkid_setup",
                        "language": "en_US",
                        "openid.ns": "http://specs.openid.net/auth/2.0",
                        "shouldShowPersistentLabels": "true"
                    }

                    otp_code = mail_code(sess, mail_token, mail_api)
                    logger.debug(f"OTP: {otp_code}")

                    data5 = {
                        **base_openid,
                        "autoReadStatus": "manual",
                        "verificationPageContactType": "email",
                        "action": "code",
                        "verifyToken": verifyToken,
                        "code": otp_code
                    }

                    req5 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data5)
                    anti_csrf = find(req5.text, "name='anti-csrftoken-a2z' value='", "'")
                    verifyToken = find(req5.text, 'name="verifyToken" value="', '"')

                    data6 = {
                        **base_openid,
                        "anti-csrftoken-a2z": anti_csrf,
                        "verifyToken": verifyToken,
                        "cvf_phone_cc": amazon_cc,
                        "cvf_phone_num": sms_phone,
                        "cvf_action": "collect"
                    }

                    req6 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data6)
                    logger.debug("* Esperando SMS...")
                    sms_code = get_code(hero_keys, activation_id)
                    logger.debug(f"SMS Code: {sms_code}")
                    set_status(hero_keys, activation_id, 6)

                    anti_csrf = find(req6.text, "name='anti-csrftoken-a2z' value='", "'")
                    verifyToken = find(req6.text, 'name="verifyToken" value="', '"')

                    data7 = {
                        **base_openid,
                        "anti-csrftoken-a2z": anti_csrf,
                        "verificationPageContactType": "sms",
                        "verifyToken": verifyToken,
                        "code": sms_code,
                        "cvf_action": "code",
                        "resendContactType": "sms"
                    }

                    req7 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data7)

                    if "entered already exists with another account" in req7.text:
                        logger.debug("Número ya registrado")
                        raise Exception("PERMANENT_NUMBER_ALREADY_REGISTERED")

                    if "new_account=1" not in req7.url:
                        logger.debug("Cuenta no creada")
                        raise Exception("REGISTRATION_FAILED")

                    # ---------- DIRECCIÓN ----------
                    logger.debug("* Agregando dirección...")

                    csrf_addr = urllib.parse.quote(find(req7.text, "name='csrfToken' value='", "'"))
                    customer_id = find(req7.text, 'name="address-ui-widgets-obfuscated-customerId" value="', '"')
                    wizard_id = find(req7.text, 'name="address-ui-widgets-address-wizard-interaction-id" value="', '"')
                    prev_token = find(req7.text, 'name="address-ui-widgets-previous-address-form-state-token" value="', '"')
                    widget_csrf = urllib.parse.quote(find(req7.text, 'name="address-ui-widgets-csrfToken" value="', '"'))
                    form_load = find(req7.text, 'name="address-ui-widgets-form-load-start-time" value="', '"')

                    sess.headers.update({
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": "https://www.amazon.com",
                        "Referer": req7.url,
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "same-origin",
                        "Sec-Fetch-User": "?1"
                    })

                    data8 = (
                        f"csrfToken={csrf_addr}&addressID="
                        f"&address-ui-widgets-addressFormButtonText=save"
                        f"&address-ui-widgets-addressFormHideHeading=true"
                        f"&address-ui-widgets-addressFormHideSubmitButton=false"
                        f"&address-ui-widgets-enableAddressDetails=true"
                        f"&address-ui-widgets-enableAddressWizardForm=true"
                        f"&address-ui-widgets-address-wizard-interaction-id={wizard_id}"
                        f"&address-ui-widgets-obfuscated-customerId={customer_id}"
                        f"&address-ui-widgets-csrfToken={widget_csrf}"
                        f"&address-ui-widgets-form-load-start-time={form_load}"
                        f"&address-ui-widgets-isAddressSuggestionsView=true"
                        f"&address-ui-widgets-suggested-address-selection=original-address-"
                        f"&original-address-address-ui-widgets-enterAddressFullName={urllib.parse.quote(info['full_name'])}"
                        f"&original-address-address-ui-widgets-enterAddressLine1={urllib.parse.quote(info['street'])}"
                        f"&original-address-address-ui-widgets-enterAddressLine2="
                        f"&original-address-address-ui-widgets-enterAddressCity={urllib.parse.quote(info['city'])}"
                        f"&original-address-address-ui-widgets-enterAddressStateOrRegion={info['state']}"
                        f"&original-address-address-ui-widgets-enterAddressPostalCode={info['zip']}"
                        f"&original-address-address-ui-widgets-countryCode=US"
                        f"&original-address-address-ui-widgets-enterAddressPhoneNumber={info['phone']}"
                        f"&address-ui-widgets-use-as-my-default=true"
                        f"&address-ui-widgets-previous-address-form-state-token={prev_token}"
                        f"&address-ui-widgets-saveOriginalOrSuggestedAddress=Submit+Query"
                    )

                    sess.post("https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button", data=data8)

                    cookies = "; ".join(f"{k}={v.replace(chr(34), chr(39))}" for k, v in sess.cookies.items())
                    elapsed = round(time.time() - t, 2)

                    logger.debug(f"\n{'='*60}")
                    logger.debug(f"CUENTA CREADA!")
                    logger.debug(f"{'='*60}")
                    logger.debug(f"Email:    {email}")
                    logger.debug(f"Password: {password}")
                    logger.debug(f"Phone:    {sms_phone}")
                    logger.debug(f"Tiempo:   {elapsed}s | Ext: {intento} | Num: {num_attempt} | Retry: {reg_retry}")
                    logger.debug(f"{'='*60}")
                    logger.debug(f"COOKIES:")
                    logger.debug(f"{cookies}")
                    logger.debug(f"{'='*60}\n")

                    registration_success = True
                    return {
                        "name": info["full_name"],
                        "phone": sms_phone,
                        "password": password,
                        "email": email,
                        "cookies": cookies,
                        "status": "Cuenta generada!",
                        "response": cookies,
                        "ip": get_current_ip(sess),
                        "time": elapsed,
                        "intentos": intento,
                        "num_attempts": num_attempt
                    }

                except CAPSolverNoBalance:
                    raise
                except (SMSAccountBannedTemporarily, SMSNoBalance):
                    raise
                except Exception as e:
                    error_str = str(e)
                    logger.debug(f"Error en reg_retry #{reg_retry}: {error_str}")

                    # ====== NUEVO: DETECTAR ACTIVIDAD INUSUAL ======
                    # Si es actividad inusual, reintentamos con nueva sesión (mismo número)
                    if "PERMANENT_UNUSUAL_ACTIVITY" in error_str or "detected unusual activity" in error_str.lower():
                        logger.debug("🔄 Actividad inusual detectada → reintentando con nueva sesión (mismo número)")
                        continue  # No cancelamos número, solo seguimos al siguiente reintento

                    # Para otros errores, mantener lógica anterior
                    permanent_keywords = [
                        "PERMANENT_EMAIL_ALREADY_USED",
                        "PERMANENT_NUMBER_ALREADY_REGISTERED",
                        "AMAZON_BLOCKED_ACCOUNT",
                        "already an account",
                        "entered already exists with another account",
                        "REGISTRATION_FAILED"
                    ]
                    is_permanent = any(kw in error_str for kw in permanent_keywords)

                    if is_permanent:
                        logger.debug(f"Error permanente, cancelando número y pasando al siguiente.")
                        if activation_id:
                            set_status(hero_keys, activation_id, 8)
                        break  # sale del bucle reg_retry → se comprará otro número
                    else:
                        # Error transitorio (red, timeout, etc.) → reintentar con misma sesión o nueva?
                        if reg_retry == MAX_REG_RETRIES:
                            logger.warning(f"Agotados reintentos para este número. Cancelando.")
                            if activation_id:
                                set_status(hero_keys, activation_id, 8)
                            break
                        else:
                            logger.debug(f"Reintentando con el mismo número (retry {reg_retry+1}/{MAX_REG_RETRIES})")
                            time.sleep(2)
                            continue

            # Si no se registró después de los reintentos, continuar con el siguiente número
            if not registration_success:
                continue
            else:
                # registration_success es True solo si se retornó antes
                pass

        # Si se agotaron los números para este proxy, cambiar proxy (siguiente intento)
        logger.debug(f"Se agotaron {max_num_intentos} números para el proxy actual, cambiando de proxy...")

    raise Exception(f"Se agotaron los {max_intentos} intentos externos")
async def generate_cookie_api(country, add_address=True, max_retries=None, max_internal_retries=10, force_playwright=False):
    logger.debug(f"🚀 generate_cookie_api llamada con country={country}, force_playwright={force_playwright}")
    global SERVICE_BLOCKED_UNTIL, SERVICE_BLOCKED_REASON

    try:
        if country not in base_urls:
            return {'success': False, 'error': f'País no soportado: {country}', 'country': country, 'screenshot': None}

        # ========== NUEVO: Si force_playwright está activado, saltar método rápido ==========
        if force_playwright:
            logger.debug("🔧 force_playwright activado: saltando método rápido y usando Playwright directamente.")
        else:
            # ---------- MÉTODO RÁPIDO ----------
            if CAPSOLVER_API_KEY and HERO_SMS_API_KEY and PROXY_STRING:
                logger.debug("🔧 Intentando método rápido (curl_cffi + Capsolver) de forma secuencial...")
                loop = asyncio.get_running_loop()
                max_attempts = 10
                for attempt in range(1, max_attempts + 1):
                    logger.debug(f"   Intento rápido #{attempt}/{max_attempts}")
                    try:
                        fast_result = await loop.run_in_executor(
                            None,
                            process,
                            CAPSOLVER_API_KEY,
                            HERO_SMS_KEYS,
                            None, None, None, None, None,
                            PROXY_STRING,
                            None,
                            country
                        )
                        if fast_result:
                            logger.debug("✅ Método rápido exitoso.")
                            account_data = {
                                'phone': fast_result['phone'],
                                'password': fast_result['password'],
                                'name': fast_result['name'],
                                'address': 'No address added',
                                'cookie_string': fast_result['cookies'],
                                'cookie_dict': dict(x.split('=', 1) for x in fast_result['cookies'].split('; ') if '=' in x),
                                'country': country,
                                'purchase_country': country
                            }
                            return {'success': True, 'data': account_data, 'country': country, 'screenshot': None}
                    except CAPSolverNoBalance as e:
                        logger.error(f"❌ CapSolver sin saldo: {e}")
                        set_service_enabled(False)
                        return {
                            'success': False,
                            'error': 'El servicio de resolución de captchas (CapSolver) no tiene saldo. El generador de cookies ha sido desactivado. Por favor, contacta al administrador para recargar el saldo y reactivar el servicio mediante /estatusCuki en el bot.',
                            'screenshot': None,
                            'captcha_balance': True
                        }
                    except SMSAccountBannedTemporarily as e:
                        logger.error(f"❌ Al menos una key de SMS está baneada temporalmente: {e}")
                        set_service_enabled(False)
                        SERVICE_BLOCKED_REASON = 'sms_temp'
                        SERVICE_BLOCKED_UNTIL = time.time() + 30 * 60
                        threading.Timer(30 * 60, lambda: set_service_enabled(True)).start()
                        return {
                            'success': False,
                            'error': 'Una cuenta de SMS está baneada temporalmente. El servicio se ha deshabilitado por 30 minutos. Reintenta más tarde.',
                            'screenshot': None,
                            'banned_temporarily': True
                        }
                    except SMSNoBalance as e:
                        logger.error(f"❌ Todas las keys de SMS tienen saldo insuficiente: {e}")
                        set_service_enabled(False)
                        SERVICE_BLOCKED_REASON = 'no_balance'
                        return {
                            'success': False,
                            'error': 'Saldo de SMS insuficiente en todas las cuentas. Avisar a administradores para recargar. El servicio ha sido deshabilitado indefinidamente.',
                            'screenshot': None,
                            'no_balance': True
                        }
                    except Exception as e:
                        logger.debug(f"   Intento rápido #{attempt} falló: {e}")
                        if attempt == max_attempts:
                            logger.debug("⚠️ Todos los intentos rápidos fallaron. Recurriendo a Playwright...")
                        else:
                            await asyncio.sleep(2)
            else:
                logger.debug("⚠️ Método rápido no disponible (faltan claves o proxy). Usando Playwright directamente.")

        # ---------- FALLBACK: PLAYWRIGHT ----------
        account_data, error_msg, screenshot = await create_amazon_account(
            country,
            add_address_flag=add_address,
            max_retries=max_retries,
            max_internal_retries=max_internal_retries
        )
        if account_data:
            return {'success': True, 'data': account_data, 'country': country, 'screenshot': screenshot}
        else:
            return {'success': False, 'error': error_msg, 'country': country, 'screenshot': screenshot}

    except Exception as e:
        logger.exception(f"💥 Excepción en generate_cookie_api: {e}")
        return {'success': False, 'error': str(e), 'country': country, 'screenshot': None}# -------------------------------------------------------------------
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


async def close_overlays(page):
    """Intenta cerrar modales o overlays comunes de Amazon (cookies, etc.)"""
    # Lista de botones comunes para cerrar
    close_buttons = [
        'button:has-text("Aceptar")',
        'button:has-text("Aceptar cookies")',
        'button:has-text("Continuar")',
        'button:has-text("Cerrar")',
        'button[aria-label="Cerrar"]',
        'button[aria-label="Close"]',
        'button:has-text("Entendido")',
        'button:has-text("OK")'
    ]
    for selector in close_buttons:
        try:
            # Esperar hasta 2 segundos para que aparezca
            element = await page.wait_for_selector(selector, timeout=2000)
            if element:
                await element.click()
                await page.wait_for_timeout(500)
        except:
            pass
    # También intentar presionar Escape para cerrar modales
    try:
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(500)
    except:
        pass


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
    global SERVICE_BLOCKED_UNTIL, SERVICE_BLOCKED_REASON

    # Si no hay bloqueo, consultar BD
    if SERVICE_BLOCKED_REASON is None and time.time() >= SERVICE_BLOCKED_UNTIL:
        SERVICE_BLOCKED_UNTIL = 0
        try:
            response = requests.get(
                f"{API_BASE_URL}/service-status-for-generator",
                headers={'x-bot-key': BOT_API_KEY},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('enabled', True)
            else:
                return True
        except Exception:
            return True

    # Hay un bloqueo: consultar BD para ver si el admin ya reactivó
    try:
        response = requests.get(
            f"{API_BASE_URL}/service-status-for-generator",
            headers={'x-bot-key': BOT_API_KEY},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('enabled', False):
                # Admin reactivó → limpiar bloqueo local
                SERVICE_BLOCKED_REASON = None
                SERVICE_BLOCKED_UNTIL = 0
                return True
            else:
                # Admin mantiene desactivado → respetar tiempo local
                return time.time() < SERVICE_BLOCKED_UNTIL
        else:
            # No se puede consultar, usar tiempo local
            return time.time() < SERVICE_BLOCKED_UNTIL
    except Exception:
        # Error de conexión, usar tiempo local
        return time.time() < SERVICE_BLOCKED_UNTIL   
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
    headers = {
        'Authorization': f'Bearer {token}',
        'x-bot-key': BOT_API_KEY,
        'x-api-key': SERVICE_API_KEY
    }
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
        'x-bot-key': BOT_API_KEY,
        'x-api-key': SERVICE_API_KEY,
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
    # ---------- 1. CAPTCHA DE COORDENADAS (con consenso de 8 peticiones) ----------
    content = await page.content()
    coordinate_indicators = ["Resuelve esta adivinanza", "Elija todo", "Selecciona todas las imágenes", "Seleccione todo"]
    if any(indicator in content for indicator in coordinate_indicators):
        logger.warning("⚠️ Captcha de coordenadas detectado")
        
        # Máximo de intentos globales (por si se atasca)
        max_global_attempts = 100
        global_attempt = 0
        captcha_resuelto = False
        
        while global_attempt < max_global_attempts and not captcha_resuelto:
            global_attempt += 1
            logger.debug(f"   --- Intento global #{global_attempt} ---")
            
            # Obtener el ID del canvas actual (para esperar cambios después)
            canvas_before = await page.query_selector('canvas')
            canvas_id_before = None
            if canvas_before:
                canvas_id_before = await canvas_before.get_attribute('data-challenge-id')
                if not canvas_id_before:
                    box = await canvas_before.bounding_box()
                    canvas_id_before = f"{box['x']}_{box['y']}_{box['width']}_{box['height']}" if box else None
                logger.debug(f"   Canvas ID actual: {canvas_id_before}")
            
            # Resolver el captcha actual usando 8 peticiones paralelas y consenso
            exito = await solve_coordinate_captcha(page, "coord", round_num=global_attempt)
            
            if not exito:
                # No se logró consenso -> refrescar el canvas y continuar
                logger.warning("   No se obtuvo consenso entre las respuestas. Refrescando canvas...")
                await click_refresh_button(page)
                await page.wait_for_timeout(3000)
                continue
            
                        # Después de resolver el captcha, verificar directamente si la página ya avanzó
            await page.wait_for_timeout(2000)
            
            # Verificar si la página ya avanzó a la pantalla de SMS o registro
            if await page.query_selector('#cvf-input-code, #cvf-input-otp, input[name="otpCode"]'):
                logger.debug("   ✅ Pantalla SMS detectada. Captcha completado.")
                captcha_resuelto = True
                break
            if await page.query_selector('#ap_customer_name'):
                logger.debug("   ✅ Pantalla de registro detectada. Captcha completado.")
                captcha_resuelto = True
                break
            
            # Verificar si redirigió a login (error grave)
            if await page.query_selector('#ap_email'):
                logger.warning("   🚫 Redirección a login después de resolver captcha.")
                await take_screenshot(page, "redirigido_login_despues_captcha")
                raise Exception("AMAZON_REDIRECTED_TO_LOGIN")
            
            # Verificar si el canvas ha desaparecido (el captcha se resolvió)
            canvas_exists = await page.query_selector('canvas')
            if not canvas_exists:
                logger.debug("   ✅ Canvas desaparecido, captcha completado.")
                captcha_resuelto = True
                break
            
            # Verificar mensajes de error específicos del captcha
            error_incorrecto = await page.query_selector('.a-alert-content:has-text("Incorrecto"), div:has-text("Incorrecto")')
            error_timeout = await page.query_selector('.a-alert-content:has-text("superado el límite de tiempo"), div:has-text("límite de tiempo")')
            if error_incorrecto or error_timeout:
                tipo = "incorrectas" if error_incorrecto else "timeout"
                logger.warning(f"   ❌ Error detectado: coordenadas {tipo}.")
                await take_screenshot(page, f"error_coordenadas_{tipo}")
                raise Exception(f"CAPTCHA_ERROR: coordenadas {tipo}")
            
            # Esperar cambio de canvas (solo 5 segundos)
            change_result = await wait_for_canvas_change(page, canvas_id_before, timeout=5)
            
            if change_result == 'new_canvas':
                logger.debug("   Nuevo canvas detectado. Reintentando siguiente ronda...")
                continue
            elif change_result == 'sms' or change_result == 'register':
                logger.debug("   ✅ Captcha completado! Pantalla final detectada.")
                captcha_resuelto = True
                break
            elif change_result == 'login':
                raise Exception("AMAZON_REDIRECTED_TO_LOGIN")
            else:
                # Si no hay cambio, verificar si el botón Confirmar ya no existe (indicador de éxito)
                confirm_btn = await page.query_selector('button:has-text("Confirmar"), input[value="Confirmar"]')
                if not confirm_btn:
                    logger.debug("   ✅ Botón Confirmar desaparecido, captcha completado.")
                    captcha_resuelto = True
                    break
                else:
                    logger.warning("   ⏱️ Timeout esperando cambio, pero se asume éxito (modo defensivo).")
                    captcha_resuelto = True
                    break
        
        if captcha_resuelto:
            logger.debug(f"   ✅ Captcha de coordenadas completado exitosamente después de {global_attempt} intentos.")
            return True
        else:
            raise Exception(f"No se pudo completar el captcha después de {max_global_attempts} intentos.")
    

    
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
    MIN_MATCHES = 2           # coincidencias requeridas
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
    
async def wait_for_sms_code_with_retry(service_name, service_id, page, timeout_total: int = TIMEOUT_SMS, resend_interval: int = 40):
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
    
async def get_hero_sms_code(activation_id, timeout: int = TIMEOUT_SMS):
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
def get_phone_number_sync(country_code, force_service=None, force_country=None):
    """Versión síncrona de get_phone_number (ejecuta asyncio.run())"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_phone_number(country_code, force_service, force_country))
    finally:
        loop.close()

def get_hero_sms_code_sync(activation_id, timeout: int = TIMEOUT_SMS):
    """SMS code polling síncrono para Hero SMS"""
    start = time.time()
    url = "https://hero-sms.com/stubs/handler_api.php"
    while time.time() - start < timeout:
        params = {'api_key': HERO_SMS_API_KEY, 'action': 'getStatusV2', 'id': activation_id}
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('sms') and data['sms'].get('code'):
                    return data['sms']['code']
        except Exception:
            pass
        time.sleep(5)
    return None

def get_fivesim_code_sync(order_id, timeout: int = TIMEOUT_SMS):
    """SMS code polling síncrono para 5sim"""
    url = f"{FIVESIM_BASE_URL}/user/check/{order_id}"
    headers = {'Authorization': f'Bearer {FIVESIM_API_KEY}', 'Accept': 'application/json'}
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == 'RECEIVED':
                    sms = data.get('sms', [])
                    if sms:
                        code = sms[0].get('code')
                        if not code:
                            text = sms[0].get('text', '')
                            codes = re.findall(r'\b(\d{5,6})\b', text)
                            code = codes[0] if codes else None
                        if code:
                            return code
        except Exception:
            pass
        time.sleep(5)
    return None

# ===================================================================
# FUNCIÓN PRINCIPAL PARA OBTENER NÚMERO (VERSIÓN UNIFICADA)
# ===================================================================
async def get_phone_number(account_country, force_service=None, force_country=None):
    """
    Obtiene un número de teléfono usando la lógica unificada:
    - Prueba todas las keys de Hero SMS para cada país en orden.
    - Si Hero falla (NO_BALANCE o CHANNELS_LIMIT), pasa a 5sim.
    - Si se fuerza un servicio y/o país, respeta esa preferencia.
    """
    # Prefijos para extraer número local (dígitos después del código país)
    prefix_len = {
        'ID': 2, 'MX': 2, 'US': 1, 'CA': 1, 'UK': 2, 'DE': 2, 'FR': 2,
        'IT': 2, 'ES': 2, 'JP': 2, 'AU': 2, 'IN': 2,
        'BR': 2, 'CM': 3, 'MA': 3, 'KG': 3, 'CO': 2,
    }
    prefix_len_plus = {
        'ID': 3, 'MX': 3, 'US': 2, 'CA': 2, 'UK': 3, 'DE': 3, 'FR': 3,
        'IT': 3, 'ES': 3, 'JP': 3, 'AU': 3, 'IN': 3, 'KG': 3, 'PL': 3,
        'CO': 3, 'LV': 3, 'PK': 3, 'TJ': 3, 'KE': 3, 'BR': 3, 'CM': 4, 'MA': 4,
    }

    # ---------- CASO 1: Se fuerza un servicio y un país específico ----------
    if force_service and force_country:
        logger.debug(f"🔒 Forzando servicio={force_service}, país={force_country}")
        if force_service == 'hero':
            try:
                activation_id, phone, purchase_country = get_number(HERO_SMS_KEYS, country_code=force_country)
                local_len = prefix_len.get(purchase_country, 0)
                phone_local = phone[local_len:] if local_len and len(phone) > local_len else phone
                phone_local = re.sub(r'\D', '', phone_local)
                return {
                    'full': f'+{phone}',
                    'local': phone_local,
                    'service_id': activation_id,
                    'service_name': 'hero',
                    'purchase_country': purchase_country
                }
            except Exception as e:
                logger.warning(f"Hero SMS forzado falló en {force_country}: {e}")
                return None
        elif force_service == '5sim':
            try:
                phone_full, service_id = await get_fivesim_number(force_country)
                if not phone_full or not service_id:
                    return None
                local_len = prefix_len_plus.get(force_country, 0)
                phone_local = phone_full[local_len:] if local_len and len(phone_full) > local_len else phone_full
                phone_local = re.sub(r'\D', '', phone_local)
                return {
                    'full': phone_full,
                    'local': phone_local,
                    'service_id': service_id,
                    'service_name': '5sim',
                    'purchase_country': force_country
                }
            except Exception as e:
                logger.warning(f"5sim forzado falló en {force_country}: {e}")
                return None
        else:
            return None

    # ---------- CASO 2: Se fuerza solo el servicio (sin país) ----------
    if force_service:
        logger.debug(f"🔒 Forzando solo servicio={force_service}")
        if force_service == 'hero':
            for country in HERO_COUNTRY_ORDER:
                try:
                    activation_id, phone, purchase_country = get_number(HERO_SMS_KEYS, country_code=country)
                    local_len = prefix_len.get(purchase_country, 0)
                    phone_local = phone[local_len:] if local_len and len(phone) > local_len else phone
                    phone_local = re.sub(r'\D', '', phone_local)
                    return {
                        'full': f'+{phone}',
                        'local': phone_local,
                        'service_id': activation_id,
                        'service_name': 'hero',
                        'purchase_country': purchase_country
                    }
                except SMSNoBalance as e:
                    logger.error(f"Hero SMS sin saldo en {country}: {e}")
                    break  # si todas las keys tienen NO_BALANCE, no seguir con otros países (misma cuenta)
                except SMSAccountBannedTemporarily as e:
                    logger.warning(f"Hero SMS baneado temporalmente en {country}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Hero SMS error en {country}: {e}")
                    continue
            return None
        elif force_service == '5sim':
            # Obtener orden de países para 5sim (por precio)
            fivesim_prices = await get_fivesim_prices()
            order = list(fivesim_prices.keys()) if fivesim_prices else FIVESIM_MANUAL_ORDER
            for country in order:
                try:
                    phone_full, service_id = await get_fivesim_number(country)
                    if not phone_full or not service_id:
                        continue
                    local_len = prefix_len_plus.get(country, 0)
                    phone_local = phone_full[local_len:] if local_len and len(phone_full) > local_len else phone_full
                    phone_local = re.sub(r'\D', '', phone_local)
                    return {
                        'full': phone_full,
                        'local': phone_local,
                        'service_id': service_id,
                        'service_name': '5sim',
                        'purchase_country': country
                    }
                except Exception as e:
                    logger.debug(f"5sim error en {country}: {e}")
                    continue
            return None
        else:
            return None

    # ---------- CASO 3: Sin fuerza: probar hero (con todas las keys) y luego 5sim ----------
    # 3.1 Intentar con Hero SMS (todas las keys) en cada país del orden
    for country in HERO_COUNTRY_ORDER:
        try:
            activation_id, phone, purchase_country = get_number(HERO_SMS_KEYS, country_code=country)
            local_len = prefix_len.get(purchase_country, 0)
            phone_local = phone[local_len:] if local_len and len(phone) > local_len else phone
            phone_local = re.sub(r'\D', '', phone_local)
            logger.debug(f"✅ Número obtenido con Hero SMS: {phone} (país {purchase_country})")
            return {
                'full': f'+{phone}',
                'local': phone_local,
                'service_id': activation_id,
                'service_name': 'hero',
                'purchase_country': purchase_country
            }
        except SMSNoBalance as e:
            logger.error(f"❌ Hero SMS sin saldo en {country}: {e}")
            # Si es NO_BALANCE para todas las keys, no tiene sentido probar otros países (misma cuenta)
            break
        except SMSAccountBannedTemporarily as e:
            logger.warning(f"⚠️ Hero SMS baneado temporalmente en {country}: {e}")
            continue  # probar siguiente país (podría funcionar)
        except Exception as e:
            logger.debug(f"⚠️ Hero SMS error en {country}: {e}")
            continue

    # 3.2 Si Hero falla, intentar con 5sim
    logger.debug("🔄 Hero SMS falló, intentando con 5sim...")
    if FIVESIM_API_KEY:
        fivesim_prices = await get_fivesim_prices()
        order = list(fivesim_prices.keys()) if fivesim_prices else FIVESIM_MANUAL_ORDER
        for country in order:
            try:
                phone_full, service_id = await get_fivesim_number(country)
                if not phone_full or not service_id:
                    continue
                local_len = prefix_len_plus.get(country, 0)
                phone_local = phone_full[local_len:] if local_len and len(phone_full) > local_len else phone_full
                phone_local = re.sub(r'\D', '', phone_local)
                logger.debug(f"✅ Número obtenido con 5sim: {phone_full} (país {country})")
                return {
                    'full': phone_full,
                    'local': phone_local,
                    'service_id': service_id,
                    'service_name': '5sim',
                    'purchase_country': country
                }
            except Exception as e:
                logger.debug(f"⚠️ 5sim error en {country}: {e}")
                continue

    # Si todo falla
    logger.error("❌ No se pudo obtener número de teléfono con ningún servicio.")
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
# FUNCIÓN AUXILIAR PARA CAPTURAR PANTALLA (optimizadaa)
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
            # ----- PASO 1: Configurar sesión requests (solo para probar proxy) -----
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

            # ----- PASO 3: Generar credenciales (sin número aún) -----
            logger.debug("🔑 Generando credenciales...")
            password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
            first_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            last_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            fullname = f"{first_name} {last_name}"
            account_data['password'] = password
            account_data['name'] = fullname
            logger.debug(f"   👤 Nombre: {fullname}")
            logger.debug(f"   🔐 Contraseña: {password}")

            # ----- PASO 4: Iniciar Playwright -----
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

            # ----- PASO 5: Lanzar browser -----
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

            # ----- BUCLE DE REINTENTO INTERNO (misma IP, misma página) -----
            internal_attempt = 0
            registration_success = False
            last_error = None

            # Variables para el número (se obtendrá dentro del bucle)
            phone_info = None
            service_id = None
            service_name = None
            purchase_country = None
            sms_phone = None

            while internal_attempt < max_internal_retries and not registration_success:
                internal_attempt += 1
                logger.debug(f"🔄 Intento interno {internal_attempt}/{max_internal_retries} (misma IP)")

                if internal_attempt > 1:
                    # Cerrar página actual y abrir una nueva en el mismo contexto
                    await page.close()
                    page = await context.new_page()

                try:
                    # ========== OBTENER NÚMERO (solo si no se tiene aún) ==========
                    if phone_info is None:
                        try:
                            phone_info = await get_phone_number(country_code)
                            if not phone_info:
                                raise Exception("No se pudo obtener número de teléfono")
                            sms_phone = phone_info['local']
                            service_id = phone_info['service_id']
                            service_name = phone_info['service_name']
                            purchase_country = phone_info['purchase_country']
                            logger.debug(f"Número obtenido: {phone_info['full']} (servicio: {service_name}, país: {purchase_country})")
                            account_data['phone'] = sms_phone
                            account_data['purchase_country'] = purchase_country
                        except SMSAccountBannedTemporarily as e:
                            logger.error(f"❌ Todas las keys de SMS están en CHANNELS_LIMIT. Deteniendo proceso.")
                            # Lanzar excepción para que el global la capture y desactive el servicio
                            raise SMSAccountBannedTemporarily("Límite de canales alcanzado en todas las keys y países")
                        except Exception as e:
                            raise

                    # ----- PASO 7: Navegar a la URL base (con reintentos) -----
                    base_url = base_urls[country_code]
                    max_nav_retries = 3
                    nav_success = False
                    last_error = None

                    login_selectors = [
                        '#nav-link-accountList',
                        'a[data-nav-role="signin"]',
                        'a.nav-a.nav-a-2[href*="/ap/signin"]',
                        'a:has-text("Hola, identifícate")',
                        'a:has-text("Cuenta y Listas")',
                        'a[href*="/ap/signin"]'
                    ]

                    for nav_attempt in range(1, max_nav_retries + 1):
                        try:
                            logger.debug(f"   Intentando cargar {base_url} (intento {nav_attempt})")
                            await page.unroute('**/*')
                            await page.goto(base_url, wait_until='domcontentloaded', timeout=60000)
                            await page.wait_for_timeout(3000)
                            await handle_captcha_if_present(page, "initial_load")
                            current_url = page.url
                            logger.debug(f"   URL actual después de navegación: {current_url}")
                            if 'amazon' not in current_url:
                                logger.warning(f"   Redirección inesperada a {current_url}, reintentando...")
                                continue
                            await close_overlays(page)
                            selector_found = False
                            for sel in login_selectors:
                                try:
                                    await page.wait_for_selector(sel, state='visible', timeout=10000)
                                    logger.debug(f"   ✅ Selector encontrado: {sel}")
                                    selector_found = True
                                    break
                                except:
                                    continue
                            if selector_found:
                                nav_success = True
                                break
                            else:
                                await take_screenshot(page, "no_login_selector")
                                content = await page.content()
                                if "Lo sentimos" in content or "no podemos crear tu cuenta" in content:
                                    raise Exception("AMAZON_ERROR_PAGE")
                                elif "detected unusual activity" in content or "actividad inusual" in content:
                                    raise Exception("AMAZON_UNUSUAL_ACTIVITY")
                                else:
                                    logger.warning("   No se encontró selector de login, reintentando...")
                                    continue
                        except Exception as nav_err:
                            last_error = nav_err
                            logger.warning(f"Navegación intento {nav_attempt} falló: {nav_err}")
                            if nav_attempt == max_nav_retries:
                                raise
                            await asyncio.sleep(10)
                            await page.close()
                            page = await context.new_page()

                    if not nav_success:
                        raise Exception(f"No se pudo cargar la página después de {max_nav_retries} intentos: {last_error}")

                    await page.route('**/*', block_resources)

                    # ----- PASO 7.5: Página de bienvenida y login -----
                    logger.debug("🛒 [PASO 7.5] Verificando página de bienvenida...")
                    continue_shopping_selectors = [
                        'input[value="Continuar a Compras"]',
                        'button:has-text("Continuar a Compras")',
                        'input[value="Continue to Shopping"]',
                        'button:has-text("Continue to Shopping")'
                    ]
                    for selector in continue_shopping_selectors:
                        try:
                            btn = await page.wait_for_selector(selector, state='visible', timeout=200)
                            if btn:
                                logger.debug(f"   ✅ Botón de continuar encontrado: {selector}")
                                await btn.click()
                                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                                await page.wait_for_timeout(2000)
                                break
                        except:
                            continue

                    logger.debug("👤 Haciendo clic en inicio de sesión...")
                    clicked = False
                    try:
                        await page.click('#nav-link-accountList', timeout=15000)
                        logger.debug("✅ Clic en #nav-link-accountList")
                        clicked = True
                    except:
                        pass
                    if not clicked:
                        try:
                            await page.click('text="Hola, identifícate"')
                            logger.debug("✅ Clic en 'Hola, identifícate'")
                            clicked = True
                        except:
                            pass
                    if not clicked:
                        login_url = f"{base_urls[country_code]}/ap/signin?openid.return_to={base_urls[country_code]}%2F&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=amzn_{country_code.lower()}&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
                        await page.goto(login_url, wait_until='domcontentloaded', timeout=30000)
                        logger.debug("✅ Navegación directa a login")
                        clicked = True
                    if not clicked:
                        raise Exception("No se pudo acceder a la página de inicio de sesión")

                    await page.wait_for_timeout(2000)
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

                    # ====== NUEVO: SI LA URL CONTIENE "claim?" ======
                    if "claim?" in page.url.lower():
                        logger.warning("⚠️ Número ya registrado. Cancelando este número y comprando otro...")

                        # 1. Intentar cancelar el número (si es posible, pero si da EARLY_CANCEL_DENIED, lo ignoramos)
                        if service_id:
                            try:
                                # Solo intentar cancelar si ha pasado más de 2 minutos (120 segundos)
                                # Para saberlo, necesitaríamos guardar el timestamp de compra.
                                # Como no lo tenemos, mejor no cancelar y dejar que el número expire solo.
                                # O simplemente intentar cancelar y si falla, continuar.
                                if service_name == 'hero':
                                    await cancel_hero_sms(service_id)
                                elif service_name == '5sim':
                                    await cancel_fivesim(service_id)
                                logger.debug(f"   ✅ Número {phone_info['full']} cancelado (o se intentó)")
                            except Exception as e:
                                logger.debug(f"   ⚠️ No se pudo cancelar el número (probablemente EARLY_CANCEL_DENIED): {e}")

                        # 2. Marcar phone_info como None para forzar la compra de un nuevo número en la siguiente iteración
                        phone_info = None
                        # 3. Reiniciar el bucle interno (continue) para que se compre un nuevo número
                        logger.debug("   🔄 Reiniciando bucle para comprar otro número...")
                        # Limpiar cookies y cerrar página para empezar fresco
                        await page.close()
                        page = await context.new_page()
                        continue

                    # ----- PASO 10.5: Resolver captcha si aparece antes del envío -----
                    await handle_captcha_if_present(page, step_name="pre_submit")

                    # ----- PASO 11: Página intermedia "Proceder a crear una cuenta" -----
                    logger.debug("🔍 Verificando página intermedia...")
                    primary_selector = 'span#intention-submit-button input.a-button-input'
                    clicked = await smart_click(page, primary_selector, timeout=ACTION_TIMEOUT*1000, wait_for_navigation=False)
                    if clicked:
                        try:
                            await page.wait_for_function('document.querySelector("#ap_customer_name") !== null', timeout=15000)
                            logger.debug("   ✅ Formulario de registro cargado después del clic")
                        except Exception as e:
                            raise Exception(f"Timeout esperando campo de nombre después del clic: {e}")
                    else:
                        logger.debug("   ⚠️ No se encontró el botón 'Proceder a crear una cuenta'")
                        current_url = page.url
                        page_content = await page.content()
                        is_login_page = await page.query_selector('#ap_email') is not None
                        if is_login_page:
                            logger.warning("   🔄 Redirigido a la página de inicio de sesión. Reiniciando proceso interno.")
                            # Limpiar cookies y reiniciar
                            await page.close()
                            page = await context.new_page()
                            continue
                        elif "Lo sentimos" in page_content or "no podemos crear tu cuenta" in page_content:
                            logger.warning("   ❌ Página de error de Amazon detectada. Reiniciando proceso interno.")
                            await page.close()
                            page = await context.new_page()
                            continue
                        else:
                            logger.debug("   ℹ️ No se detectó error. Esperando 4 segundos a que el formulario cargue automáticamente...")
                            await page.wait_for_timeout(4000)
                            try:
                                await page.wait_for_selector('#ap_customer_name', state='visible', timeout=2000)
                                logger.debug("   ✅ Formulario de registro cargado automáticamente")
                            except Exception:
                                raise Exception("No se pudo acceder al formulario de registro después de Continuar")

                    last_screenshot = await take_screenshot(page, "despues_proceder")

                    # ----- PASO 12: Enviar formulario de registro -----
                    async def enviar_formulario_registro():
                        logger.debug("📝 Enviando formulario de registro (con reintentos)...")
                        name_selectors = ['input#ap_customer_name', 'input[name="customerName"]']
                        name_filled = False
                        for sel in name_selectors:
                            if await smart_fill(page, sel, fullname):
                                name_filled = True
                                break
                        if not name_filled:
                            logger.warning("⚠️ No se pudo llenar campo de nombre, puede estar precargado")

                        await page.wait_for_selector('input#ap_password', state='visible', timeout=5000)
                        await page.wait_for_selector('input#ap_password_check', state='visible', timeout=5000)

                        max_submit_attempts = 3
                        submit_success = False
                        for submit_attempt in range(1, max_submit_attempts + 1):
                            if submit_attempt > 1:
                                logger.debug(f"   Reintentando envío (intento {submit_attempt})")
                                await smart_fill(page, 'input#ap_password', password)
                                await smart_fill(page, 'input#ap_password_check', password)
                                await smart_fill(page, 'input[name="passwordCheck"]', password)
                            else:
                                await smart_fill(page, 'input#ap_password', password)
                                await smart_fill(page, 'input#ap_password_check', password)
                                await smart_fill(page, 'input[name="passwordCheck"]', password)

                            filled_pwd = await page.input_value('input#ap_password')
                            if not filled_pwd or len(filled_pwd) < 6:
                                continue

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
                            await handle_captcha_if_present(page, step_name="post_submit")

                            content = await page.content()
                            if "Detectamos actividad inusual" in content:
                                logger.warning("   🚫 ACTIVIDAD INUSUAL -> reinicio GLOBAL")
                                raise Exception("AMAZON_BLOCKED_ACCOUNT")
                            if "incorrecto o no válido" in content or "Introduzca un número de móvil válido" in content:
                                logger.warning(f"   NÚMERO INVÁLIDO (intento {submit_attempt}) -> rellenando número")
                                # Si el número es inválido, comprar otro
                                phone_field = await page.wait_for_selector(phone_field_selector, timeout=3000)
                                if phone_field:
                                    # Marcar phone_info como None para comprar otro
                                    phone_info = None
                                    raise Exception("NUMERO_INVALIDO_RECARGAR")
                            if "Mínimo 6 caracteres requeridos" in content or "Minimo 6 caracteres requeridos" in content:
                                logger.warning(f"   CONTRASEÑA VACÍA (intento {submit_attempt}) -> reintentando")
                                continue
                            if "El número de teléfono móvil ya está en uso" in content or "El número de teléfono móvil ya está registrado" in content:
                                logger.warning("   NÚMERO YA REGISTRADO -> comprando otro número")
                                phone_info = None
                                raise Exception("NUMERO_REGISTRADO_RECARGAR")
                            submit_success = True
                            break

                        if not submit_success:
                            raise Exception("No se pudo enviar el formulario de registro después de varios intentos")
                        return True

                    try:
                        await enviar_formulario_registro()
                    except Exception as e:
                        if "NUMERO_INVALIDO_RECARGAR" in str(e) or "NUMERO_REGISTRADO_RECARGAR" in str(e):
                            # Reiniciar el bucle para comprar otro número
                            logger.debug("   🔄 Número inválido o registrado. Comprando otro...")
                            await page.close()
                            page = await context.new_page()
                            continue
                        else:
                            raise

                    last_screenshot = await take_screenshot(page, "despues_registro")

                    # ----- PASO 15: VERIFICACIÓN POR SMS -----
                    logger.debug("📱 Verificación SMS con reintentos por país y número...")
                    await page.wait_for_timeout(5000)

                    # Verificar si estamos en WhatsApp
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
                            await page.wait_for_timeout(3000)

                    # Esperar campo de código
                    try:
                        code_input = await page.wait_for_selector('#cvf-input-code', state='visible', timeout=30000)
                    except Exception as e:
                        error_msg = await page.query_selector('.a-alert-content, .a-alert-error')
                        if error_msg:
                            error_text = await error_msg.text_content()
                            if "No se puede enviar un mensaje SMS" in error_text or "Verifica a través de WhatsApp" in error_text:
                                logger.warning(f"⚠️ SMS no disponible. Cancelando número y comprando otro...")
                                if service_id:
                                    try:
                                        if service_name == 'hero':
                                            await cancel_hero_sms(service_id)
                                        elif service_name == '5sim':
                                            await cancel_fivesim(service_id)
                                    except Exception as cancel_err:
                                        logger.debug(f"   ⚠️ Error cancelando número: {cancel_err}")
                                phone_info = None
                                await page.close()
                                page = await context.new_page()
                                continue
                            else:
                                logger.error(f"❌ Error inesperado: {error_text}")
                                raise Exception(f"Error en verificación SMS: {error_text}")
                        else:
                            raise Exception(f"Campo de código no apareció: {e}")

                    # Esperar código SMS
                    sms_code = await wait_for_sms_code_with_retry(service_name, service_id, page, timeout_total=TIMEOUT_SMS, resend_interval=40)
                    if sms_code:
                        await code_input.fill('')
                        await code_input.fill(sms_code)
                        logger.debug(f"   ✅ Código SMS ingresado: {sms_code}")
                        verify_btn = await page.query_selector('input[type="submit"], button:has-text("Verificar"), button:has-text("Verify")')
                        if verify_btn:
                            await verify_btn.click()
                            await page.wait_for_load_state('domcontentloaded', timeout=15000)
                            if 'your-account' in page.url.lower() or 'account' in page.url.lower():
                                logger.debug("   ✅ Registro exitoso después de SMS.")
                            else:
                                logger.warning("   Código incorrecto o no redirigió, reintentando...")
                                # Si el código falla, cancelar número y comprar otro
                                if service_id:
                                    try:
                                        if service_name == 'hero':
                                            await cancel_hero_sms(service_id)
                                        elif service_name == '5sim':
                                            await cancel_fivesim(service_id)
                                    except Exception as cancel_err:
                                        logger.debug(f"   ⚠️ Error cancelando número: {cancel_err}")
                                phone_info = None
                                await page.close()
                                page = await context.new_page()
                                continue
                        else:
                            logger.warning("   No se encontró botón de verificar")
                    else:
                        logger.warning(f"⏰ No se recibió código en el tiempo límite. Cancelando número...")
                        if service_id:
                            try:
                                if service_name == 'hero':
                                    await cancel_hero_sms(service_id)
                                elif service_name == '5sim':
                                    await cancel_fivesim(service_id)
                            except Exception as cancel_err:
                                logger.debug(f"   ⚠️ Error cancelando número: {cancel_err}")
                        phone_info = None
                        await page.close()
                        page = await context.new_page()
                        continue

                    # ----- PASO 16: Verificar éxito -----
                    if 'your-account' in page.url.lower() or 'account' in page.url.lower() or 'welcome' in page.url.lower():
                        logger.debug("   ✅ Registro exitoso!")
                        cookies = await context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}
                        cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                        account_data['cookie_dict'] = cookie_dict
                        account_data['cookie_string'] = cookie_string
                        logger.debug(f"   🍪 Cookies obtenidas: {len(cookie_dict)} cookies")

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
                    error_str = str(e)
                    logger.debug(f"Error en intento interno {internal_attempt}: {error_str}")

                    # Si es error de SMS de límite, propagar para desactivar
                    if "SMSAccountBannedTemporarily" in error_str or "Límite de canales" in error_str:
                        raise

                    # Si es error de página de Amazon, reiniciar el bucle
                    if "AMAZON_ERROR_PAGE" in error_str or "AMAZON_ERROR_LOSENTIMOS" in error_str or "AMAZON_BLOCKED_ACCOUNT" in error_str:
                        logger.warning("⚠️ Error de página de Amazon. Reiniciando el bucle interno...")
                        await page.close()
                        page = await context.new_page()
                        continue

                    # Si es error recuperable, continuar el bucle
                    if "SMS_TIME_OUT" in error_str or "AMAZON_CAPTCHA_ERROR" in error_str or "FUNCAPTCHA_NO_SITEKEY" in error_str or "FUNCAPTCHA_NO_TOKEN" in error_str or "FUNCAPTCHA_NOT_DETECTED" in error_str or "AMAZON_REDIRECTED_TO_LOGIN" in error_str or "SMS_UNAVAILABLE_RETRY" in error_str:
                        logger.warning(f"Fallo recuperable (intento interno {internal_attempt}), reiniciando en nueva pestaña...")
                        await page.close()
                        page = await context.new_page()
                        continue
                    else:
                        logger.error(f"Error no recuperable en intento interno {internal_attempt}: {e}")
                        raise

            if not registration_success:
                raise last_error

        except SMSAccountBannedTemporarily as e:
            logger.error(f"❌ SMSAccountBannedTemporarily capturado: {e}")
            # Desactivar servicio y detener el proceso
            set_service_enabled(False)
            SERVICE_BLOCKED_REASON = 'sms_temp'
            SERVICE_BLOCKED_UNTIL = time.time() + 30 * 60
            threading.Timer(30 * 60, lambda: set_service_enabled(True)).start()
            # Propagar la excepción para que el generador se detenga
            raise

        except Exception as e:
            logger.error(f"❌ Error en intento global {global_attempt}: {e}")
            screenshot_b64 = None
            if page:
                try:
                    screenshot_b64 = await take_screenshot(page, "error_final")
                except Exception as ss_err:
                    logger.debug(f"   No se pudo tomar captura: {ss_err}")

            if global_attempt == retries:
                return None, str(e), screenshot_b64

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




# API FLASK
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app, origins=['https://astralchk.com'], methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "x-device-fingerprint"], supports_credentials=True)

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://astralchk.com')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization, x-device-fingerprint')
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
    force_playwright = data.get('force_playwright', False)
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
            if SERVICE_BLOCKED_REASON == 'sms_temp' and SERVICE_BLOCKED_UNTIL > time.time():
                remaining = int((SERVICE_BLOCKED_UNTIL - time.time()) / 60)
                msg = f'El servicio se ha deshabilitado por cuenta de SMS baneada temporalmente. Reintenta en {remaining} minutos.'
            elif SERVICE_BLOCKED_REASON == 'no_balance':
                msg = 'Saldo de SMS insuficiente en todas las cuentas. Avisar a administradores para recargar. El servicio ha sido deshabilitado indefinidamente.'
            else:
                msg = 'Servicio deshabilitado temporalmente por mantenimiento. Contacta al owner.'
            return jsonify({'success': False, 'error': msg}), 503
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(generate_cookie_api(country, add_address, max_retries, max_internal_retries, force_playwright))
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
        logger.debug("🍪 Generador de Cookies Amazon - Modo CLI (optimizado - mínimo consumo)")
        if not API_KEY_2CAPTCHA and not API_KEY_ANTICAPTCHA:
            logger.error("❌ ERROR: Configura al menos una API de captcha")
            sys.exit(1)
        if not PROXY_HOST_PORT:
            logger.error("❌ ERROR: PROXY_STRING no configurada")
            sys.exit(1)
        while True:
            logger.debug("\n--- MENÚ ---")
            logger.debug("1. Generar cookie")
            logger.debug("2. Salir")
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
                        logger.debug(f"\n✅ Cookie generada:")
                        logger.debug(f"   Teléfono: {data['phone']}")
                        logger.debug(f"   Contraseña: {data['password']}")
                        logger.debug(f"   Cookie: {data['cookie_string']}")
                    else:
                        logger.debug(f"\n❌ Error: {res['error']}")
                        if res.get('screenshot'):
                            logger.debug("   📸 Captura de pantalla disponible")
                finally:
                    loop.close()
            elif op == '2':
                break
    else:
        logger.debug(f"🚀 Iniciando API optimizada (mínimo consumo) en {API_HOST}:{API_PORT}")
        app.run(host=API_HOST, port=API_PORT, debug=False, threaded=True)