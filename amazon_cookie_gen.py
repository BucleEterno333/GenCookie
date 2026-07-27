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
import certifi
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
# ======================================================================
# PARCH SSL GLOBAL - PARA EVITAR ERRORES DE CERTIFICADOS EN PRODUCCIÓN
# ======================================================================
import ssl
import requests as std_requests
import curl_cffi
from curl_cffi import requests as cffi_requests

# 1. Desactivar verificación SSL a nivel de módulo ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# 2. Variables de entorno para curl_cffi y requests
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

# 3. Parchear 'requests' estándar (parcheando el método request de Session)
_original_std_request = std_requests.Session.request

def patched_std_request(self, method, url, **kwargs):
    kwargs['verify'] = False
    return _original_std_request(self, method, url, **kwargs)

std_requests.Session.request = patched_std_request

# Parchear métodos de conveniencia get y post
_original_std_get = std_requests.get
_original_std_post = std_requests.post

def patched_std_get(url, **kwargs):
    kwargs['verify'] = False
    return _original_std_get(url, **kwargs)

def patched_std_post(url, **kwargs):
    kwargs['verify'] = False
    return _original_std_post(url, **kwargs)

std_requests.get = patched_std_get
std_requests.post = patched_std_post

print("✅ Parche SSL aplicado a 'requests' estándar")

# 4. Parchear 'curl_cffi.requests' (igual)
_original_cffi_request = cffi_requests.Session.request

def patched_cffi_request(self, method, url, **kwargs):
    kwargs['verify'] = False
    return _original_cffi_request(self, method, url, **kwargs)

cffi_requests.Session.request = patched_cffi_request

_original_cffi_get = cffi_requests.get
_original_cffi_post = cffi_requests.post

def patched_cffi_get(url, **kwargs):
    kwargs['verify'] = False
    return _original_cffi_get(url, **kwargs)

def patched_cffi_post(url, **kwargs):
    kwargs['verify'] = False
    return _original_cffi_post(url, **kwargs)

cffi_requests.get = patched_cffi_get
cffi_requests.post = patched_cffi_post

# También parchear el módulo importado como 'curl_cffi.requests'
curl_cffi.requests.Session.request = patched_cffi_request
curl_cffi.requests.get = patched_cffi_get
curl_cffi.requests.post = patched_cffi_post

print("✅ Parche SSL aplicado a 'curl_cffi.requests'")

# 5. Desactivar advertencias de urllib3
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

print("🚀 SSL desactivado globalmente para todas las peticiones")
# ======================================================================





# Importar desde la carpeta amazon (la versión que funciona)
from amazon import core, helpers, AmazonRegisterError, AccountBuilder, AwsWaf, CookieConverter
from amazon.sms import HeroSms
from amazon.captcha import Captcha


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
TIMEOUT_SMS = int(os.getenv('TIMEOUT_SMS', '180'))              # Timeout para esperar SMS

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

_SMS_API = "https://hero-sms.com/stubs/handler_api.php"
PROXY_LIST = []

# 5 APIs de mail temporal con sus formatos específicos
_MAIL_APIS = [
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
            None  # No necesita token en headers, usa cookies
        ),
        "read": lambda token, msg_id: (
            "GET",
            f"https://10minutemail.com/messages/{msg_id['id']}",
            None,
            None
        ),
        "get_email": lambda data: data.get("address"),
        "get_token": lambda data: None,  # No hay token, usaremos cookies
        "has_messages": lambda data: isinstance(data, list) and len(data) > 0,
        "get_messages": lambda data: data if isinstance(data, list) else [],
        "get_msg_id": lambda msg: {"id": msg.get("id", msg.get("messageId", 0))},
        "get_body": lambda data: data.get("body") or data.get("html", ""),
        "check_errors": lambda data: None,
        "uses_cookies": True,  # Flag para indicar que usa cookies en lugar de token
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

# Orden de países para Hero SMS (barato a caro)
HERO_COUNTRY_ORDER = ['US', 'CA', 'ID', 'MA', 'CO', 'MX', 'BR', 'CM', 'KZ', 'KG' ]
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

HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "35"))
CAPTCHA_MAX = 4
SMS_TIMEOUT = int(os.environ.get("SMS_TIMEOUT", "100"))

