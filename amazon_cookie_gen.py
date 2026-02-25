#!/usr/bin/env python3
"""
Amazon Cookie Generator - Versión completa mejorada
- Mantiene toda la funcionalidad original (~1800 líneas)
- Configuración mediante variables de entorno
- 2captcha con fallback a anticaptcha
- Integración con Hero SMS para verificación telefónica (amazon.com)
- Logging detallado y archivos de depuración
- Soporte para modo interactivo y argumentos CLI
- AHORA: Soporte para API REST (devuelve JSON)
- AHORA: Opción para no agregar dirección
"""

import os
import re
import json
import time
import random
import uuid
import asyncio
import logging
import socket
import argparse
import sys
from urllib.parse import urlencode, urljoin, quote
from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright

# -------------------------------------------------------------------
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO
# -------------------------------------------------------------------
# Captcha
CAPTCHA_PROVIDER = os.getenv('CAPTCHA_PROVIDER', '2captcha')  # '2captcha' o 'anticaptcha'
API_KEY_2CAPTCHA = os.getenv('API_KEY_2CAPTCHA', '')
API_KEY_ANTICAPTCHA = os.getenv('API_KEY_ANTICAPTCHA', '')

# Proxy (formato: usuario:contraseña@host:puerto o host:puerto)
PROXY_STRING = os.getenv('PROXY_STRING', '')
PROXY_AUTH = None
PROXY_HOST_PORT = None
if PROXY_STRING:
    if '@' in PROXY_STRING:
        PROXY_AUTH, PROXY_HOST_PORT = PROXY_STRING.split('@', 1)
    else:
        PROXY_HOST_PORT = PROXY_STRING

# Hero SMS
HERO_SMS_API_KEY = os.getenv('HERO_SMS_API_KEY', '')
HERO_SMS_COUNTRY = os.getenv('HERO_SMS_COUNTRY', 'us')
HERO_SMS_OPERATOR = os.getenv('HERO_SMS_OPERATOR', 'any')

# User-Agents para rotación (igual que original)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'
]

# -------------------------------------------------------------------
# CONFIGURACIÓN FIJA DE DOMINIOS Y URLS (manteniendo original)
# -------------------------------------------------------------------
base_urls = {
    'amazon.ca': 'https://www.amazon.ca',
    'amazon.com.mx': 'https://www.amazon.com.mx',
    'amazon.com': 'https://www.amazon.com',
    'amazon.co.uk': 'https://www.amazon.co.uk',
    'amazon.de': 'https://www.amazon.de',
    'amazon.fr': 'https://www.amazon.fr',
    'amazon.it': 'https://www.amazon.it',
    'amazon.es': 'https://www.amazon.es',
    'amazon.co.jp': 'https://www.amazon.co.jp',
    'amazon.com.au': 'https://www.amazon.com.au',
    'amazon.in': 'https://www.amazon.in'
}

domains = list(base_urls.keys())