# ======================================================================
# CLASE AmazonAccountCreator
# ======================================================================
class AmazonAccountCreator:
    def __init__(
        self,
        herosms_api_key: str,
        capsolver_api_key: str,
        country: str = 'MX',
        proxy: str = None,
        sms_max_price: float = None,
        on_status: callable = None,
    ):
        if country not in core.countrys_supported:
            raise ValueError(f"Country '{country}' not supported. Use: {', '.join(core.countrys_supported)}")

        self.country       = country
        self.domain        = core.DOMAIN_MAP[country]
        self.base_url      = f"https://www.{self.domain}"
        self.assoc_handle  = core.ASSOC_HANDLE_MAP[country]
        self.register_url  = core.MANAGE_URLS[country]
        self.proxy         = proxy
        self.user          = helpers.generateFakeProfile()
        self.capsolver_key = capsolver_api_key
        self.phone_data    = None
        _sms_price = sms_max_price
        if _sms_price is None:
            try:
                _sms_price = float(os.environ.get("SMS_MAX_PRICE", "0.18"))
            except ValueError:
                _sms_price = 0.12
        # targetCountry se establece como None para no fijar un país predeterminado
        self.sms_service   = HeroSms(herosms_api_key, maxPrice=_sms_price, targetCountry=None)
        self._on_status    = on_status
        self.skip_billing  = False

    def _emit(self, message: str):
        if self._on_status:
            try:
                self._on_status(message)
            except Exception as e:
                logger.warning(f"Status callback error: {e}")
        else:
            logger.info(message)

    def create(self, max_retries: int = 3, skip_billing: bool = False) -> dict:
        self.skip_billing = skip_billing
        for attempt in range(max_retries + 1):
            try:
                return self._attempt(attempt)
            except KeyboardInterrupt:
                self._emit("Cancelled by user")
                self._cancel_phone()
                return self._error("Cancelled by user")
            except Exception as e:
                error_msg = str(e)
                needs_new_number = any(k in error_msg for k in [
                    "unusual activity", "actividad inusual",
                    "number_associated", "sms_timeout",
                ])
                if needs_new_number:
                    self._cancel_phone()
                if 'unusual activity' in error_msg or 'actividad inusual' in error_msg:
                    self.user = helpers.generateFakeProfile()
                if attempt >= max_retries:
                    self._cancel_phone()
                    return self._error(error_msg)
                self._emit(f"Retry {attempt + 1}/{max_retries}: {error_msg}")
                time.sleep(2.0 if 'unusual activity' in error_msg else (0.5 if needs_new_number else 0.2))
                # NO intentes obtener nuevo número aquí; el próximo attempt lo hará automáticamente
        return self._error("Unexpected exit")

    def _attempt(self, retry: int) -> dict:
        self._emit(f"Attempt #{retry + 1}")
        init_time = time.time()

        if not self.phone_data:
            self._emit("Acquiring phone number (trying countries in order)...")
            for country_iso in HERO_COUNTRY_ORDER:
                country_code = hero_country_map.get(country_iso)
                if not country_code:
                    continue
                self._emit(f"Trying country {country_iso} (code {country_code})...")
                try:
                    phone_data = self.sms_service.getNumber(country_code=country_code)
                    if phone_data:
                        self.phone_data = phone_data
                        self._emit(f"Phone obtained: {self.phone_data['number']} from {country_iso}")
                        break
                except Exception as e:
                    self._emit(f"Failed for {country_iso}: {e}")
                    continue
            if not self.phone_data:
                raise Exception("No phone number available in any country")
        else:
            logger.info(f"Reusing phone: {self.phone_data['number']}")

        result = self._execute_flow()
        cookies_raw = result['cookies']

        try:
            self.sms_service.finishActivation(self.phone_data['activationId'])
        except Exception:
            pass

        if not getattr(self, "skip_billing", False):
            self._emit("Adding billing address...")
            builder = AccountBuilder(
                cookies_raw, country=self.country,
                proxy=helpers.normalizeProxy(self.proxy),
            )
            billing = builder.handleBillingAddress()
            if billing['status']:
                self._emit(billing['message'])
            else:
                self._emit(f"Billing warning: {billing['message']}")

        self._emit(f"Account created in {time.time() - init_time:.1f}s")
        return {
            "status": True,
            "profile": {
                "email": self.user.mail,
                "phone": f"+{self.phone_data['number']}",
                "password": self.user.password,
            },
            "cookies": cookies_raw,
            "country": self.country,
        }
    def _execute_flow(self) -> dict:
        phone       = self.phone_data['number']
        phone_short = self.phone_data['normalizedNumber']
        user        = self.user
        base        = self.base_url
        handle      = self.assoc_handle
        cc_default  = core.AMAZON_COUNTRY_CODE_MAP.get(self.country, self.country)
        s, ua = helpers.buildSession(base, self.domain, self.proxy)
        dyn_urls, dyn_hashes = [], []

        self._emit("Solving WAF challenge...")
        try:
            wr = AwsWaf(
                websiteURL=f'{base}/',
                proxy=helpers.normalizeProxy(self.proxy),
                userAgent=ua,
            ).solve()
            if wr['status']:
                s.cookies.set(
                    'aws-waf-token', wr['token'],
                    domain=f'.{self.domain}', path='/',
                )
                logger.info(f"WAF token obtained ({len(wr['token'])} chars)")
            else:
                logger.warning(f"WAF failed: {wr['description']}")
        except Exception as e:
            logger.warning(f"WAF error: {e}")

        self._emit("Loading registration page...")
        r1, s = helpers.get_with_retry(
            s, self.register_url, timeout=HTTP_TIMEOUT,
            proxy=self.proxy, base_url=base, domain=self.domain,
        )
        logger.info(f"Page loaded: {str(r1.url)[:70]}")
        html1 = BeautifulSoup(r1.text, 'html.parser')
        dyn_urls, dyn_hashes = helpers.extractScripts(r1.text)

        if '/ax/claim' not in str(r1.url) and helpers.getHiddenField(html1, 'appActionToken'):
            r3, r2_url = r1, r1.url
        else:
            self._emit("Submitting phone number...")
            f1 = html1.find('form')
            a1 = f1.get('action', '') if f1 else ''
            if a1 and not a1.startswith('http'):
                a1 = f'{base}{a1}'

            claim_data = {
                'appAction': 'SIGNIN_CLAIM_COLLECT',
                'subPageType': 'FullPageUnifiedClaimCollect',
                'claimCollectionWorkflow': 'unified',
                'unifiedAuthTreatment': 'T2',
                'metadata1': helpers.generateMetadata(str(r1.url), f'{base}/', dyn_urls, dyn_hashes, ua, email=phone_short),
                'claimType': 'phoneNumber',
                'countryCode': helpers.phone_country_code(phone, self.country),
                'isServerSideRouting': 'true',
                'anti-csrftoken-a2z': helpers.getHiddenField(html1, 'anti-csrftoken-a2z'),
                'email': f"+{phone}" if not phone.startswith('+') else phone,
                'password': '',
            }
            for inp in html1.find_all('input', {'type': 'hidden'}):
                n = inp.get('name')
                if n and n not in claim_data:
                    claim_data[n] = inp.get('value', '')

            r2 = helpers.postForm(s, a1 or f'{base}/ax/claim', claim_data, r1.url, base)
            r2_url = r2.url
            html2 = BeautifulSoup(r2.text, 'html.parser')
            arb = helpers.getHiddenField(html2, 'arb')

            reg_form = None
            for f in html2.find_all('form'):
                if '/ap/register' in f.get('action', ''):
                    reg_form = f
                    break

            if arb:
                logger.info("Phone claimed (new number)")
                c_email   = helpers.getHiddenField(html2, 'email') or phone_short
                c_country = helpers.getHiddenField(html2, 'countryCode') or cc_default
            elif reg_form:
                logger.info("Number may exist, using register link")
                ei = reg_form.find('input', {'name': 'email'})
                ci = reg_form.find('input', {'name': 'countryCode'})
                c_email   = ei.get('value', phone_short) if ei else phone_short
                c_country = ci.get('value', cc_default) if ci else cc_default
            elif 'SIGNIN_PWD_COLLECT' in r2.text or 'SIGNIN_OTP_COLLECT' in r2.text:
                raise AmazonRegisterError("number_associated")
            else:
                raise AmazonRegisterError("no_arb")

            self._emit("Loading registration form...")
            tf = reg_form or html2.find('form')
            ra = tf.get('action', '') if tf else ''
            if ra and not ra.startswith('http'):
                ra = f'{base}{ra}'

            rd = {
                'claimCollectionLayoutType': 'unifiedAuthClaimCollection',
                'unifiedAuthTreatment': 'T2',
                'countryCode': c_country,
                'email': c_email,
                'anti-csrftoken-a2z': helpers.getHiddenField(html2, 'anti-csrftoken-a2z'),
            }
            if arb:
                rd['arb'] = arb
            for inp in tf.find_all('input', {'type': 'hidden'}):
                n = inp.get('name')
                if n and n not in rd:
                    rd[n] = inp.get('value', '')

            r3 = helpers.postForm(s, ra or f'{base}/ap/register', rd, r2.url, base)
            self._emit("Registration form loaded")

        html3 = BeautifulSoup(r3.text, 'html.parser')
        if not helpers.getHiddenField(html3, 'appActionToken'):
            raise AmazonRegisterError("no_register_form")

        self._emit("Submitting registration...")
        otp_resp = None
        reg_resp = helpers.submitRegister(s, r3, r2_url, phone_short, user, ua, base, dyn_urls, dyn_hashes, cc_default, "first")

        if helpers.isUnusual(reg_resp.text):
            raise AmazonRegisterError("unusual activity")

        reg_url = str(reg_resp.url)

        if helpers.isOtp(reg_resp.text, reg_url):
            self._emit("Registration accepted, OTP page reached")
            otp_resp = reg_resp
        elif helpers.isCaptcha(reg_resp.text):
            self._emit("Captcha challenge detected")
            cp = reg_resp
            for i in range(CAPTCHA_MAX):
                self._emit(f"Solving captcha ({i + 1}/{CAPTCHA_MAX})...")
                cvf = Captcha.solve(
                    s, cp.text, cp.url, base, self.capsolver_key, handle,
                    on_status=self._emit,
                )
                if not cvf:
                    self._emit(f"Captcha intento {i + 1} falló, reintentando...")
                    continue
                if helpers.isOtp(cvf.text, str(cvf.url)):
                    self._emit("Captcha passed, OTP page reached")
                    otp_resp = cvf
                    break
                if helpers.isUnusual(cvf.text):
                    raise AmazonRegisterError("unusual activity")
                if helpers.isRegForm(cvf.text):
                    self._emit("Captcha: reenviando formulario de registro...")
                    rs = helpers.submitRegister(s, cvf, cp.url, phone_short, user, ua, base, dyn_urls, dyn_hashes, cc_default, f"resubmit-{i + 1}")
                    if helpers.isUnusual(rs.text):
                        raise AmazonRegisterError("unusual activity")
                    if helpers.isOtp(rs.text, str(rs.url)):
                        self._emit("Registro reenviado → OTP")
                        otp_resp = rs
                        break
                    cp = rs
                    continue
                elif helpers.isCaptcha(cvf.text):
                    self._emit("Captcha: Amazon pidió otro captcha")
                    cp = cvf
                    continue
                else:
                    cvf_html = BeautifulSoup(cvf.text, 'html.parser')
                    if cvf_html.find('form') and helpers.getHiddenField(cvf_html, 'appActionToken'):
                        self._emit("Captcha: reenviando registro (post-CVF)...")
                        rs = helpers.submitRegister(s, cvf, cp.url, phone_short, user, ua, base, dyn_urls, dyn_hashes, cc_default, f"cvf-resubmit-{i + 1}")
                        if helpers.isOtp(rs.text, str(rs.url)):
                            self._emit("Registro post-CVF → OTP")
                            otp_resp = rs
                            break
                        if helpers.isUnusual(rs.text):
                            raise AmazonRegisterError("unusual activity")
                        cp = rs
                        continue
                    else:
                        self._emit("Captcha: respuesta inesperada, reintentando...")
                        cp = cvf
                        continue
            if not otp_resp:
                raise AmazonRegisterError("captcha_failed")
        elif 'SIGNIN_PWD_COLLECT' in reg_resp.text or 'SIGNIN_OTP_COLLECT' in reg_resp.text:
            raise AmazonRegisterError("number_associated")
        else:
            raise AmazonRegisterError("unexpected_response")

        otp_html = BeautifulSoup(otp_resp.text, 'html.parser')

        contact_form = None
        for f in otp_html.find_all('form'):
            if f.find('input', {'name': 'requestedContactType'}):
                contact_form = f
                break

        if contact_form:
            current_type = contact_form.find('input', {'name': 'requestedContactType'})
            current_val = current_type.get('value', '') if current_type else ''
            if current_val != 'sms':
                self._emit("Switching to SMS verification...")
                ca_data = {}
                for inp in contact_form.find_all('input'):
                    n = inp.get('name')
                    if n:
                        ca_data[n] = inp.get('value', '')
                ca_data['requestedContactType'] = 'sms'
                ca_action = contact_form.get('action', '')
                if ca_action and not ca_action.startswith('http'):
                    ca_action = urljoin(str(otp_resp.url), ca_action)
                if not ca_action:
                    ca_action = f'{base}/ap/cvf/verify'
                otp_resp = helpers.postForm(s, ca_action, ca_data, str(otp_resp.url), base)
                otp_html = BeautifulSoup(otp_resp.text, 'html.parser')

        sms_switch_form = None
        for f in otp_html.find_all('form'):
            if f.find('input', {'name': 'requestedContactType', 'value': 'sms'}):
                sms_switch_form = f
                break

        if sms_switch_form:
            self._emit("Switching verification to SMS...")
            sms_data = {}
            for inp in sms_switch_form.find_all('input'):
                n = inp.get('name')
                if n:
                    sms_data[n] = inp.get('value', '')
            sms_action = sms_switch_form.get('action', '')
            if sms_action and not sms_action.startswith('http'):
                sms_action = urljoin(str(otp_resp.url), sms_action)
            if not sms_action:
                sms_action = f'{base}/ap/cvf/verify'
            switch_resp = helpers.postForm(s, sms_action, sms_data, str(otp_resp.url), base)
            switch_html = BeautifulSoup(switch_resp.text, 'html.parser')
            if switch_html.find('input', {'name': 'code'}) or 'sms' in switch_resp.text.lower():
                otp_resp = switch_resp

        self._emit("Waiting for SMS code...")
        try:
            self.sms_service.markReady(self.phone_data['activationId'])
            sms_timeout = int(os.environ.get("SMS_TIMEOUT", "75"))
            otp_code = self.sms_service.getSMS(
                self.phone_data['activationId'], timeout=sms_timeout,
            )
            if not otp_code:
                raise RuntimeError("Empty SMS code")
            self._emit("SMS code received")
        except Exception:
            raise AmazonRegisterError("sms_timeout")

        self._emit("Submitting OTP...")
        oh = BeautifulSoup(otp_resp.text, 'html.parser')
        otp_form = None
        for c in oh.find_all('form'):
            if c.find('input', {'name': 'code'}):
                otp_form = c
                break
        if not otp_form:
            otp_form = oh.find('form')

        otp_action = otp_form.get('action', '') if otp_form else ''
        if otp_action and not otp_action.startswith('http'):
            otp_action = urljoin(str(otp_resp.url), otp_action)
        if not otp_action:
            otp_action = f'{base}/ap/cvf/verify'

        ou, ohh = helpers.extractScripts(otp_resp.text)
        otp_payload = {}
        if otp_form:
            for inp in otp_form.find_all('input', {'type': 'hidden'}):
                n = inp.get('name')
                if n:
                    otp_payload[n] = inp.get('value', '')
        otp_payload['action']    = 'code'
        otp_payload['code']      = otp_code
        otp_payload['metadata1'] = helpers.generateMetadata(str(otp_resp.url), str(otp_resp.url), ou or dyn_urls, ohh or dyn_hashes, ua, email=phone_short, name=user.name)

        otp_sub = helpers.postForm(s, otp_action, otp_payload, str(otp_resp.url), base)

        success_markers = ['amazon.com/?', '/ref', '/gp/', 'nav_newcust', f'{self.domain}/?', f'{self.domain}/ref']
        if any(x in str(otp_sub.url) for x in success_markers):
            self._emit("Account verified")
            cookies = helpers.export_session_cookies(s, self.domain)
            return {'status': True, 'cookies': cookies, 'session': s}
        else:
            raise AmazonRegisterError("otp_failed")

    def _cancel_phone(self):
        if self.phone_data:
            try:
                self.sms_service.cancelActivation(self.phone_data['activationId'])
                logger.info("Phone cancelled to save credits")
            except Exception:
                pass
            self.phone_data = None

    @staticmethod
    def _error(message: str) -> dict:
        return {"status": False, "message": message}