# URLs de login (original)
login_urls = {
    'amazon.ca': (
        "https://www.amazon.ca/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.ca%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_ca&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.com.mx': (
        "https://www.amazon.com.mx/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.com.mx%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_mx&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.com': (
        "https://www.amazon.com/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_us&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.co.uk': (
        "https://www.amazon.co.uk/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.co.uk%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_uk&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.de': (
        "https://www.amazon.de/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.de%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_de&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.fr': (
        "https://www.amazon.fr/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.fr%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_fr&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.it': (
        "https://www.amazon.it/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.it%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_it&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.es': (
        "https://www.amazon.es/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.es%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_es&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.co.jp': (
        "https://www.amazon.co.jp/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_jp&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.com.au': (
        "https://www.amazon.com.au/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.com.au%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_au&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    ),
    'amazon.in': (
        "https://www.amazon.in/ap/signin?ie=UTF8&openid.pape.max_auth_age=0&"
        "openid.return_to=https%3A%2F%2Fwww.amazon.in%2F%3F_encoding%3DUTF8%26ref_%3Dnavm_accountmenu_switchacct&"
        "openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.assoc_handle=anywhere_v2_in&_encoding=UTF8&openid.mode=checkid_setup&"
        "openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&"
        "openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&switch_account=signin&"
        "ignoreAuthState=1&disableLoginPrepopulate=1&ref_=ap_sw_aa"
    )
}

address_book_urls = {
    'amazon.ca': "https://www.amazon.ca/a/addresses?ref_=ya_d_c_addr",
    'amazon.com.mx': "https://www.amazon.com.mx/a/addresses?ref_=ya_d_c_addr",
    'amazon.com': "https://www.amazon.com/a/addresses?ref_=ya_d_c_addr",
    'amazon.co.uk': "https://www.amazon.co.uk/a/addresses?ref_=ya_d_c_addr",
    'amazon.de': "https://www.amazon.de/a/addresses?ref_=ya_d_c_addr",
    'amazon.fr': "https://www.amazon.fr/a/addresses?ref_=ya_d_c_addr",
    'amazon.it': "https://www.amazon.it/a/addresses?ref_=ya_d_c_addr",
    'amazon.es': "https://www.amazon.es/a/addresses?ref_=ya_d_c_addr",
    'amazon.co.jp': "https://www.amazon.co.jp/a/addresses?ref_=ya_d_c_addr",
    'amazon.com.au': "https://www.amazon.com.au/a/addresses?ref_=ya_d_c_addr",
    'amazon.in': "https://www.amazon.in/a/addresses?ref_=ya_d_c_addr"
}

add_address_urls = {
    'amazon.ca': "https://www.amazon.ca/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.com.mx': "https://www.amazon.com.mx/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.com': "https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.co.uk': "https://www.amazon.co.uk/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.de': "https://www.amazon.de/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.fr': "https://www.amazon.fr/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.it': "https://www.amazon.it/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.es': "https://www.amazon.es/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.co.jp': "https://www.amazon.co.jp/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.com.au': "https://www.amazon.com.au/a/addresses/add?ref=ya_address_book_add_button",
    'amazon.in': "https://www.amazon.in/a/addresses/add?ref=ya_address_book_add_button"
}

wallet_urls = {
    'amazon.ca': "https://www.amazon.ca/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.com.mx': "https://www.amazon.com.mx/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.com': "https://www.amazon.com/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.co.uk': "https://www.amazon.co.uk/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.de': "https://www.amazon.de/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.fr': "https://www.amazon.fr/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.it': "https://www.amazon.it/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.es': "https://www.amazon.es/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.co.jp': "https://www.amazon.co.jp/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.com.au': "https://www.amazon.com.au/cpe/yourpayments/wallet?ref_=ya_mb_mpo",
    'amazon.in': "https://www.amazon.in/cpe/yourpayments/wallet?ref_=ya_mb_mpo"
}

# URLs de registro (manteniendo original)
register_urls = {
    'amazon.ca': 'https://www.amazon.ca/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_ca&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_ca&openid.return_to=https%3A%2F%2Fwww.amazon.ca%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.com.mx': 'https://www.amazon.com.mx/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_mx&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_mx&openid.return_to=https%3A%2F%2Fwww.amazon.com.mx%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.com': 'https://www.amazon.com/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_us&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_us&openid.return_to=https%3A%2F%2Fwww.amazon.com%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.co.uk': 'https://www.amazon.co.uk/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_uk&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_uk&openid.return_to=https%3A%2F%2Fwww.amazon.co.uk%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.de': 'https://www.amazon.de/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_de&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_de&openid.return_to=https%3A%2F%2Fwww.amazon.de%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.fr': 'https://www.amazon.fr/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_fr&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_fr&openid.return_to=https%3A%2F%2Fwww.amazon.fr%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.it': 'https://www.amazon.it/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_it&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_it&openid.return_to=https%3A%2F%2Fwww.amazon.it%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.es': 'https://www.amazon.es/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_es&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_es&openid.return_to=https%3A%2F%2Fwww.amazon.es%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.co.jp': 'https://www.amazon.co.jp/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_jp&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_jp&openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.com.au': 'https://www.amazon.com.au/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_au&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_au&openid.return_to=https%3A%2F%2Fwww.amazon.com.au%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.in': 'https://www.amazon.in/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_in&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_in&openid.return_to=https%3A%2F%2Fwww.amazon.in%2Fyour-account&policy_handle=Retail-Checkout'
}

# Cookies iniciales (manteniendo original pero generando valores dinámicos)
INITIAL_COOKIES = {}
for domain in domains:
    # Extraer código de país del dominio para personalizar
    if domain == 'amazon.ca':
        code = 'acbca'
        currency = 'CAD'
        lc = 'en_CA'
    elif domain == 'amazon.com.mx':
        code = 'acbmx'
        currency = 'MXN'
        lc = 'es_MX'
    elif domain == 'amazon.com':
        code = 'main'
        currency = 'USD'
        lc = 'en_US'
    elif domain == 'amazon.co.uk':
        code = 'acbuk'
        currency = 'GBP'
        lc = 'en_GB'
    elif domain == 'amazon.de':
        code = 'acbde'
        currency = 'EUR'
        lc = 'de_DE'
    elif domain == 'amazon.fr':
        code = 'acbfr'
        currency = 'EUR'
        lc = 'fr_FR'
    elif domain == 'amazon.it':
        code = 'acbit'
        currency = 'EUR'
        lc = 'it_IT'
    elif domain == 'amazon.es':
        code = 'acbes'
        currency = 'EUR'
        lc = 'es_ES'
    elif domain == 'amazon.co.jp':
        code = 'acbjp'
        currency = 'JPY'
        lc = 'ja_JP'
    elif domain == 'amazon.com.au':
        code = 'acbau'
        currency = 'AUD'
        lc = 'en_AU'
    elif domain == 'amazon.in':
        code = 'acbin'
        currency = 'INR'
        lc = 'en_IN'
    else:
        code = 'unknown'
        currency = 'USD'
        lc = 'en_US'

    INITIAL_COOKIES[domain] = {
        'session-id': f'{random.randint(100,999)}-{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}',
        'i18n-prefs': currency,
        f'lc-{code}': lc,
        f'ubid-{code}': f'{random.randint(100,999)}-{random.randint(1000000,9999999)}-{random.randint(1000000,9999999)}',
        'session-id-time': '2390080760l',
        'session-token': uuid.uuid4().hex.upper(),
        'csm-hit': f'{uuid.uuid4().hex[:12]}|{int(time.time()*1000)}',
        'rxc': uuid.uuid4().hex[:12].upper()
    }

# -------------------------------------------------------------------
# LOGGING
# -------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,  # Nivel DEBUG para máxima información
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amazon_cookie_gen.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# FUNCIONES AUXILIARES (manteniendo originales)
# -------------------------------------------------------------------
def test_proxy(session):
    """Prueba la conectividad del proxy y retorna la IP pública."""
    try:
        response = session.get('https://api.ipify.org?format=json', timeout=15)
        logger.debug(f"**Respuesta de prueba del proxy**: {response.status_code} - {response.text[:500]}")
        if response.status_code != 200:
            logger.error(f"Proxy test failed with status code: {response.status_code}")
            return False, f"Status code {response.status_code}: {response.text[:500]}"
        if 'application/json' not in response.headers.get('Content-Type', ''):
            logger.error(f"Proxy test response is not JSON: {response.text[:500]}")
            return False, f"Non-JSON response: {response.text[:500]}"
        try:
            data = response.json()
            return True, data['ip']
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)} - Response: {response.text[:500]}")
            return False, f"JSON decode error: {str(e)}"
    except requests.exceptions.RequestException as e:
        logger.error(f"Proxy test failed: {str(e)}")
        return False, str(e)

def get_str(string, start, end, occurrence=1):
    """Extrae texto entre dos cadenas (útil para obtener códigos)."""
    try:
        pattern = f'{re.escape(start)}(.*?){re.escape(end)}'
        matches = re.finditer(pattern, string)
        for i, match in enumerate(matches, 1):
            if i == occurrence:
                return match.group(1)
        return None
    except Exception as e:
        logger.debug(f"get_str error: {e}")
        return None

def convert_cookie(cookie_str, output_format='CA'):
    """Convierte cookies según el país (función original)."""
    country_codes = {
        'CA': {'code': 'acbca', 'currency': 'CAD', 'lc': 'lc-acbca', 'lc_value': 'en_CA'},
        'MX': {'code': 'acbmx', 'currency': 'MXN', 'lc': 'lc-acbmx', 'lc_value': 'es_MX'},
        'US': {'code': 'main', 'currency': 'USD', 'lc': 'lc-main', 'lc_value': 'en_US'},
        'UK': {'code': 'acbuk', 'currency': 'GBP', 'lc': 'lc-acbuk', 'lc_value': 'en_GB'},
        'DE': {'code': 'acbde', 'currency': 'EUR', 'lc': 'lc-acbde', 'lc_value': 'de_DE'},
        'FR': {'code': 'acbfr', 'currency': 'EUR', 'lc': 'lc-acbfr', 'lc_value': 'fr_FR'},
        'IT': {'code': 'acbit', 'currency': 'EUR', 'lc': 'lc-acbit', 'lc_value': 'it_IT'},
        'ES': {'code': 'acbes', 'currency': 'EUR', 'lc': 'lc-acbes', 'lc_value': 'es_ES'},
        'JP': {'code': 'acbjp', 'currency': 'JPY', 'lc': 'lc-acbjp', 'lc_value': 'ja_JP'},
        'AU': {'code': 'acbau', 'currency': 'AUD', 'lc': 'lc-acbau', 'lc_value': 'en_AU'},
        'IN': {'code': 'acbin', 'currency': 'INR', 'lc': 'lc-acbin', 'lc_value': 'en_IN'}
    }
    if output_format not in country_codes:
        return cookie_str
    country = country_codes[output_format]
    cookie_str = re.sub(r'acbes|acbmx|acbit|main|acbca|acbde|acbuk|acbau|acbjp|acbfr|acbin', country['code'], cookie_str)
    cookie_str = re.sub(r'(i18n-prefs=)[A-Z]{3}', r'\1' + country['currency'], cookie_str)
    cookie_str = re.sub(rf'({country["lc"]}=)[a-z]{{2}}_[A-Z]{{2}}', r'\1' + country['lc_value'], cookie_str)
    return cookie_str

# -------------------------------------------------------------------
# CAPTCHA RESOLUTION (2captcha + fallback anticaptcha)
# -------------------------------------------------------------------
def solve_captcha(site_key, page_url, is_image_captcha=False, image_path=None):
    """
    Resuelve captcha usando primero 2captcha (si está configurado) y luego anticaptcha como fallback.
    Retorna el código de solución o None si falla.
    """
    solution = None

    # Intentar con 2captcha
    if API_KEY_2CAPTCHA and (CAPTCHA_PROVIDER == '2captcha' or not solution):
        try:
            from twocaptcha import TwoCaptcha
            solver = TwoCaptcha(API_KEY_2CAPTCHA)
            if is_image_captcha and image_path:
                logger.info("Enviando captcha de imagen a 2captcha...")
                result = solver.normal(image_path)
                solution = result['code']
            else:
                logger.info(f"Enviando reCAPTCHA v2 a 2captcha (sitekey: {site_key})...")
                result = solver.recaptcha(sitekey=site_key, url=page_url)
                solution = result['code']
            logger.info(f"2captcha resuelto exitosamente: {solution[:20]}...")
        except Exception as e:
            logger.warning(f"2captcha falló: {e}. Intentando con anticaptcha...")
            solution = None

    # Fallback a anticaptcha
    if not solution and API_KEY_ANTICAPTCHA:
        try:
            from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
            from anticaptchaofficial.imagecaptcha import imagecaptcha
            if is_image_captcha and image_path:
                logger.info("Enviando captcha de imagen a anticaptcha...")
                solver = imagecaptcha()
                solver.set_api_key(API_KEY_ANTICAPTCHA)
                solver.set_verbose(1)
                solution = solver.solve_and_return_solution(image_path)
            else:
                logger.info(f"Enviando reCAPTCHA v2 a anticaptcha (sitekey: {site_key})...")
                solver = recaptchaV2Proxyless()
                solver.set_api_key(API_KEY_ANTICAPTCHA)
                solver.set_website_url(page_url)
                solver.set_website_key(site_key)
                solver.set_verbose(1)
                solution = solver.solve_and_return_solution()
            if solution:
                logger.info(f"anticaptcha resuelto exitosamente: {solution[:20]}...")
            else:
                logger.error("anticaptcha no pudo resolver el captcha")
        except Exception as e:
            logger.error(f"anticaptcha también falló: {e}")
            solution = None

    return solution