# Historial de números comprados
NUM_HISTORY = []

def add_to_history(activation_id, phone_full, service_name):
    global NUM_HISTORY
    NUM_HISTORY = [h for h in NUM_HISTORY if h['activation_id'] != activation_id]
    NUM_HISTORY.append({
        'activation_id': activation_id,
        'phone_full': phone_full,
        'service_name': service_name,
        'timestamp': time.time()
    })
    logging.debug(f"📝 Número {phone_full} agregado al historial (total: {len(NUM_HISTORY)})")

def cancel_all_numbers():
    global NUM_HISTORY
    if not NUM_HISTORY:
        return
    logging.debug(f"🔄 Cancelando {len(NUM_HISTORY)} números del historial...")
    for entry in NUM_HISTORY:
        try:
            if entry['service_name'] == 'hero':
                cancel_hero_sms(entry['activation_id'])
            elif entry['service_name'] == '5sim':
                cancel_fivesim(entry['activation_id'])
        except Exception as e:
            logging.debug(f"Error cancelando {entry['phone_full']}: {e}")
    NUM_HISTORY = []
    logging.debug("🗑️ Historial limpiado")

def cancel_number(activation_id, service_name):
    global NUM_HISTORY
    try:
        if service_name == 'hero':
            cancel_hero_sms(activation_id)
        elif service_name == '5sim':
            cancel_fivesim(activation_id)
    except Exception as e:
        logging.debug(f"Error cancelando número {activation_id}: {e}")
    NUM_HISTORY = [h for h in NUM_HISTORY if h['activation_id'] != activation_id]
    logging.debug(f"🗑️ Número {activation_id} removido del historial")

def verify_with_retry(phone, country_code, retries=3):
    """Verifica un número con reintentos en caso de error."""
    for attempt in range(1, retries + 1):
        result = is_phone_registered_sync(phone, country_code)
        if result is not None:
            return result
        logging.warning(f"   ⚠️ Intento {attempt}/{retries} falló para {phone}, reintentando en 2s...")
        time.sleep(2)
    return None

def _is_banned_response(text: str) -> bool:
    """Detecta si la respuesta de Hero SMS es un BANNED."""
    try:
        data = json.loads(text)
        return data.get('title') == 'BANNED'
    except:
        return False

def extract_hidden_inputs(html):
    soup = BeautifulSoup(html, 'html.parser')
    hidden = {}
    for inp in soup.find_all('input', type='hidden'):
        name = inp.get('name')
        value = inp.get('value', '')
        if name:
            hidden[name] = value
    return hidden

def get_current_ip(sess):
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
    try:
        result = string.split(start, 1)[1].split(end, 1)[0]
        return result.strip() if strip else result
    except (IndexError, AttributeError):
        raise ValueError(f"Capture failed: '{start}' -> '{end}' not found")

def capR(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"Extract failed: '{pattern}' not found")
    return match.group(1)

def capS(api_key: str, images: list, question: str) -> dict:
    """Resuelve captcha WAF (AwsWafClassification) con imágenes en base64."""
    capsolver.api_key = api_key
    processed_images = []
    for img in images:
        if isinstance(img, str) and img.startswith('http'):
            try:
                resp = requests.get(img, timeout=10)
                img_base64 = base64.b64encode(resp.content).decode('utf-8')
                processed_images.append(img_base64)
                logging.debug(f"   ✅ Imagen descargada y convertida a base64 ({len(img_base64)} chars)")
            except Exception as e:
                logging.debug(f"   ⚠️ Error descargando imagen, usando URL: {e}")
                processed_images.append(img)
        else:
            processed_images.append(img)
    try:
        result = capsolver.solve({
            "type": "AwsWafClassification",
            "question": f"aws:grid:{question}",
            "images": processed_images
        })
        return result
    except Exception as e:
        logging.debug(f"   ❌ Capsolver solve falló: {e}")
        raise

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
                    raise CAPSolverNoBalance("CapSolver sin saldo o clave inválida")
                else:
                    logging.debug(f"* CapSolver Exception: {e}")
                    continue
            j5 = sess.post(f"{captcha_url}/verify", json={
                "state": {"iv": j4["state"]["iv"], "payload": j4["state"]["payload"]},
                "key": j4["key"], "hmac_tag": j4["hmac_tag"],
                "client_solution": solved,
                "metrics": {"solve_time_millis": random.randint(5000, 8000)},
                "locale": "en-us"
            }).json()
            if not j5.get("captcha_voucher"):
                logging.debug(f"* Captcha Failed => Attempt {attempt + 1}/5")
                continue
            captcha_jwt = j5["captcha_voucher"]
            jwt_client_id = json.loads(base64.urlsafe_b64decode(captcha_jwt.split(".")[1] + "=="))["client_id"]
            json6 = json.dumps({"challengeType": "WAF_ADVERSARIAL_SYNTHETIC_GRID_V2_LEVEL_1", "data": f'"{captcha_jwt}"'}, separators=(",", ":"))
            action_type = json.loads(sess.get(f"https://www.amazon.com/aaut/verify/cvf/{jwt_client_id}?context={urllib.parse.quote(client_ctx)}&options={urllib.parse.quote(json_opt)}&response={urllib.parse.quote(json6)}").headers.get("amz-aamation-resp")).get("actionType")
            logging.debug(f"* WAF Attempt {attempt + 1}/5 => {action_type}")
            if action_type == "PASS":
                return jwt_client_id
        except CAPSolverNoBalance:
            raise
        except Exception as e:
            logging.debug(f"* WAF attempt {attempt+1} error: {e}")
            continue
    raise Exception("WAF Failed After 5 Attempts")

def set_service_enabled(enabled: bool) -> bool:
    global SERVICE_BLOCKED_UNTIL, SERVICE_BLOCKED_REASON
    if enabled:
        SERVICE_BLOCKED_UNTIL = 0
        SERVICE_BLOCKED_REASON = None
    else:
        SERVICE_BLOCKED_UNTIL = time.time() + 3600
        SERVICE_BLOCKED_REASON = 'capsolver_balance'
    try:
        headers = {'x-bot-key': BOT_API_KEY, 'Content-Type': 'application/json'}
        payload = {'enabled': enabled}
        response = requests.post(f"{API_BASE_URL}/admin/bot/toggle-service", json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            logging.info(f"✅ Servicio de generación {'activado' if enabled else 'desactivado'} correctamente")
            return True
        else:
            logging.error(f"❌ Error al cambiar estado del servicio: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ Error al cambiar estado del servicio: {e}")
        return False

def get_number(keys, country_code: str = None) -> Tuple[str, str, str]:
    if isinstance(keys, str):
        keys = [keys]
    if country_code:
        countries_to_try = [country_code]
    else:
        countries_to_try = [HERO_COUNTRY_ORDER[0]]

    key_errors = {}
    for iso_code in countries_to_try:
        hero_country_num = hero_country_map.get(iso_code)
        if not hero_country_num:
            continue
        key_index = 0
        while key_index < len(keys):
            key = keys[key_index]
            logging.debug(f"  📞 Intentando país {iso_code} (código {hero_country_num}) con key {key[:4]}...")
            url = f"{_SMS_API}?api_key={key}&action=getNumber&service=am&country={hero_country_num}"
            try:
                r = requests.get(url, timeout=30).text
                if _is_banned_response(r):
                    if "CHANNELS_LIMIT" in r:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "CHANNELS_LIMIT")
                    else:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "BANNED")
                    logging.warning(f"⚠️ Key {key[:4]} baneada para {iso_code}: {r[:80]}")
                    key_index += 1
                    continue
                if r.startswith("ACCESS_NUMBER"):
                    _, activation_id, phone = r.split(":")
                    phone = phone.strip()
                    logging.debug(f"  ✅ Número obtenido: {phone} (país {iso_code}) con key {key[:4]}")
                    return activation_id, phone, iso_code
                else:
                    if "NO_BALANCE" in r:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "NO_BALANCE")
                    elif "CHANNELS_LIMIT" in r:
                        key_errors[key] = _prioritize_error(key_errors.get(key), "CHANNELS_LIMIT")
                    else:
                        key_errors[key] = _prioritize_error(key_errors.get(key), r[:80])
                    logging.debug(f"  ❌ Falló para {iso_code} con key {key[:4]}: {r[:80]}")
                    key_index += 1
            except Exception as e:
                logging.debug(f"  ❌ Error en {iso_code} con key {key[:4]}: {e}")
                key_index += 1
        logging.debug(f"  🔄 Agotadas todas las keys para {iso_code}")

    if not key_errors:
        raise Exception("No se pudo obtener número con ninguna key (sin errores específicos)")

    total_keys = len(keys)
    no_balance_count = sum(1 for err in key_errors.values() if "NO_BALANCE" in err)
    channels_limit_count = sum(1 for err in key_errors.values() if "CHANNELS_LIMIT" in err)

    if no_balance_count == total_keys:
        logging.error("❌ Todas las keys tienen NO_BALANCE. Apagando servicio indefinidamente.")
        raise SMSNoBalance("Saldo insuficiente en todas las cuentas de SMS. Avisar a administradores para recargar.")

    if channels_limit_count > 0:
        logging.error(f"❌ Al menos una key tiene CHANNELS_LIMIT ({channels_limit_count} keys). Apagando servicio por 30 minutos.")
        raise SMSAccountBannedTemporarily("Al menos una cuenta de SMS está temporalmente baneada (límite de canales). El servicio se desactivará por 30 minutos.")

    error_summary = ", ".join([f"{key[:4]}: {err}" for key, err in key_errors.items()])
    raise Exception(f"No se pudo obtener número. Errores: {error_summary}")