# -------------------------------------------------------------------
# HERO SMS (servicio de números virtuales)
# -------------------------------------------------------------------
async def get_hero_sms_number():
    """Solicita un número de teléfono temporal a Hero SMS para el servicio Amazon."""
    if not HERO_SMS_API_KEY:
        logger.error("HERO_SMS_API_KEY no configurada")
        return None
    url = "https://hero-sms.com/api/v1/numbers/rent"
    headers = {"Authorization": f"Bearer {HERO_SMS_API_KEY}"}
    payload = {
        "country": HERO_SMS_COUNTRY,
        "operator": HERO_SMS_OPERATOR,
        "service": "amazon"
    }
    try:
        logger.debug(f"Solicitando número a Hero SMS con payload: {payload}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        logger.debug(f"Respuesta de Hero SMS: {response.status_code} - {response.text[:200]}")
        if response.status_code == 200:
            data = response.json()
            phone = data.get('phone_number')
            request_id = data.get('request_id')
            if phone and request_id:
                logger.info(f"Número Hero SMS obtenido: {phone} (request_id: {request_id})")
                return phone, request_id
            else:
                logger.error(f"Respuesta incompleta de Hero SMS: {data}")
                return None
        else:
            logger.error(f"Error obteniendo número: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Excepción en get_hero_sms_number: {e}")
        return None

async def get_hero_sms_code(request_id, timeout=120):
    """Espera y obtiene el código SMS de Hero SMS."""
    url = f"https://hero-sms.com/api/v1/numbers/wait/{request_id}"
    headers = {"Authorization": f"Bearer {HERO_SMS_API_KEY}"}
    start_time = time.time()
    logger.info(f"Esperando código SMS (request_id: {request_id})...")
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            logger.debug(f"Respuesta de wait: {response.status_code} - {response.text[:200]}")
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'received':
                    message = data.get('message', '')
                    # Buscar código de 5-6 dígitos en el mensaje
                    code_match = re.search(r'\b(\d{5,6})\b', message)
                    if code_match:
                        code = code_match.group(1)
                        logger.info(f"Código SMS recibido: {code}")
                        return code
                    else:
                        logger.warning(f"Mensaje recibido pero no se encontró código: {message}")
                else:
                    logger.debug(f"Estado actual: {data.get('status')}")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error obteniendo código SMS: {e}")
            await asyncio.sleep(5)
    logger.error(f"Timeout después de {timeout} segundos esperando código SMS")
    return None

# -------------------------------------------------------------------
# CORREO TEMPORAL (mail.tm, guerrillamail, tempmail.plus)
# -------------------------------------------------------------------
async def generate_temp_email():
    """Genera una dirección de correo temporal usando múltiples servicios."""
    services = [
        ('mail.tm', 'https://api.mail.tm'),
        ('guerrillamail', 'https://api.guerrillamail.com'),
        ('tempmail.plus', 'https://api.tempmail.plus')
    ]
    for service_name, api_url in services:
        logger.debug(f"Intentando generar correo con {service_name}...")
        try:
            if service_name == 'mail.tm':
                # Obtener dominios disponibles
                resp = requests.get(f"{api_url}/domains", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    domains_list = data.get('hydra:member', [])
                    if domains_list and domains_list[0].get('domain'):
                        domain = domains_list[0]['domain']
                        email = f"{uuid.uuid4().hex[:8]}@{domain}"
                        password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
                        # Crear cuenta
                        acc_resp = requests.post(
                            f"{api_url}/accounts",
                            json={"address": email, "password": password},
                            timeout=10
                        )
                        if acc_resp.status_code == 201:
                            token = acc_resp.json().get('token')
                            logger.info(f"Correo mail.tm generado: {email}")
                            return email, token, service_name
            elif service_name == 'guerrillamail':
                resp = requests.get(f"{api_url}/ajax.php?f=get_email_address&ip=127.0.0.1", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    email = data.get('email_addr')
                    token = data.get('sid_token')
                    if email and token:
                        logger.info(f"Correo guerrillamail generado: {email}")
                        return email, token, service_name
            elif service_name == 'tempmail.plus':
                resp = requests.get(f"{api_url}/generate", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    email = data.get('email')
                    token = data.get('token')
                    if email and token:
                        logger.info(f"Correo tempmail.plus generado: {email}")
                        return email, token, service_name
        except Exception as e:
            logger.warning(f"Error con {service_name}: {e}")
            continue
    logger.error("No se pudo generar correo temporal con ningún servicio")
    return None, None, None

async def get_verification_code(email, token, service, max_attempts=15, wait_time=8):
    """
    Obtiene el código de verificación del correo temporal.
    Espera hasta max_attempts ciclos de wait_time segundos.
    """
    logger.info(f"Esperando código de verificación para {email} (servicio: {service})...")
    for attempt in range(max_attempts):
        try:
            if service == 'mail.tm' and token:
                resp = requests.get(
                    "https://api.mail.tm/messages",
                    headers={'Authorization': f'Bearer {token}'},
                    timeout=10
                )
                if resp.status_code == 200:
                    emails = resp.json().get('hydra:member', [])
                    for mail in emails:
                        # Intentar extraer código del texto del mensaje
                        text = mail.get('text', '') or mail.get('html', '') or mail.get('intro', '')
                        code = get_str(text, 'Your verification code is ', '\n')
                        if code:
                            logger.info(f"Código de verificación encontrado: {code}")
                            return code
            elif service == 'guerrillamail' and token:
                resp = requests.get(
                    f"https://api.guerrillamail.com/ajax.php?f=check_email&seq=0&sid_token={token}",
                    timeout=10
                )
                if resp.status_code == 200:
                    emails = resp.json().get('list', [])
                    for mail in emails:
                        body = mail.get('mail_body', '') or mail.get('mail_body_ex', '')
                        code = get_str(body, 'Your verification code is ', '\n')
                        if code:
                            logger.info(f"Código de verificación encontrado: {code}")
                            return code
            elif service == 'tempmail.plus' and token:
                resp = requests.get(f"https://api.tempmail.plus/messages/{token}", timeout=10)
                if resp.status_code == 200:
                    emails = resp.json().get('messages', [])
                    for mail in emails:
                        text = mail.get('text', '') or mail.get('html', '')
                        code = get_str(text, 'Your verification code is ', '\n')
                        if code:
                            logger.info(f"Código de verificación encontrado: {code}")
                            return code
        except Exception as e:
            logger.debug(f"Error en intento {attempt+1} obteniendo código: {e}")
        await asyncio.sleep(wait_time)
    logger.error("No se recibió código de verificación después de varios intentos")
    return None

# -------------------------------------------------------------------
# RE-AUTENTICACIÓN (login_again)
# -------------------------------------------------------------------
async def login_again(session, domain, email, password, token=None, service=None, max_attempts=3):
    """Vuelve a iniciar sesión en la cuenta si la sesión expiró."""
    for attempt in range(max_attempts):
        logger.info(f"Re-autenticación intento {attempt+1}/{max_attempts} para {email} en {domain}")
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        # Establecer cookies iniciales
        session.cookies.clear()
        for key, value in INITIAL_COOKIES[domain].items():
            session.cookies.set(key, value, domain=f".{domain}")

        # Obtener página de login
        resp = session.get(login_urls[domain], headers=headers, timeout=15, allow_redirects=True)
        logger.debug(f"Página de login respuesta: {resp.status_code} - {resp.url}")
        with open(f'login_page_{email}_{domain}_attempt_{attempt+1}.html', 'w', encoding='utf-8') as f:
            f.write(resp.text)

        if resp.status_code != 200:
            logger.error(f"Error al obtener página de login: {resp.status_code}")
            await asyncio.sleep(2 ** attempt)
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Detectar captcha en la página de login
        captcha_div = soup.find('div', {'id': 'captchacharacters'})
        recaptcha_div = soup.find('div', {'class': re.compile('g-recaptcha')})
        if 'captcha' in resp.text.lower() or captcha_div or recaptcha_div:
            logger.info("CAPTCHA detectado en página de login")
            if recaptcha_div:
                site_key = recaptcha_div.get('data-sitekey')
                if site_key:
                    captcha_solution = solve_captcha(site_key, login_urls[domain])
                    if not captcha_solution:
                        logger.error("No se pudo resolver reCAPTCHA en login")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    # Enviar solución
                    post_resp = session.post(
                        login_urls[domain],
                        data={'g-recaptcha-response': captcha_solution},
                        headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                        timeout=15,
                        allow_redirects=True
                    )
                    soup = BeautifulSoup(post_resp.text, 'html.parser')
                    logger.debug(f"Respuesta tras resolver reCAPTCHA: {post_resp.status_code}")
            elif captcha_div:
                img = captcha_div.find('img')
                if img and img.get('src'):
                    img_url = urljoin(login_urls[domain], img['src'])
                    img_resp = session.get(img_url, timeout=10)
                    if img_resp.status_code == 200:
                        with open('temp_captcha.jpg', 'wb') as f:
                            f.write(img_resp.content)
                        solution = solve_captcha(None, login_urls[domain], is_image_captcha=True, image_path='temp_captcha.jpg')
                        if solution:
                            post_resp = session.post(
                                login_urls[domain],
                                data={'cvf_captcha_input': solution},
                                headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                                timeout=15,
                                allow_redirects=True
                            )
                            soup = BeautifulSoup(post_resp.text, 'html.parser')
                            logger.debug(f"Respuesta tras resolver imagen captcha: {post_resp.status_code}")
            # Recargar soup con la respuesta después del captcha (si se resolvió)

        # Buscar formulario de login
        form = (soup.find('form', {'id': re.compile('ap_signin_form|signin|login', re.I)}) or
                soup.find('form', {'action': re.compile('signin|sign-in|login', re.I)}) or
                soup.find('form', {'method': 'post'}))
        if not form:
            logger.error("No se encontró formulario de login")
            await asyncio.sleep(2 ** attempt)
            continue

        # Extraer campos ocultos
        payload = {}
        for inp in form.find_all('input', type='hidden'):
            if inp.get('name'):
                payload[inp['name']] = inp.get('value', '')
        payload.update({
            'email': email,
            'password': password,
            'rememberMe': 'true'
        })

        action = urljoin(base_urls[domain], form.get('action') or login_urls[domain])
        login_resp = session.post(
            action,
            data=urlencode(payload),
            headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=15,
            allow_redirects=True
        )
        logger.debug(f"Respuesta de login: {login_resp.status_code} - {login_resp.url}")
        with open(f'login_response_{email}_{domain}_attempt_{attempt+1}.html', 'w', encoding='utf-8') as f:
            f.write(login_resp.text)

        soup = BeautifulSoup(login_resp.text, 'html.parser')

        # Verificar si pide verificación en dos pasos
        if 'cvf' in login_resp.url.lower() or 'verification' in login_resp.text.lower():
            logger.info("Verificación en dos pasos detectada")
            verification_code = await get_verification_code(email, token, service)
            if not verification_code:
                logger.error("No se pudo obtener código de verificación")
                await asyncio.sleep(2 ** attempt)
                continue

            cvf_form = (soup.find('form', {'id': 'cvf_form'}) or
                        soup.find('form', {'action': re.compile('cvf|verify', re.I)}) or
                        soup.find('form', {'method': 'post'}))
            if not cvf_form:
                logger.error("No se encontró formulario de verificación")
                await asyncio.sleep(2 ** attempt)
                continue

            cvf_payload = {}
            for inp in cvf_form.find_all('input', type='hidden'):
                if inp.get('name'):
                    cvf_payload[inp['name']] = inp.get('value', '')
            cvf_payload.update({
                'code': verification_code,
                'appAction': 'VERIFY',
                'appActionToken': get_str(login_resp.text, 'name="appActionToken" value="', '"') or '',
                'workflowState': get_str(login_resp.text, 'name="workflowState" value="', '"') or ''
            })

            cvf_action = urljoin(base_urls[domain], cvf_form.get('action') or login_resp.url)
            cvf_resp = session.post(
                cvf_action,
                data=urlencode(cvf_payload),
                headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15,
                allow_redirects=True
            )
            logger.debug(f"Respuesta de verificación: {cvf_resp.status_code} - {cvf_resp.url}")
            with open(f'login_verification_response_{email}_{domain}_attempt_{attempt+1}.html', 'w', encoding='utf-8') as f:
                f.write(cvf_resp.text)
            soup = BeautifulSoup(cvf_resp.text, 'html.parser')

        # Verificar si el login fue exitoso
        if login_resp.status_code == 200 and 'signin' not in login_resp.url.lower() and 'authentication' not in login_resp.text.lower():
            logger.info(f"Re-autenticación exitosa para {email}")
            cookies = session.cookies.get_dict()
            cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
            logger.debug(f"Cookies tras re-autenticación: {cookie_str}")
            return True

        error_div = soup.find('div', {'class': re.compile('a-alert-error|a-alert-warning|a-box-error', re.I)})
        if error_div:
            error_msg = error_div.get_text(strip=True)
            logger.error(f"Error en re-login: {error_msg}")
        await asyncio.sleep(2 ** attempt)
    logger.error(f"Re-autenticación fallida después de {max_attempts} intentos")
    return False

# -------------------------------------------------------------------
# AGREGAR DIRECCIÓN (add_address)
# -------------------------------------------------------------------
async def add_address(session, domain, email, password, token=None, service=None):
    """Agrega una dirección por defecto a la cuenta."""
    logger.info(f"Agregando dirección para {email} en {domain}")
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{base_urls[domain]}/gp/your-account?ref_=nav_AccountFlyout_ya",
        "Viewport-Width": "1536"
    }

    # Asegurar cookies iniciales
    for key, value in INITIAL_COOKIES[domain].items():
        session.cookies.set(key, value, domain=f".{domain}")

    # Acceder a libreta de direcciones
    resp = session.get(address_book_urls[domain], headers=headers, timeout=15, allow_redirects=True)
    logger.debug(f"Página de libreta de direcciones: {resp.status_code} - {resp.url}")
    with open(f'address_book_page_{email}_{domain}.html', 'w', encoding='utf-8') as f:
        f.write(resp.text)

    if resp.status_code != 200:
        logger.error(f"Error al acceder a libreta de direcciones: {resp.status_code}")
        return None

    # Si redirige a login, re-autenticar
    if 'signin' in resp.url.lower() or 'authentication' in resp.text.lower():
        logger.info("Se requiere autenticación adicional, intentando re-login...")
        if not await login_again(session, domain, email, password, token, service):
            logger.error("Re-autenticación fallida")
            return None
        resp = session.get(address_book_urls[domain], headers=headers, timeout=15, allow_redirects=True)
        logger.debug(f"Página tras re-login: {resp.status_code} - {resp.url}")
        with open(f'address_book_page_{email}_{domain}_relogin.html', 'w', encoding='utf-8') as f:
            f.write(resp.text)
        if resp.status_code != 200:
            logger.error("No se pudo acceder a libreta tras re-login")
            return None

    # Ir a añadir dirección
    resp = session.get(add_address_urls[domain], headers=headers, timeout=15, allow_redirects=True)
    logger.debug(f"Página de añadir dirección: {resp.status_code} - {resp.url}")
    with open(f'address_page_{email}_{domain}.html', 'w', encoding='utf-8') as f:
        f.write(resp.text)

    if resp.status_code != 200:
        logger.error(f"Error al acceder a página de añadir dirección: {resp.status_code}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Detectar captcha
    captcha_div = soup.find('div', {'id': 'captchacharacters'})
    recaptcha_div = soup.find('div', {'class': re.compile('g-recaptcha')})
    if 'captcha' in resp.text.lower() or captcha_div or recaptcha_div:
        logger.info("CAPTCHA detectado en página de dirección")
        if recaptcha_div:
            site_key = recaptcha_div.get('data-sitekey')
            if site_key:
                captcha_solution = solve_captcha(site_key, add_address_urls[domain])
                if captcha_solution:
                    # Enviar solución
                    session.post(
                        add_address_urls[domain],
                        data={'g-recaptcha-response': captcha_solution},
                        headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                        timeout=15,
                        allow_redirects=True
                    )
        elif captcha_div:
            img = captcha_div.find('img')
            if img and img.get('src'):
                img_url = urljoin(add_address_urls[domain], img['src'])
                img_resp = session.get(img_url, timeout=10)
                if img_resp.status_code == 200:
                    with open('temp_captcha.jpg', 'wb') as f:
                        f.write(img_resp.content)
                    solution = solve_captcha(None, add_address_urls[domain], is_image_captcha=True, image_path='temp_captcha.jpg')
                    if solution:
                        session.post(
                            add_address_urls[domain],
                            data={'cvf_captcha_input': solution},
                            headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                            timeout=15,
                            allow_redirects=True
                        )
        # Recargar página después de resolver captcha
        resp = session.get(add_address_urls[domain], headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

    # Buscar formulario de dirección
    form = soup.find('form', {'id': 'address-ui-widgets-form'}) or soup.find('form', {'action': re.compile('add', re.I)})
    if not form:
        logger.error("No se encontró formulario de dirección")
        return None

    # Datos de dirección por país (original)
    address_data = {
        'amazon.ca': {
            'countryCode': 'CA',
            'fullName': 'Mark O. Montanez',
            'phone': f'1{random.randint(1000000000, 9999999999)}',
            'line1': '456 Bloor Street West',
            'city': 'Toronto',
            'state': 'ON',
            'postalCode': 'M5S 1X8'
        },
        'amazon.com.mx': {
            'countryCode': 'MX',
            'fullName': 'Juan Pérez',
            'phone': f'52{random.randint(1000000000, 9999999999)}',
            'line1': 'Calle Reforma 123',
            'city': 'Ciudad de México',
            'state': 'CDMX',
            'postalCode': '06000'
        },
        'amazon.com': {
            'countryCode': 'US',
            'fullName': 'John Doe',
            'phone': f'1{random.randint(1000000000, 9999999999)}',
            'line1': '123 Main Street',
            'city': 'New York',
            'state': 'NY',
            'postalCode': '10001'
        },
        'amazon.co.uk': {
            'countryCode': 'GB',
            'fullName': 'James Smith',
            'phone': f'44{random.randint(1000000000, 9999999999)}',
            'line1': '123 Oxford Street',
            'city': 'London',
            'state': '',
            'postalCode': 'W1D 1AA'
        },
        'amazon.de': {
            'countryCode': 'DE',
            'fullName': 'Hans Müller',
            'phone': f'49{random.randint(1000000000, 9999999999)}',
            'line1': 'Hauptstraße 12',
            'city': 'Berlin',
            'state': '',
            'postalCode': '10115'
        },
        'amazon.fr': {
            'countryCode': 'FR',
            'fullName': 'Pierre Dubois',
            'phone': f'33{random.randint(1000000000, 9999999999)}',
            'line1': '12 Rue de Rivoli',
            'city': 'Paris',
            'state': '',
            'postalCode': '75001'
        },
        'amazon.it': {
            'countryCode': 'IT',
            'fullName': 'Giuseppe Rossi',
            'phone': f'39{random.randint(1000000000, 9999999999)}',
            'line1': 'Via Roma 10',
            'city': 'Roma',
            'state': '',
            'postalCode': '00184'
        },
        'amazon.es': {
            'countryCode': 'ES',
            'fullName': 'Carlos García',
            'phone': f'34{random.randint(1000000000, 9999999999)}',
            'line1': 'Calle Mayor 15',
            'city': 'Madrid',
            'state': '',
            'postalCode': '28013'
        },
        'amazon.co.jp': {
            'countryCode': 'JP',
            'fullName': 'Taro Yamada',
            'phone': f'81{random.randint(1000000000, 9999999999)}',
            'line1': '1-2-3 Shibuya',
            'city': 'Tokyo',
            'state': '',
            'postalCode': '150-0002'
        },
        'amazon.com.au': {
            'countryCode': 'AU',
            'fullName': 'Emma Wilson',
            'phone': f'61{random.randint(1000000000, 9999999999)}',
            'line1': '123 George Street',
            'city': 'Sydney',
            'state': 'NSW',
            'postalCode': '2000'
        },
        'amazon.in': {
            'countryCode': 'IN',
            'fullName': 'Amit Sharma',
            'phone': f'91{random.randint(1000000000, 9999999999)}',
            'line1': '123 MG Road',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'postalCode': '400001'
        }
    }

    country_data = address_data[domain]

    # Extraer campos ocultos
    post_data = {}
    for inp in form.find_all('input', type='hidden'):
        if inp.get('name'):
            post_data[inp['name']] = inp.get('value', '')

    # Agregar datos del formulario (original)
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
        "address-ui-widgets-delivery-instructions-desktop-expander-context": '{"deliveryInstructionsDisplayMode" : "CDP_ONLY", "deliveryInstructionsClientName" : "YourAccountAddressBook", "deliveryInstructionsDeviceType" : "desktop", "deliveryInstructionsIsEditAddressFlow" : "false"}',
        "address-ui-widgets-addressFormButtonText": "save",
        "address-ui-widgets-addressFormHideHeading": "true",
        "address-ui-widgets-enableAddressDetails": "true",
        "address-ui-widgets-returnLegacyAddressID": "false",
        "address-ui-widgets-enableDeliveryInstructions": "true",
        "address-ui-widgets-enableAddressWizardInlineSuggestions": "false",
        "address-ui-widgets-enableEmailAddress": "false",
        "address-ui-widgets-enableAddressTips": "true",
        "address-ui-widgets-clientName": "YourAccountAddressBook",
        "address-ui-widgets-enableAddressWizardForm": "true",
        "address-ui-widgets-delivery-instructions-data": f'{{"initialCountryCode":"{country_data["countryCode"]}"}}',
        "address-ui-widgets-enableLatestAddressWizardForm": "true",
        "address-ui-widgets-avsSuppressSoftblock": "false",
        "address-ui-widgets-avsSuppressSuggestion": "false"
    })

    post_url = urljoin(base_urls[domain], form.get('action') or "/a/addresses/add")
    headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": base_urls[domain],
        "Referer": add_address_urls[domain]
    })

    # Enviar dirección
    resp = session.post(
        post_url,
        data=urlencode(post_data),
        headers=headers,
        timeout=15,
        allow_redirects=True
    )
    logger.debug(f"Respuesta envío de dirección: {resp.status_code} - {resp.url}")
    with open(f'address_response_{email}_{domain}.html', 'w', encoding='utf-8') as f:
        f.write(resp.text)

    soup = BeautifulSoup(resp.text, 'html.parser')
    error_div = soup.find('div', {'class': re.compile('a-alert-error|a-alert-warning|a-box-error', re.I)})
    if error_div:
        error_msg = error_div.get_text(strip=True)
        logger.error(f"Error al enviar dirección: {error_msg}")
        return None

    if resp.status_code != 200 or 'address' in resp.url.lower():
        logger.error(f"Fallo al enviar dirección: status {resp.status_code}, url {resp.url}")
        return None

    # Verificar que la dirección se haya agregado
    resp = session.get(address_book_urls[domain], headers=headers, timeout=15, allow_redirects=True)
    logger.debug(f"Verificación de libreta: {resp.status_code}")
    soup = BeautifulSoup(resp.text, 'html.parser')
    address_div = soup.find('div', string=re.compile(country_data['line1'], re.I))
    if not address_div:
        logger.error("No se encontró la dirección en la libreta")
        return None

    logger.info("Dirección agregada exitosamente")
    return True

# -------------------------------------------------------------------
# CREACIÓN DE CUENTA PRINCIPAL (create_amazon_account) - MODIFICADA
# -------------------------------------------------------------------
async def create_amazon_account(domain, email=None, token=None, service=None, add_address_flag=True):
    """
    Crea una cuenta de Amazon y retorna las cookies finales.
    Parámetros:
        domain: dominio de Amazon (ej. amazon.com)
        email: correo opcional (si no se proporciona, se genera uno)
        token: token del servicio de correo
        service: servicio de correo utilizado
        add_address_flag: True para agregar dirección, False para omitir
    """
    playwright = None
    browser = None
    context = None
    page = None
    session = None

    # Diccionario para almacenar los datos de la cuenta generada
    account_data = {
        'email': None,
        'password': None,
        'name': None,
        'phone': None,
        'address': None,
        'cookie_string': None,
        'cookie_dict': None,
        'country': domain.split('.')[-1].upper() if '.' in domain else domain,
        'timestamp': time.time()
    }

    try:
        # Preparar sesión requests con proxy
        session = requests.Session()
        if PROXY_HOST_PORT:
            proxy_url = f"http://{PROXY_HOST_PORT}"
            if PROXY_AUTH:
                proxy_url = f"http://{PROXY_AUTH}@{PROXY_HOST_PORT}"
            session.proxies = {'http': proxy_url, 'https': proxy_url}
            logger.info(f"Proxy configurado: {PROXY_HOST_PORT}")
        else:
            logger.warning("No se configuró proxy, se usará IP directa")

        # Probar proxy
        ok, msg = test_proxy(session)
        if not ok:
            logger.error(f"Proxy no funciona: {msg}")
            return None

        # Generar credenciales si no se proporcionan
        if not email:
            email, token, service = await generate_temp_email()
            if not email:
                return None
        
        password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
        first_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
        last_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
        fullname = f"{first_name} {last_name}"
        
        account_data['email'] = email
        account_data['password'] = password
        account_data['name'] = fullname

        # Iniciar Playwright con proxy
        playwright = await async_playwright().start()
        launch_options = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        }
        if PROXY_HOST_PORT:
            proxy_dict = {'server': f'http://{PROXY_HOST_PORT}'}
            if PROXY_AUTH:
                user, pwd = PROXY_AUTH.split(':', 1)
                proxy_dict['username'] = user
                proxy_dict['password'] = pwd
            launch_options['proxy'] = proxy_dict
            logger.debug(f"Playwright proxy configurado: {proxy_dict}")

        browser = await playwright.chromium.launch(**launch_options)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=random.choice(USER_AGENTS)
        )
        page = await context.new_page()

        print(f"📧 Creando cuenta: {email}")
        print(f"🌐 Navegando a {domain}...")
        await page.goto(register_urls[domain], wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)

        # Guardar HTML de la página de registro para depuración
        content = await page.content()
        with open(f'register_page_{email}_{domain}.html', 'w', encoding='utf-8') as f:
            f.write(content)

        # --- LLENAR FORMULARIO DE REGISTRO ---
        # Nombre completo
        try:
            await page.wait_for_selector('input[name="customerName"]', timeout=5000)
            await page.fill('input[name="customerName"]', fullname)
            logger.debug("Nombre completo llenado")
        except Exception as e:
            logger.warning(f"No se pudo llenar nombre con selector principal: {e}")
            try:
                await page.fill('input[placeholder*="name" i]', fullname)
            except:
                pass

        # Email
        try:
            await page.fill('input[name="email"]', email)
            logger.debug("Email llenado")
        except:
            try:
                await page.fill('input[type="email"]', email)
            except Exception as e:
                logger.error(f"No se pudo llenar email: {e}")
                return None

        # Contraseña
        try:
            await page.fill('input[name="password"]', password)
            logger.debug("Contraseña llenada")
        except:
            try:
                await page.fill('input[type="password"]', password)
            except Exception as e:
                logger.error(f"No se pudo llenar contraseña: {e}")
                return None

        # Confirmar contraseña (si existe)
        try:
            await page.wait_for_selector('input[name="passwordCheck"]', timeout=2000)
            await page.fill('input[name="passwordCheck"]', password)
            logger.debug("Confirmación de contraseña llenada")
        except:
            pass

        # Teléfono (solo amazon.com)
        request_id = None
        if domain == 'amazon.com':
            phone_number = None
            if HERO_SMS_API_KEY:
                phone_info = await get_hero_sms_number()
                if phone_info:
                    phone_number, request_id = phone_info
                else:
                    phone_number = f"+1{random.randint(200,999)}{random.randint(1000000,9999999)}"
                    logger.warning("No se pudo obtener número real, usando número falso")
            else:
                phone_number = f"+1{random.randint(200,999)}{random.randint(1000000,9999999)}"
                logger.warning("HERO_SMS_API_KEY no configurada, usando número falso")

            try:
                await page.wait_for_selector('input[name="phoneNumber"]', timeout=5000)
                await page.fill('input[name="phoneNumber"]', phone_number)
                logger.debug(f"Número de teléfono llenado: {phone_number}")
                account_data['phone'] = phone_number
            except:
                try:
                    await page.fill('input[type="tel"]', phone_number)
                    account_data['phone'] = phone_number
                except Exception as e:
                    logger.error(f"No se pudo llenar teléfono: {e}")
                    return None

        # Aceptar términos (si existe)
        try:
            await page.check('input[name="agreement"]', timeout=2000)
            logger.debug("Checkbox de términos marcado")
        except:
            try:
                await page.check('input[type="checkbox"]', timeout=2000)
                logger.debug("Checkbox genérico marcado")
            except:
                pass

        # Hacer clic en botón de registro
        try:
            await page.click('input[type="submit"], button[type="submit"], #continue')
            logger.debug("Botón de registro clickeado")
        except Exception as e:
            logger.error(f"No se pudo hacer clic en botón de registro: {e}")
            return None

        # Esperar a que se procese
        await page.wait_for_load_state('networkidle', timeout=30000)

        # Obtener URL actual y contenido
        current_url = page.url
        content = await page.content()
        with open(f'register_response_{email}_{domain}.html', 'w', encoding='utf-8') as f:
            f.write(content)

        soup = BeautifulSoup(content, 'html.parser')

        # Verificar errores
        error_div = soup.find('div', {'class': re.compile('a-alert-error|a-alert-warning|a-box-error', re.I)})
        if error_div:
            error_msg = error_div.get_text(strip=True)
            logger.error(f"Error en registro: {error_msg}")
            print(f"❌ Error: {error_msg}")
            return None

        # Verificar si pide verificación (correo o SMS)
        if 'verification' in current_url.lower() or 'cvf' in current_url.lower():
            if domain == 'amazon.com' and request_id:
                print("📱 Esperando código SMS...")
                code = await get_hero_sms_code(request_id)
                if code:
                    try:
                        await page.fill('input[name="code"]', code)
                        await page.click('button[type="submit"]')
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        logger.info("Código SMS enviado")
                    except Exception as e:
                        logger.error(f"Error al enviar código SMS: {e}")
                        return None
                else:
                    print("❌ No se recibió código SMS")
                    return None
            else:
                print("📧 Esperando código de verificación...")
                code = await get_verification_code(email, token, service)
                if code:
                    try:
                        await page.fill('input[name="code"]', code)
                        await page.click('button[type="submit"]')
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        logger.info("Código de correo enviado")
                    except Exception as e:
                        logger.error(f"Error al enviar código de correo: {e}")
                        return None
                else:
                    print("❌ No se recibió código de correo")
                    return None

        # Verificar si el registro fue exitoso (redirigido a your-account)
        if 'your-account' in page.url.lower() or 'account' in page.url.lower():
            print(f"✅ Cuenta creada exitosamente: {email}")
            print(f"🔑 Contraseña: {password}")

            # Obtener cookies del navegador
            cookies = await context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
            
            account_data['cookie_dict'] = cookie_dict
            account_data['cookie_string'] = cookie_string

            # Sincronizar cookies con la sesión requests para agregar dirección
            for name, value in cookie_dict.items():
                session.cookies.set(name, value, domain=f".{domain}")

            # Agregar dirección SOLO si el usuario lo solicita
            if add_address_flag:
                print("📍 Agregando dirección...")
                addr_ok = await add_address(session, domain, email, password, token, service)
                if addr_ok:
                    print("✅ Dirección agregada")
                    account_data['address'] = "Dirección agregada exitosamente"
                else:
                    print("⚠️ No se pudo agregar dirección")
                    account_data['address'] = "Error al agregar dirección"
            else:
                print("📍 Omisión de dirección solicitada por el usuario")
                account_data['address'] = "No se agregó dirección (opción desactivada)"

            # Navegar a la página de wallet para obtener cookies completas
            try:
                await page.goto(wallet_urls[domain], wait_until='networkidle', timeout=20000)
                await page.wait_for_timeout(3000)
                cookies = await context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                account_data['cookie_dict'] = cookie_dict
                account_data['cookie_string'] = cookie_string
                logger.debug("Cookies actualizadas tras visitar wallet")
            except Exception as e:
                logger.warning(f"Error al visitar wallet: {e}")

            return account_data
        else:
            print(f"❌ Registro fallido, URL final: {page.url}")
            return None

    except Exception as e:
        logger.exception("Error en create_amazon_account")
        print(f"❌ Excepción: {e}")
        return None
    finally:
        if page:
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

# -------------------------------------------------------------------
# FUNCIONES DE INTERFAZ (menú interactivo y argumentos) - MODIFICADAS
# -------------------------------------------------------------------
def convert_cookie_dict(cookies_dict, country_code):
    """Convierte un diccionario de cookies a string formateado."""
    if not cookies_dict:
        return "No se obtuvieron cookies"
    return '; '.join([f"{k}={v}" for k, v in cookies_dict.items()])

async def generate_cookies(country=None, add_address=True):
    """Genera cookies para uno o todos los dominios."""
    country_map = {
        'CA': 'amazon.ca', 'MX': 'amazon.com.mx', 'US': 'amazon.com',
        'UK': 'amazon.co.uk', 'DE': 'amazon.de', 'FR': 'amazon.fr',
        'IT': 'amazon.it', 'ES': 'amazon.es', 'JP': 'amazon.co.jp',
        'AU': 'amazon.com.au', 'IN': 'amazon.in'
    }
    
    result = {
        'success': False,
        'data': None,
        'error': None,
        'country': country
    }
    
    if country:
        country = country.upper()
        if country in country_map:
            domain = country_map[country]
            print(f"\n🔄 Procesando {domain}...")
            account_data = await create_amazon_account(domain, add_address_flag=add_address)
            if account_data:
                result['success'] = True
                result['data'] = account_data
            else:
                result['error'] = f"No se pudo generar cookie para {country}"
        else:
            result['error'] = f"País no soportado: {country}"
    else:
        # Para múltiples países, devolvemos una lista
        results = []
        for dom in domains_to_run:
            print(f"\n🔄 Procesando {dom}...")
            account_data = await create_amazon_account(dom, add_address_flag=add_address)
            if account_data:
                results.append(account_data)
            await asyncio.sleep(5)
        result['success'] = len(results) > 0
        result['data'] = results
        result['error'] = None if results else "No se generaron cookies"
    
    return result