def _prioritize_error(old: Optional[str], new: str) -> str:
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
    return new

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
                    logging.warning(f"⚠️ Key {key[:4]} baneada en get_code, probando siguiente...")
                    break
                if r.startswith("STATUS_OK"):
                    return r.split(":")[1].strip()
                if r == "STATUS_CANCEL":
                    raise Exception("SMS activation canceled")
                if "NO_BALANCE" in r:
                    logging.warning(f"⚠️ Key {key[:4]} sin saldo, probando siguiente...")
                    break
            except Exception as e:
                logging.debug(f"Error en get_code con key {key[:4]}: {e}")
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
                logging.warning(f"⚠️ Key {key[:4]} baneada en set_status, probando siguiente...")
                continue
            logging.debug(f"set_status con key {key[:4]} ejecutado (status {status})")
            return
        except Exception as e:
            logging.warning(f"Error en set_status con key {key[:4]}: {e}")
    logging.error("❌ No se pudo setStatus con ninguna key")

def _api_request(sess, method, url, json_data=None, headers=None, timeout=15):
    if headers is None:
        headers = {}
    if json_data:
        res = sess.request(method, url, json=json_data, headers=headers, timeout=timeout)
    else:
        res = sess.request(method, url, headers=headers, timeout=timeout)
    return res

def new_mail(sess, result_container):
    for api in _MAIL_APIS:
        try:
            method, url, data, *extra = api["create"]()
            headers = extra[0] if extra else {}
            res = _api_request(sess, method, url, data, headers)
            logging.debug(f"API {api['name']} - create status: {res.status_code}, body: {res.text[:200]}")
            if res.status_code not in [200, 201]:
                continue
            resp_data = res.json()
            email = api["get_email"](resp_data)
            token = api["get_token"](resp_data)
            if not token and api.get("uses_cookies"):
                token = sess.cookies.get('PHPSESSID') or sess.cookies.get('session') or 'cookie_based'
                logging.debug(f"   Usando cookie como token: {token[:10]}...")
            if email:
                result_container["email"] = email
                result_container["token"] = token if token else ''
                result_container["api"] = api["name"]
                logging.debug(f"* Email creado: {email} ({api['name']})")
                return
        except Exception as e:
            logging.debug(f"   API {api['name']} falló: {e}")
            continue
    result_container["error"] = "No se pudo crear email con ninguna API"
    logging.error("❌ No se pudo crear email con ninguna API")