def interactive_menu():
    """Menú interactivo para ejecución manual."""
    print("="*60)
    print("🍪 Generador de Cookies Amazon - Versión Completa")
    print("="*60)
    print("\nVariables de entorno requeridas:")
    print("  - PROXY_STRING (ej. user:pass@host:port)")
    print("  - API_KEY_2CAPTCHA o API_KEY_ANTICAPTCHA")
    print("  - HERO_SMS_API_KEY (opcional, para amazon.com)")
    print("="*60)

    # Verificar configuraciones mínimas
    if not API_KEY_2CAPTCHA and not API_KEY_ANTICAPTCHA:
        print("❌ ERROR: Debes configurar al menos una API de captcha (2captcha o anticaptcha)")
        return
    if not PROXY_HOST_PORT:
        print("❌ ERROR: PROXY_STRING no configurada")
        return

    while True:
        print("\n--- MENÚ ---")
        print("1. Generar cookies para un país específico")
        print("2. Generar cookies para todos los países")
        print("3. Salir")
        op = input("Opción: ").strip()

        if op == '1':
            print("\nPaíses disponibles: CA, MX, US, UK, DE, FR, IT, ES, JP, AU, IN")
            pais = input("Código de país: ").strip()
            print("\n¿Agregar dirección a la cuenta?")
            add_addr = input("Agregar dirección? (s/n, por defecto s): ").strip().lower()
            add_address_flag = add_addr != 'n'
            
            result = asyncio.run(generate_cookies(pais, add_address_flag))
            if result['success']:
                data = result['data']
                print(f"\n✅ Cookie generada exitosamente:")
                print(f"   Email: {data['email']}")
                print(f"   Contraseña: {data['password']}")
                print(f"   Cookie: {data['cookie_string'][:100]}...")
                if data.get('address'):
                    print(f"   Dirección: {data['address']}")
            else:
                print(f"❌ Error: {result['error']}")
                
        elif op == '2':
            confirm = input("¿Generar cookies para TODOS los países? (s/n): ").strip().lower()
            if confirm in ('s', 'si', 'y', 'yes'):
                print("\n¿Agregar dirección a las cuentas?")
                add_addr = input("Agregar dirección? (s/n, por defecto s): ").strip().lower()
                add_address_flag = add_addr != 'n'
                
                result = asyncio.run(generate_cookies(None, add_address_flag))
                if result['success']:
                    print(f"\n✅ Se generaron {len(result['data'])} cookies")
                else:
                    print(f"❌ Error: {result['error']}")
            else:
                print("Cancelado")
        elif op == '3':
            print("👋 Saliendo...")
            break
        else:
            print("❌ Opción inválida")