def mail_code(sess, token: str, api_name: str, timeout: int = 120) -> str:
    api = None
    for a in _MAIL_APIS:
        if a["name"] == api_name:
            api = a
            break
    if not api:
        raise Exception(f"API {api_name} no encontrada")
    logging.debug(f"* Esperando mail en {api['name']}...")
    if api.get("uses_cookies") and token == 'cookie_based':
        token = sess.cookies.get('PHPSESSID') or sess.cookies.get('session') or ''
    for i in range(timeout // 5):
        time.sleep(5)
        try:
            method, url, data, *extra = api["inbox"](token)
            headers = extra[0] if extra else {}
            res = _api_request(sess, method, url, data, headers)
            logging.debug(f"API {api_name} - inbox status: {res.status_code}, body: {res.text[:200]}")
            resp_data = res.json()
            if not api["has_messages"](resp_data):
                if i % 6 == 0:
                    logging.debug(f"  Esperando... ({i*5}s)")
                continue
            messages = api["get_messages"](resp_data)
            if not messages:
                continue
            msg = messages[0]
            msg_id = api["get_msg_id"](msg)
            method, url, data, *extra = api["read"](token, msg_id)
            headers = extra[0] if extra else {}
            res2 = _api_request(sess, method, url, data, headers)
            logging.debug(f"API {api_name} - read status: {res2.status_code}, body: {res2.text[:200]}")
            body = str(api["get_body"](res2.json()))
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
                    logging.debug(f"* OTP encontrado: {otp}")
                    return otp
        except Exception as e:
            logging.debug(f"  Error: {str(e)[:80]}")
            continue
    raise Exception(f"Mail OTP timeout en {api['name']}")

from playwright.async_api import async_playwright
import asyncio
from playwright.sync_api import sync_playwright
import traceback

def is_phone_registered_sync(phone_number: str, country_code: str = 'MX') -> Optional[bool]:
    logging.debug(f"📞 Verificando número {phone_number}...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logging.error("❌ Playwright no instalado")
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
                page.goto(base_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
                try:
                    page.click('#nav-link-accountList', timeout=15000)
                    page.wait_for_timeout(2000)
                except Exception as e:
                    logging.warning(f"   ⚠️ No se pudo hacer clic en #nav-link-accountList: {e}")
                    browser.close()
                    if attempt < max_attempts:
                        time.sleep(2)
                        continue
                    return None
                try:
                    email_field = page.wait_for_selector('#ap_email, #ap_email_login', state='visible', timeout=10000)
                    if not email_field:
                        raise Exception("No se encontró campo de email")
                    email_field.fill(phone_number)
                    page.wait_for_timeout(1000)
                    page.click('#continue', timeout=5000)
                except Exception as e:
                    logging.warning(f"   ⚠️ Error al llenar email: {e}")
                    browser.close()
                    if attempt < max_attempts:
                        time.sleep(2)
                        continue
                    return None
                page.wait_for_timeout(6000)
                content = page.content()
                if "Parece que eres nuevo en Amazon." in content:
                    logging.debug(f"   ✅ Número {phone_number} NUEVO (disponible)")
                    browser.close()
                    return False
                if "¿Ya tienes una cuenta?" in content or "Para iniciar sesión, ingresa tu contraseña." in content:
                    logging.debug(f"   ✅ Número {phone_number} YA REGISTRADO")
                    browser.close()
                    return True
                if page.query_selector('#ap_password'):
                    logging.debug(f"   ✅ Número {phone_number} YA REGISTRADO (selector)")
                    browser.close()
                    return True
                if page.query_selector('#ap_customer_name'):
                    logging.debug(f"   ✅ Número {phone_number} NUEVO (selector)")
                    browser.close()
                    return False
                logging.warning(f"   ⚠️ Estado desconocido, asumiendo NUEVO")
                browser.close()
                return False
        except Exception as e:
            logging.error(f"❌ Error en intento {attempt}/{max_attempts} para {phone_number}: {e}")
            if attempt < max_attempts:
                time.sleep(2)
            else:
                return None
    return None

async def is_phone_registered(phone_number, country_code='US'):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=random.choice(USER_AGENTS)
        )
        page = await context.new_page()
        await page.goto("https://www.amazon.com/ap/signin")
        await page.fill('#ap_email', phone_number)
        await page.click('#continue')
        await page.wait_for_timeout(3000)
        content = await page.content()
        if await page.query_selector('#ap_password'):
            await browser.close()
            return True
        if await page.query_selector('#ap_customer_name'):
            await browser.close()
            return False
        if "No hemos podido encontrar una cuenta" in content or "We cannot find an account" in content:
            await browser.close()
            return False
        await browser.close()
        return False

def safe_request(sess, method, url, data=None, json_data=None, headers=None, max_retries=3, backoff=2):
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
            if response.status_code in [200, 201, 302, 303]:
                return response
            else:
                logging.warning(f"Intento {attempt}: status {response.status_code} - {response.text[:100]}")
                if response.status_code in [400, 401, 403, 404, 405, 406, 410]:
                    raise Exception(f"Error HTTP {response.status_code}: {response.text[:200]}")
        except Exception as e:
            last_exception = e
            logging.warning(f"Intento {attempt} falló: {e}")
            if attempt < max_retries:
                wait = backoff ** attempt
                logging.debug(f"Reintentando en {wait}s...")
                time.sleep(wait)
            else:
                raise Exception(f"Fallo después de {max_retries} intentos: {last_exception}")
    raise Exception("No se pudo completar la petición")

def process(capsolver_key, hero_keys, email=None, mail_token=None, mail_api=None,
            activation_id=None, sms_phone=None, proxy=None, t=None, country_code='BR'):
    """
    Genera una cuenta de Amazon usando el método rápido (curl_cffi + Capsolver).
    Adaptado para replicar el comportamiento de AmazonAccountCreator.
    """
    if t is None:
        t = time.time()

    max_intentos = 50
    max_num_intentos = 5
    MAX_REG_RETRIES = 20

    # Función auxiliar para normalizar el proxy (similar a helpers.normalizeProxy)
    def normalize_proxy(proxy_str):
        if not proxy_str:
            return None
        # Si ya tiene http:// o https://, lo dejamos
        if proxy_str.startswith('http://') or proxy_str.startswith('https://'):
            return proxy_str
        # Si tiene formato user:pass@host:port, añadimos http://
        if '@' in proxy_str:
            return f"http://{proxy_str}"
        # Si solo host:port
        return f"http://{proxy_str}"

    for intento in range(1, max_intentos + 1):
        for num_attempt in range(1, max_num_intentos + 1):
            try:
                activation_id, sms_phone, purchase_country = get_number(hero_keys)
                add_to_history(activation_id, sms_phone, 'hero')
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

            for reg_retry in range(1, MAX_REG_RETRIES + 1):
                try:
                    logger.debug(f"\n{'='*60}")
                    logger.debug(f"INTENTO EXTERNO #{intento} - NUM # {num_attempt} - REG RETRY #{reg_retry}")
                    logger.debug(f"{'='*60}")

                    info = gen_profile()
                    assoc_handle = "anywhere_v2_us"
                    arb = "88b7dd8f-6e15-491a-87df-9351dcbfc80f"
                    password = "dfbc1992"

                    # ---------- CREAR SESIÓN CON HEADERS COMPLETOS ----------
                    sess = curl_requests.Session()
                    sess.impersonate = "chrome"
                    sess.verify = False  # Puede cambiarse a True si se usa certifi

                    # Headers completos (igual que en helpers.buildSession)
                    sess.headers.update({
                        "User-Agent": info["user_agent"],
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "keep-alive",
                        "Cache-Control": "max-age=0",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "sec-ch-ua": '"Chromium";v="147", "Not?A_Brand";v="99"',
                        "sec-ch-ua-mobile": "?1",
                        "sec-ch-ua-platform": '"Android"' if "Android" in info["user_agent"] else '"Windows"',
                        "DNT": "1",
                    })

                    # Configurar proxy
                    if proxy:
                        normalized_proxy = normalize_proxy(proxy)
                        sess.proxies = {"http": normalized_proxy, "https": normalized_proxy}
                        logger.debug(f"Proxy configurado: {normalized_proxy}")

                    # ---------- EMAIL EN PARALELO ----------
                    mail_result = {}
                    mail_thread = threading.Thread(target=new_mail, args=(sess, mail_result))
                    mail_thread.start()

                    # Petición inicial /ax/claim (como en versión antigua)
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

                    # ---------- PRIMER POST (claim) ----------
                    # Extraer todos los campos ocultos del formulario (como en la versión antigua)
                    # Primero hacemos GET a la página de registro para obtener el formulario inicial
                    initial_url = (
                        "https://www.amazon.com/ap/register?openid.mode=checkid_setup"
                        "&openid.ns=http://specs.openid.net/auth/2.0"
                        "&openid.identity=http://specs.openid.net/auth/2.0/identifier_select"
                        "&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select"
                        "&openid.assoc_handle=anywhere_v2_us"
                        "&openid.return_to=https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button"
                    )
                    # Obtenemos la página para extraer anti-csrftoken-a2z y otros campos
                    resp_initial = sess.get(initial_url, timeout=30)
                    soup_initial = BeautifulSoup(resp_initial.text, 'html.parser')
                    anti_csrf = None
                    for inp in soup_initial.find_all('input', type='hidden'):
                        if inp.get('name') == 'anti-csrftoken-a2z':
                            anti_csrf = inp.get('value')
                            break
                    if not anti_csrf:
                        # Buscar también en el texto con regex
                        match = re.search(r'name="anti-csrftoken-a2z"\s+value="([^"]+)"', resp_initial.text)
                        if match:
                            anti_csrf = match.group(1)

                    # Datos del primer POST (claim)
                    data1 = {
                        "arb": arb,
                        "email": email,
                        "claimCollectionLayoutType": "unifiedAuthClaimCollection",
                        "anti-csrftoken-a2z": anti_csrf if anti_csrf else "",
                    }
                    # Añadir cualquier otro campo oculto que aparezca en el formulario
                    for inp in soup_initial.find_all('input', type='hidden'):
                        n = inp.get('name')
                        if n and n not in data1:
                            data1[n] = inp.get('value', '')

                    req1 = safe_request(
                        sess,
                        "POST",
                        initial_url,
                        data=data1,
                        headers={"Referer": initial_url, "Origin": "https://www.amazon.com"},
                        max_retries=3
                    )

                    if req1 is None or req1.status_code != 200 or "appActionToken" not in req1.text:
                        raise Exception("req1 falló")

                    # Extraer campos ocultos de la respuesta
                    soup1 = BeautifulSoup(req1.text, 'html.parser')
                    appActionToken = None
                    workflowState = None
                    openid_return_to = None
                    prevRID = None
                    for inp in soup1.find_all('input', type='hidden'):
                        name = inp.get('name')
                        value = inp.get('value', '')
                        if name == 'appActionToken':
                            appActionToken = value
                        elif name == 'workflowState':
                            workflowState = value
                        elif name == 'openid.return_to':
                            openid_return_to = value
                        elif name == 'prevRID':
                            prevRID = value
                    if not appActionToken:
                        raise Exception("No se encontró appActionToken")

                    # ---------- REGISTRO ----------
                    data2 = {
                        "appActionToken": appActionToken,
                        "appAction": "REGISTER",
                        "shouldShowPersistentLabels": "true",
                        "openid.return_to": openid_return_to or "",
                        "prevRID": prevRID or "",
                        "workflowState": workflowState or "",
                        "customerName": info["full_name"],
                        "email": email,
                        "password": password,
                        "showPasswordChecked": "true"
                    }
                    # Añadir anti-csrftoken-a2z si aparece en la respuesta
                    anti_csrf2 = None
                    for inp in soup1.find_all('input', type='hidden'):
                        if inp.get('name') == 'anti-csrftoken-a2z':
                            anti_csrf2 = inp.get('value')
                            break
                    if anti_csrf2:
                        data2['anti-csrftoken-a2z'] = anti_csrf2

                    req2 = safe_request(
                        sess,
                        "POST",
                        "https://www.amazon.com/ap/register",
                        data=data2,
                        headers={"Referer": req1.url, "Origin": "https://www.amazon.com"},
                        max_retries=3
                    )

                    # Pausa aleatoria (0.5-1.5s)
                    time.sleep(random.uniform(0.5, 1.5))

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
                        try:
                            verifyToken = find(req2.text, 'name="verifyToken" value="', '"')
                        except:
                            verifyToken = None

                        dataExternalId = capR(r'"data-external-id":\s*"([^"]+)"', req2.text)
                        try:
                            anti_csrf_waf = find(req2.text, "name='anti-csrftoken-a2z' value='", "'")
                        except:
                            anti_csrf_waf = ""

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
                            "anti-csrftoken-a2z": anti_csrf_waf,
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
                            "verifyToken": verifyToken if verifyToken else ""
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

                        logger.debug(f"📄 req4 status: {req4.status_code}")
                        logger.debug(f"📄 req4 URL: {req4.url}")
                        try:
                            verifyToken = find(req4.text, 'name="verifyToken" value="', '"')
                        except:
                            if not verifyToken:
                                verifyToken = ""
                    else:
                        try:
                            verifyToken = find(req2.text, 'name="verifyToken" value="', '"')
                        except:
                            verifyToken = ""

                    if not verifyToken:
                        html_content = req2.text
                        match = re.search(r'name="verifyToken"\s+value="([^"]+)"', html_content)
                        if match:
                            verifyToken = match.group(1)
                            logger.debug(f"VerifyToken encontrado vía regex: {verifyToken}")
                        else:
                            if 'req4' in locals():
                                match = re.search(r'name="verifyToken"\s+value="([^"]+)"', req4.text)
                                if match:
                                    verifyToken = match.group(1)
                                    logger.debug(f"VerifyToken encontrado vía regex en req4: {verifyToken}")

                    if not verifyToken:
                        logger.warning("⚠️ No se pudo obtener verifyToken, pero continuamos...")

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
                        "verifyToken": verifyToken if verifyToken else "",
                        "code": otp_code
                    }
                    # Añadir anti-csrftoken-a2z si existe en req5
                    req5 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data5)
                    try:
                        anti_csrf_otp = find(req5.text, "name='anti-csrftoken-a2z' value='", "'")
                    except:
                        anti_csrf_otp = ""
                    try:
                        verifyToken = find(req5.text, 'name="verifyToken" value="', '"')
                    except:
                        verifyToken = ""

                    data6 = {
                        **base_openid,
                        "anti-csrftoken-a2z": anti_csrf_otp,
                        "verifyToken": verifyToken if verifyToken else "",
                        "cvf_phone_cc": amazon_cc,
                        "cvf_phone_num": sms_phone,
                        "cvf_action": "collect"
                    }
                    req6 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data6)

                    # Pausa antes de SMS
                    time.sleep(random.uniform(1.0, 2.0))

                    logger.debug("* Esperando SMS...")
                    sms_code = get_code(hero_keys, activation_id)
                    logger.debug(f"SMS Code: {sms_code}")
                    set_status(hero_keys, activation_id, 6)

                    try:
                        anti_csrf_sms = find(req6.text, "name='anti-csrftoken-a2z' value='", "'")
                    except:
                        anti_csrf_sms = ""
                    try:
                        verifyToken = find(req6.text, 'name="verifyToken" value="', '"')
                    except:
                        verifyToken = ""

                    data7 = {
                        **base_openid,
                        "anti-csrftoken-a2z": anti_csrf_sms,
                        "verificationPageContactType": "sms",
                        "verifyToken": verifyToken if verifyToken else "",
                        "code": sms_code,
                        "cvf_action": "code",
                        "resendContactType": "sms"
                    }
                    req7 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data7)

                    if "entered already exists with another account" in req7.text:
                        logger.debug("Número ya registrado")
                        cancel_number(activation_id, 'hero')
                        cancel_all_numbers()
                        raise Exception("PERMANENT_NUMBER_ALREADY_REGISTERED")

                    if "new_account=1" not in req7.url:
                        logger.debug("Cuenta no creada")
                        raise Exception("REGISTRATION_FAILED")

                    # ---------- DIRECCIÓN (como en versión antigua) ----------
                    logger.debug("* Agregando dirección...")
                    try:
                        csrf_addr = urllib.parse.quote(find(req7.text, "name='csrfToken' value='", "'"))
                    except:
                        csrf_addr = ""
                    try:
                        customer_id = find(req7.text, 'name="address-ui-widgets-obfuscated-customerId" value="', '"')
                    except:
                        customer_id = ""
                    try:
                        wizard_id = find(req7.text, 'name="address-ui-widgets-address-wizard-interaction-id" value="', '"')
                    except:
                        wizard_id = ""
                    try:
                        prev_token = find(req7.text, 'name="address-ui-widgets-previous-address-form-state-token" value="', '"')
                    except:
                        prev_token = ""
                    try:
                        widget_csrf = urllib.parse.quote(find(req7.text, 'name="address-ui-widgets-csrfToken" value="', '"'))
                    except:
                        widget_csrf = ""
                    try:
                        form_load = find(req7.text, 'name="address-ui-widgets-form-load-start-time" value="', '"')
                    except:
                        form_load = ""

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

                    if "PERMANENT_UNUSUAL_ACTIVITY" in error_str or "detected unusual activity" in error_str.lower():
                        logger.debug("🔄 Actividad inusual detectada → reintentando con nueva sesión (mismo número)")
                        # Limpiar cookies y headers para la nueva sesión (se reinicia el bucle)
                        continue

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
                        break
                    else:
                        if reg_retry == MAX_REG_RETRIES:
                            logger.warning(f"Agotados reintentos para este número. Cancelando.")
                            if activation_id:
                                set_status(hero_keys, activation_id, 8)
                            break
                        else:
                            logger.debug(f"Reintentando con el mismo número (retry {reg_retry+1}/{MAX_REG_RETRIES})")
                            time.sleep(2)
                            continue

            if not registration_success:
                continue
            else:
                pass

    raise Exception(f"Se agotaron los {max_intentos} intentos externos")
# ========== MAPA DE PAÍSES ==========
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

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amazon_cookie_api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def close_overlays(page):
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
            element = await page.wait_for_selector(selector, timeout=2000)
            if element:
                await element.click()
                await page.wait_for_timeout(500)
        except:
            pass
    try:
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(500)
    except:
        pass

GOOD_SESSIONS = {}
SESSION_LIFETIME = 3600