# -------------------------------------------------------------------
# FUNCIÓN PARA API (nueva)
# -------------------------------------------------------------------
async def generate_cookie_api(country, add_address=True):
    """
    Función para ser llamada desde una API.
    Retorna un diccionario con los resultados.
    """
    try:
        result = await generate_cookies(country, add_address)
        return result
    except Exception as e:
        logger.exception("Error en generate_cookie_api")
        return {
            'success': False,
            'error': str(e),
            'country': country
        }

# -------------------------------------------------------------------
# ENTRYPOINT PRINCIPAL
# -------------------------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generador de cookies de Amazon')
    parser.add_argument('--country', help='Código de país (CA, MX, US, UK, DE, FR, IT, ES, JP, AU, IN)')
    parser.add_argument('--all', action='store_true', help='Generar para todos los países')
    parser.add_argument('--no-address', action='store_true', help='No agregar dirección a la cuenta')
    parser.add_argument('--json', action='store_true', help='Salida en formato JSON (para API)')
    args = parser.parse_args()

    add_address_flag = not args.no_address

    if args.country:
        if args.json:
            # Modo JSON - para API
            result = asyncio.run(generate_cookie_api(args.country, add_address_flag))
            print(json.dumps(result, indent=2, default=str))
        else:
            # Modo interactivo simple
            result = asyncio.run(generate_cookies(args.country, add_address_flag))
            if result['success']:
                data = result['data']
                print(f"\n✅ Cookie generada exitosamente:")
                print(f"   Email: {data['email']}")
                print(f"   Contraseña: {data['password']}")
                print(f"   Cookie: {data['cookie_string']}")
            else:
                print(f"❌ Error: {result['error']}")
    elif args.all:
        if args.json:
            result = asyncio.run(generate_cookies(None, add_address_flag))
            print(json.dumps(result, indent=2, default=str))
        else:
            asyncio.run(generate_cookies(None, add_address_flag))
    else:
        interactive_menu()