def add_good_session(session_id):
    GOOD_SESSIONS[session_id] = {
        "last_used": time.time(),
        "success_count": GOOD_SESSIONS.get(session_id, {}).get("success_count", 0) + 1
    }
    logger.debug(f"✅ Sesión {session_id} marcada como buena (total: {len(GOOD_SESSIONS)})")

def get_best_session():
    if not GOOD_SESSIONS:
        return None
    best = max(GOOD_SESSIONS.items(), key=lambda x: (x[1]["last_used"], x[1]["success_count"]))
    session_id = best[0]
    now = time.time()
    expired = [sid for sid, data in GOOD_SESSIONS.items() if now - data["last_used"] > SESSION_LIFETIME]
    for sid in expired:
        del GOOD_SESSIONS[sid]
        logger.debug(f"🗑️ Sesión {sid} expirada")
    return session_id

def is_service_enabled():
    global SERVICE_BLOCKED_UNTIL, SERVICE_BLOCKED_REASON
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
    try:
        response = requests.get(
            f"{API_BASE_URL}/service-status-for-generator",
            headers={'x-bot-key': BOT_API_KEY},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('enabled', False):
                SERVICE_BLOCKED_REASON = None
                SERVICE_BLOCKED_UNTIL = 0
                return True
            else:
                return time.time() < SERVICE_BLOCKED_UNTIL
        else:
            return time.time() < SERVICE_BLOCKED_UNTIL
    except Exception:
        return time.time() < SERVICE_BLOCKED_UNTIL

def test_proxy(session, max_retries=3):
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
    try:
        pattern = f'{re.escape(start)}(.*?){re.escape(end)}'
        matches = re.finditer(pattern, string)
        for i, match in enumerate(matches, 1):
            if i == occurrence:
                return match.group(1)
        return None
    except Exception:
        return None

def check_user_credits(token, required=3):
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
    try:
        current_url = page.url
        logger.debug(f"📍 [{step_name}] URL actual: {current_url}")
        return current_url
    except Exception as e:
        logger.warning(f"⚠️ No se pudo obtener URL en paso {step_name}: {e}")
        return None

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
                                if isinstance(coords, list):
                                    for item in coords:
                                        if isinstance(item, dict):
                                            points.append({'x': int(item['x']), 'y': int(item['y'])})
                                        elif isinstance(item, list) and len(item) == 2:
                                            points.append({'x': int(item[0]), 'y': int(item[1])})
                                        else:
                                            logger.warning(f"   Formato de coordenada desconocido: {item}")
                                elif isinstance(coords, str):
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

def solve_funcaptcha_capsolver(page_url, site_key, surl=None):
    if not CAPSOLVER_API_KEY:
        return None
    capsolver.api_key = CAPSOLVER_API_KEY
    try:
        task = {
            "type": "FunCaptchaTaskProxyless",
            "websiteURL": page_url,
            "websitePublicKey": site_key,
        }
        if surl:
            task["funcaptchaApiJSSubdomain"] = surl
        logger.debug(f"   Intentando Capsolver con site_key: {site_key[:10]}...")
        result = capsolver.solve(task)
        if result and result.get('solution', {}).get('token'):
            token = result['solution']['token']
            logger.debug(f"   ✅ Token obtenido con Capsolver")
            return token
        else:
            logger.warning(f"   Capsolver falló: {result}")
            return None
    except Exception as e:
        logger.warning(f"   Capsolver error: {e}")
        return None

def solve_funcaptcha_2captcha(page_url, site_key, surl=None):
    if not API_KEY_2CAPTCHA:
        return None
    site_key = site_key.strip()
    if not site_key:
        return None
    if surl and not surl.startswith('http'):
        surl = None
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
        logger.debug(f"   Probando 2captcha con {config['desc']} (site_key: {site_key[:10]}...)")
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
    if not API_KEY_ANTICAPTCHA:
        return None
    try:
        from anticaptchaofficial.funcaptchaproxyless import FunCaptchaTaskProxyless
        solver = FunCaptchaTaskProxyless()
    except ImportError:
        try:
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
    site_key = None
    surl = None
    iframe = None
    for _ in range(15):
        iframe = await page.query_selector('#cvf-aamation-challenge-iframe')
        if iframe:
            src = await iframe.get_attribute('src')
            if src and src != 'about:blank' and 'arkoselabs' in src:
                break
        await page.wait_for_timeout(1000)
    if iframe:
        src = await iframe.get_attribute('src')
        if src:
            pk_match = re.search(r'[?&]pk=([A-Za-z0-9_-]{20,})', src)
            if pk_match:
                site_key = pk_match.group(1)
                logger.debug(f"   Site_key desde src pk: {site_key}")
            surl_match = re.search(r'surl=([^&]+)', src)
            if surl_match:
                surl_candidate = surl_match.group(1)
                if surl_candidate.startswith('http'):
                    surl = surl_candidate
                else:
                    from urllib.parse import unquote
                    surl_decoded = unquote(surl_candidate)
                    if surl_decoded.startswith('http'):
                        surl = surl_decoded
                logger.debug(f"   Surl desde src: {surl}")
    page_content = await page.content()
    pub_match = re.search(r'"data-public-key":\s*"([^"]+)"', page_content)
    if pub_match:
        site_key = pub_match.group(1)
        logger.debug(f"   Site_key desde data-public-key: {site_key}")
    if not site_key:
        uuid_match = re.search(r'"data-external-id":\s*"([A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12})"', page_content, re.IGNORECASE)
        if uuid_match:
            site_key = uuid_match.group(1)
            logger.debug(f"   Site_key (UUID) desde script: {site_key}")
        else:
            alnum_match = re.search(r'"data-external-id":\s*"([A-Za-z0-9]{20,})"', page_content)
            if alnum_match:
                site_key = alnum_match.group(1)
                logger.debug(f"   Site_key (alfanumérico) desde script: {site_key}")
    if site_key and '%' in site_key:
        from urllib.parse import unquote
        site_key = unquote(site_key)
        logger.debug(f"   Site_key decodificado: {site_key}")
    return site_key, surl

async def handle_captcha_if_present(page, step_name="captcha"):
    logger.debug(f"🔍 Verificando captcha en paso: {step_name}")
    await page.wait_for_timeout(3000)
    content = await page.content()
    coordinate_indicators = ["Resuelve esta adivinanza", "Elija todo", "Selecciona todas las imágenes", "Seleccione todo"]
    if any(indicator in content for indicator in coordinate_indicators):
        logger.warning("⚠️ Captcha de coordenadas detectado")
        max_global_attempts = 100
        global_attempt = 0
        captcha_resuelto = False
        while global_attempt < max_global_attempts and not captcha_resuelto:
            global_attempt += 1
            logger.debug(f"   --- Intento global #{global_attempt} ---")
            canvas_before = await page.query_selector('canvas')
            canvas_id_before = None
            if canvas_before:
                canvas_id_before = await canvas_before.get_attribute('data-challenge-id')
                if not canvas_id_before:
                    box = await canvas_before.bounding_box()
                    canvas_id_before = f"{box['x']}_{box['y']}_{box['width']}_{box['height']}" if box else None
                logger.debug(f"   Canvas ID actual: {canvas_id_before}")
            exito = await solve_coordinate_captcha(page, "coord", round_num=global_attempt)
            if not exito:
                logger.warning("   No se obtuvo consenso entre las respuestas. Refrescando canvas...")
                await click_refresh_button(page)
                await page.wait_for_timeout(3000)
                continue
            await page.wait_for_timeout(2000)
            if await page.query_selector('#cvf-input-code, #cvf-input-otp, input[name="otpCode"]'):
                logger.debug("   ✅ Pantalla SMS detectada. Captcha completado.")
                captcha_resuelto = True
                break
            if await page.query_selector('#ap_customer_name'):
                logger.debug("   ✅ Pantalla de registro detectada. Captcha completado.")
                captcha_resuelto = True
                break
            if await page.query_selector('#ap_email'):
                logger.warning("   🚫 Redirección a login después de resolver captcha.")
                await take_screenshot(page, "redirigido_login_despues_captcha")
                raise Exception("AMAZON_REDIRECTED_TO_LOGIN")
            canvas_exists = await page.query_selector('canvas')
            if not canvas_exists:
                logger.debug("   ✅ Canvas desaparecido, captcha completado.")
                captcha_resuelto = True
                break
            error_incorrecto = await page.query_selector('.a-alert-content:has-text("Incorrecto"), div:has-text("Incorrecto")')
            error_timeout = await page.query_selector('.a-alert-content:has-text("superado el límite de tiempo"), div:has-text("límite de tiempo")')
            if error_incorrecto or error_timeout:
                tipo = "incorrectas" if error_incorrecto else "timeout"
                logger.warning(f"   ❌ Error detectado: coordenadas {tipo}.")
                await take_screenshot(page, f"error_coordenadas_{tipo}")
                raise Exception(f"CAPTCHA_ERROR: coordenadas {tipo}")
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
    title = await page.title()
    if "Confirma tu identidad" in title or "Verify your identity" in title:
        logger.debug("   Página 'Confirma tu identidad' detectada")
        await page.wait_for_timeout(3000)
        page_content = await page.content()
        has_arkose = bool(re.search(r'acic\.setupACIC', page_content)) or bool(await page.query_selector('#cvf-aamation-challenge-iframe'))
        if not has_arkose:
            logger.debug("   No se detectó FunCaptcha real. Asumiendo página de verificación SMS/WhatsApp.")
            return False
        start_button = None
        target_frame = None
        for _ in range(15):
            for frame in page.frames:
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
                            start_button = btn
                            target_frame = frame
                            break
                    except:
                        continue
                if start_button:
                    break
            if start_button:
                break
            await page.wait_for_timeout(1000)
        if start_button:
            logger.debug("   ✅ Botón 'Iniciar rompecabezas' encontrado, haciendo clic...")
            await start_button.click()
            await page.wait_for_timeout(5000)
            iframe = await page.wait_for_selector('#cvf-aamation-challenge-iframe', timeout=15000)
            src = await iframe.get_attribute('src')
            if not src or src == 'about:blank':
                for _ in range(10):
                    src = await iframe.get_attribute('src')
                    if src and src != 'about:blank':
                        break
                    await page.wait_for_timeout(1000)
            site_key = None
            surl = None
            if src:
                pk_match = re.search(r'[?&]pk=([A-Za-z0-9_-]{20,})', src)
                if pk_match:
                    site_key = pk_match.group(1)
                    logger.debug(f"   Site_key desde src pk: {site_key}")
                surl_match = re.search(r'surl=([^&]+)', src)
                if surl_match:
                    surl_candidate = surl_match.group(1)
                    if surl_candidate.startswith('http'):
                        surl = surl_candidate
                    else:
                        from urllib.parse import unquote
                        surl_decoded = unquote(surl_candidate)
                        if surl_decoded.startswith('http'):
                            surl = surl_decoded
                    logger.debug(f"   Surl desde src: {surl}")
            if not site_key:
                site_key, surl = await extract_site_key_robust(page)
            if site_key:
                logger.debug(f"   Intentando resolver FunCaptcha con site_key: {site_key}")
                token = solve_funcaptcha_capsolver(page.url, site_key, surl)
                if not token and API_KEY_2CAPTCHA:
                    token = solve_funcaptcha_2captcha(page.url, site_key, surl)
                if not token and API_KEY_ANTICAPTCHA:
                    token = solve_funcaptcha_anticaptcha(page.url, site_key, surl)
                if token:
                    await page.evaluate(f"""
                        document.getElementById('cvf_aamation_response_token').value = '{token}';
                        document.getElementById('cvf-aamation-challenge-form').submit();
                    """)
                    await page.wait_for_load_state('domcontentloaded', timeout=30000)
                    logger.debug("   ✅ FunCaptcha resuelto")
                    return True
                else:
                    logger.warning("   Falló resolución del FunCaptcha")
                    raise Exception("FUNCAPTCHA_NO_TOKEN")
            else:
                logger.warning("   No se pudo obtener site_key después del clic")
                raise Exception("FUNCAPTCHA_NO_SITEKEY")
        else:
            logger.warning("   ❌ No se encontró botón 'Iniciar rompecabezas'")
            raise Exception("FUNCAPTCHA_NOT_DETECTED")
    return False

async def click_refresh_button(page):
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
                await page.wait_for_timeout(2000)
                return True
        except Exception:
            continue
    logger.debug("   ⚠️ No se encontró botón de refrescar, continuando sin refrescar")
    error_incorrecto = await page.query_selector('.a-alert-content:has-text("Incorrecto"), div:has-text("Incorrecto. Vuelva a intentarlo.")')
    if error_incorrecto:
        logger.warning("❌ Error detectado: coordenadas incorrectas. Reintentando internamente...")
    raise Exception("AMAZON_CAPTCHA_ERROR")
    return False

async def solve_coordinate_captcha(page, step_name="coordinate", round_num=1):
    NUM_REQUESTS = 5
    MIN_MATCHES = 2
    TIMEOUT = 50
    logger.debug(f"   Resolviendo captcha: {NUM_REQUESTS} peticiones, buscando {MIN_MATCHES} coincidencias (timeout {TIMEOUT}s)")
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
    valid_responses = []
    tasks = [asyncio.create_task(fetch_one()) for _ in range(NUM_REQUESTS)]
    pending = tasks.copy()
    start_time = time.time()
    best_cells_tuple = None
    best_points = None
    while pending and (time.time() - start_time) < TIMEOUT:
        done, pending = await asyncio.wait(pending, timeout=1, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                points = task.result()
            except Exception as e:
                logger.debug(f"   Tarea falló: {e}")
                continue
            if points and len(points) == 5:
                cells = coords_to_cells(points)
                if len(cells) == 5:
                    cells_tuple = tuple(sorted(cells))
                    logger.debug(f"   Respuesta válida: celdas {cells_tuple}")
                    valid_responses.append((cells_tuple, points))
                    from collections import Counter
                    counter = Counter(cell_set for cell_set, _ in valid_responses)
                    most_common, count = counter.most_common(1)[0]
                    if count >= MIN_MATCHES:
                        logger.debug(f"   ✅ Alcanzadas {count} coincidencias. Usando celdas {most_common}")
                        best_cells_tuple = most_common
                        for c, pts in valid_responses:
                            if c == best_cells_tuple:
                                best_points = pts
                                break
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
    for t in pending:
        t.cancel()
    if not best_points:
        logger.warning(f"   No se alcanzaron {MIN_MATCHES} coincidencias tras {len(valid_responses)} respuestas válidas")
        return False
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
    start = time.time()
    last_resend = start
    while time.time() - start < timeout_total:
        code = None
        for s in SMS_SERVICES:
            if s['name'] == service_name and s['enabled']:
                code = await s['get_code'](service_id, timeout=3)
                if code:
                    return code
                break
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

# ===================================================================
# SMS SERVICES
# ===================================================================
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
                iso_code = COUNTRY_NAME_TO_CODE.get(country_name)
                if iso_code:
                    prices[iso_code] = float(cost)
                else:
                    logger.debug(f"⚠️ País '{country_name}' no mapeado a ISO, se ignora")
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

def get_phone_number_sync(country_code, force_service=None, force_country=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_phone_number(country_code, force_service, force_country))
    finally:
        loop.close()

def get_hero_sms_code_sync(activation_id, timeout: int = TIMEOUT_SMS):
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

async def get_phone_number(account_country, force_service=None, force_country=None):
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
                    break
                except SMSAccountBannedTemporarily as e:
                    logger.warning(f"Hero SMS baneado temporalmente en {country}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Hero SMS error en {country}: {e}")
                    continue
            return None
        elif force_service == '5sim':
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
    channels_limit_detected = False
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
            break
        except SMSAccountBannedTemporarily as e:
            logger.warning(f"⚠️ Hero SMS baneado temporalmente en {country}: {e}")
            channels_limit_detected = True
            continue
        except Exception as e:
            logger.debug(f"⚠️ Hero SMS error en {country}: {e}")
            continue
    if channels_limit_detected:
        logger.error("❌ CHANNELS_LIMIT en todos los países de Hero SMS. Deteniendo proceso.")
        raise SMSAccountBannedTemporarily("Límite de canales alcanzado en todos los países. El servicio se desactivará.")
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
    content = await page.content()
    match = re.search(r'Resueltos:\s*(\d+)\s*(?:de|Necesarios:)\s*(\d+)', content, re.IGNORECASE)
    if match:
        resolved = int(match.group(1))
        needed = int(match.group(2))
        logger.debug(f"📊 Progreso captcha (ES): {resolved}/{needed}")
        return resolved, needed
    match_en = re.search(r'Solved:\s*(\d+)\s*(?:of|Needed:)\s*(\d+)', content, re.IGNORECASE)
    if match_en:
        resolved = int(match_en.group(1))
        needed = int(match_en.group(2))
        logger.debug(f"📊 Captcha progress (EN): {resolved}/{needed}")
        return resolved, needed
    logger.debug("📊 No se pudo leer el progreso, se asume 0/3")
    return 0, 3

async def wait_for_canvas_change(page, previous_canvas_id=None, timeout=5):
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
        error_elem = await page.query_selector('.a-alert-content:has-text("Incorrecto"), div:has-text("Incorrecto. Vuelva a intentarlo.")')
        if error_elem:
            logger.debug("   ❌ Mensaje de error detectado")
            return 'error'
        if await page.query_selector('#cvf-input-code, #cvf-input-otp, input[name="otpCode"]'):
            logger.debug("   📱 Campo SMS detectado")
            return 'sms'
        if await page.query_selector('#ap_customer_name'):
            logger.debug("   📝 Formulario de registro detectado")
            return 'register'
        if await page.query_selector('#ap_email'):
            logger.warning("   🚫 Redirigido a login")
            return 'login'
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
    try:
        await page.wait_for_function('document.readyState === "complete"', timeout=timeout*1000)
        await page.wait_for_timeout(500)
        return await page.content()
    except Exception as e:
        logger.warning(f"⚠️ Error en safe_get_content: {e}")
        await page.wait_for_timeout(2000)
        return await page.content()

async def block_resources(route):
    resource_type = route.request.resource_type
    if resource_type in ['image', 'font', 'media']:
        await route.abort()
    else:
        await route.continue_()

async def block_heavy_resources(route):
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

# ===================================================================
# FUNCIÓN PRINCIPAL DE CREACIÓN DE CUENTA (OPTIMIZADA CON REINTENTOS INTERNOS)
# ===================================================================
async def create_amazon_account(country_code, add_address_flag=True, max_retries=None, max_internal_retries=10, service_preference=None):
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
            logger.debug("🔄 Probando proxy...")
            ok, ip = test_proxy(session)
            if not ok:
                logger.error(f"   ❌ Proxy no funciona: {ip}")
                raise Exception(f"Proxy error: {ip}")
            logger.debug(f"   ✅ Proxy OK - IP pública: {ip}")
            logger.debug("🔑 Generando credenciales...")
            password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
            first_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            last_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            fullname = f"{first_name} {last_name}"
            account_data['password'] = password
            account_data['name'] = fullname
            logger.debug(f"   👤 Nombre: {fullname}")
            logger.debug(f"   🔐 Contraseña: {password}")
            try:
                phone_info = await get_phone_number(country_code, force_service=service_preference)
                if not phone_info:
                    raise Exception("No se pudo obtener número de teléfono")
                sms_phone = phone_info['local']
                service_id = phone_info['service_id']
                service_name = phone_info['service_name']
                purchase_country = phone_info['purchase_country']
                logger.debug(f"Número obtenido: {phone_info['full']} (servicio: {service_name}, país: {purchase_country})")
                account_data['phone'] = sms_phone
                account_data['purchase_country'] = purchase_country
                add_to_history(service_id, phone_info['full'], service_name)
            except SMSAccountBannedTemporarily as e:
                logger.error(f"❌ CHANNELS_LIMIT en todas las keys: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Error obteniendo número: {e}")
                raise
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

            # ----- BUCLE DE REINTENTO INTERNO (misma IP, misma página, MISMO NÚMERO) -----
            internal_attempt = 0
            registration_success = False
            last_error = None

            while internal_attempt < max_internal_retries and not registration_success:
                internal_attempt += 1
                logger.debug(f"🔄 Intento interno {internal_attempt}/{max_internal_retries} (misma IP)")

                # Si no es el primer intento, cerrar página y abrir nueva (mismo contexto)
                if internal_attempt > 1:
                    await page.close()
                    page = await context.new_page()

                try:
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

                    # ====== DETECCIÓN DE NÚMERO YA REGISTRADO ======
                    if "claim?" in page.url.lower():
                        logger.warning("⚠️ Número ya registrado. Cancelando y comprando otro...")
                        if service_id:
                            try:
                                if service_name == 'hero':
                                    await cancel_hero_sms(service_id)
                                elif service_name == '5sim':
                                    await cancel_fivesim(service_id)
                                logger.debug(f"   ✅ Número {phone_info['full']} cancelado")
                            except Exception as e:
                                logger.debug(f"   ⚠️ No se pudo cancelar (probablemente EARLY_CANCEL_DENIED): {e}")
                        # Forzar compra de nuevo número en el siguiente intento global
                        phone_info = None
                        # Salir del bucle interno y del global para recomprar
                        raise Exception("NUMBER_ALREADY_REGISTERED_RECYCLE")

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
                            logger.warning("   🔄 Redirigido a login. Reiniciando...")
                            # No cancelamos número, solo reiniciamos la página
                            await page.close()
                            page = await context.new_page()
                            continue
                        elif "Lo sentimos" in page_content or "no podemos crear tu cuenta" in page_content:
                            logger.warning("   ❌ Error de Amazon. Reiniciando sin cancelar número...")
                            # Mantener el número, solo reiniciar página
                            await page.close()
                            page = await context.new_page()
                            continue
                        else:
                            logger.debug("   ℹ️ No se detectó error. Esperando 4 segundos...")
                            await page.wait_for_timeout(4000)
                            try:
                                await page.wait_for_selector('#ap_customer_name', state='visible', timeout=2000)
                                logger.debug("   ✅ Formulario cargado automáticamente")
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
                                logger.warning(f"   NÚMERO INVÁLIDO -> comprando otro")
                                if service_id:
                                    try:
                                        if service_name == 'hero':
                                            await cancel_hero_sms(service_id)
                                        elif service_name == '5sim':
                                            await cancel_fivesim(service_id)
                                    except Exception:
                                        pass
                                phone_info = None
                                raise Exception("NUMERO_INVALIDO_RECARGAR")
                            if "Mínimo 6 caracteres requeridos" in content or "Minimo 6 caracteres requeridos" in content:
                                logger.warning(f"   CONTRASEÑA VACÍA (intento {submit_attempt}) -> reintentando")
                                continue
                            if "El número de teléfono móvil ya está en uso" in content or "El número de teléfono móvil ya está registrado" in content:
                                logger.warning("   NÚMERO YA REGISTRADO -> comprando otro")
                                if service_id:
                                    try:
                                        if service_name == 'hero':
                                            await cancel_hero_sms(service_id)
                                        elif service_name == '5sim':
                                            await cancel_fivesim(service_id)
                                    except Exception:
                                        pass
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
                            logger.debug("   🔄 Comprando otro número...")
                            # Salir del bucle interno y del global para recomprar
                            raise Exception("NUMBER_ALREADY_REGISTERED_RECYCLE")
                        else:
                            raise

                    last_screenshot = await take_screenshot(page, "despues_registro")

                    # ----- PASO 15: VERIFICACIÓN POR SMS -----
                    logger.debug("📱 Verificación SMS...")
                    await page.wait_for_timeout(5000)

                    # Manejar WhatsApp
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
                                    except Exception:
                                        pass
                                phone_info = None
                                raise Exception("SMS_UNAVAILABLE_RECYCLE")
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
                                logger.warning("   Código incorrecto o no redirigió. Cancelando número...")
                                if service_id:
                                    try:
                                        if service_name == 'hero':
                                            await cancel_hero_sms(service_id)
                                        elif service_name == '5sim':
                                            await cancel_fivesim(service_id)
                                    except Exception:
                                        pass
                                phone_info = None
                                raise Exception("SMS_CODE_INCORRECT_RECYCLE")
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
                            except Exception:
                                pass
                        phone_info = None
                        raise Exception("SMS_TIMEOUT_RECYCLE")

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

                    # Si es error que requiere comprar otro número (claim, número inválido, etc.)
                    if "NUMBER_ALREADY_REGISTERED_RECYCLE" in error_str or "NUMERO_INVALIDO_RECARGAR" in error_str or "NUMERO_REGISTRADO_RECARGAR" in error_str or "SMS_UNAVAILABLE_RECYCLE" in error_str or "SMS_CODE_INCORRECT_RECYCLE" in error_str or "SMS_TIMEOUT_RECYCLE" in error_str:
                        logger.warning("⚠️ Requiere comprar otro número. Saliendo del bucle interno para recomprar en el global.")
                        raise  # Lo captura el bucle global y recompra

                    # Errores de página (Amazon) - NO cancelar número, solo reiniciar página
                    if "AMAZON_ERROR_PAGE" in error_str or "AMAZON_ERROR_LOSENTIMOS" in error_str or "AMAZON_BLOCKED_ACCOUNT" in error_str:
                        logger.warning("⚠️ Error de página de Amazon. Reiniciando el bucle interno...")
                        # No cancelamos número, solo reiniciamos página
                        await page.close()
                        page = await context.new_page()
                        continue

                    # Errores recuperables (SMS timeout, captcha, etc.) - reiniciar página
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
            set_service_enabled(False)
            SERVICE_BLOCKED_REASON = 'sms_temp'
            SERVICE_BLOCKED_UNTIL = time.time() + 30 * 60
            threading.Timer(30 * 60, lambda: set_service_enabled(True)).start()
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

# ===================================================================
# FUNCIÓN PRINCIPAL generate_cookie_api (punto de entrada)
# ===================================================================
async def generate_cookie_api(country, add_address=True, max_retries=None, max_internal_retries=10, force_playwright=False, service_preference=None):
    logger.debug(f"🚀 generate_cookie_api llamada con country={country}, force_playwright={force_playwright}")
    global SERVICE_BLOCKED_UNTIL, SERVICE_BLOCKED_REASON

    try:
        if country not in base_urls:
            return {'success': False, 'error': f'País no soportado: {country}', 'country': country, 'screenshot': None}

        # ---------- MÉTODO PRINCIPAL: USAR AmazonAccountCreator (la versión que funciona) ----------
        if CAPSOLVER_API_KEY and HERO_SMS_API_KEY and PROXY_STRING:
            logger.debug("🔧 Usando AmazonAccountCreator (método rápido con curl_cffi y capsolver)")

            # Normalizar proxy (si tiene formato user:pass@host:port)
            proxy_str = PROXY_STRING
            # Si el proxy no tiene http://, se lo añadimos (el creador espera el formato sin http)
            if proxy_str and not proxy_str.startswith('http://') and not proxy_str.startswith('https://'):
                proxy_str = proxy_str  # ya viene sin http, lo dejamos así

            # Instanciar el creador (igual que en main.py)
            loop = asyncio.get_running_loop()
            creator = AmazonAccountCreator(
                herosms_api_key=HERO_SMS_API_KEY,
                capsolver_api_key=CAPSOLVER_API_KEY,
                country=country,
                proxy=proxy_str,
                sms_max_price=0.06,  # puedes ajustar desde variable de entorno
                on_status=None  # si quieres ver logs, puedes pasar una función lambda
            )

            # Ejecutar create (bloqueante, lo corremos en un hilo para no bloquear el event loop)
            result = await loop.run_in_executor(None, creator.create, max_retries or 3, not add_address)

            if result.get('status'):
                # Extraer datos igual que en la versión antigua
                profile = result.get('profile', {})
                raw_cookie = result.get('cookies', '')
                # Convertir cookie usando CookieConverter (importado desde amazon)
                cookie = CookieConverter.convert(raw_cookie, country) if raw_cookie else ''

                account_data = {
                    'phone': profile.get('phone', '').replace('+', ''),  # o mantenlo con +
                    'password': profile.get('password', ''),
                    'name': '',  # no tenemos nombre en el perfil de AmazonAccountCreator, pero podemos generarlo
                    'address': 'Dirección agregada' if add_address else 'No se agregó dirección',
                    'cookie_string': raw_cookie,
                    'cookie_dict': dict(x.split('=', 1) for x in raw_cookie.split('; ') if '=' in x),
                    'country': country,
                    'purchase_country': country,
                    'email': profile.get('email', ''),
                }
                return {'success': True, 'data': account_data, 'country': country, 'screenshot': None}
            else:
                error_msg = result.get('message', 'Error desconocido en AmazonAccountCreator')
                # Si el error es de saldo o baneo, propagar excepción para manejarlo
                if 'sms' in error_msg.lower() or 'balance' in error_msg.lower():
                    raise Exception(error_msg)
                return {'success': False, 'error': error_msg, 'country': country, 'screenshot': None}

        else:
            logger.warning("⚠️ Faltan claves CAPSOLVER o HERO_SMS o PROXY_STRING. No se puede usar AmazonAccountCreator.")
            # Si no se puede usar, podrías intentar el fallback a Playwright (si force_playwright es True)
            if force_playwright:
                logger.debug("🔧 force_playwright activado: usando Playwright directamente.")
                account_data, error_msg, screenshot = await create_amazon_account(
                    country,
                    add_address_flag=add_address,
                    max_retries=max_retries,
                    max_internal_retries=max_internal_retries,
                    service_preference=service_preference
                )
                if account_data:
                    return {'success': True, 'data': account_data, 'country': country, 'screenshot': screenshot}
                else:
                    return {'success': False, 'error': error_msg, 'country': country, 'screenshot': screenshot}
            else:
                return {'success': False, 'error': 'No se puede generar cookie: faltan claves o proxy', 'country': country}

    except CAPSolverNoBalance as e:
        logger.error(f"❌ CapSolver sin saldo: {e}")
        set_service_enabled(False)
        return {
            'success': False,
            'error': 'El servicio de resolución de captchas (CapSolver) no tiene saldo. El generador de cookies ha sido desactivado.',
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
        logger.exception(f"💥 Excepción en generate_cookie_api: {e}")
        return {'success': False, 'error': str(e), 'country': country, 'screenshot': None}
# ===================================================================
# API FLASK
# ===================================================================
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
    
    service_preference = data.get('service_preference')  # 'A', 'B', 'C', 'hero', '5sim', etc.
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
        result = loop.run_until_complete(generate_cookie_api(country, add_address, max_retries, max_internal_retries, force_playwright, service_preference))
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

# ===================================================================
# MAIN
# ===================================================================
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