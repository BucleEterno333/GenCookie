#!/usr/bin/env python3
"""
Amazon Cookie Generator - Versión API REST
- Mantiene toda la funcionalidad original
- Configuración mediante variables de entorno
- 2captcha con fallback a anticaptcha
- Integración con Hero SMS para verificación telefónica
- AHORA: Captura de pantalla en cada paso y envío al frontend (screenshot en base64)
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
from urllib.parse import urlencode, urljoin, quote
from bs4 import BeautifulSoup
import requests
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading

# -------------------------------------------------------------------
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO
# -------------------------------------------------------------------
# Captcha
CAPTCHA_PROVIDER = os.getenv('CAPTCHA_PROVIDER', '2captcha')
API_KEY_2CAPTCHA = os.getenv('API_KEY_2CAPTCHA', '')
API_KEY_ANTICAPTCHA = os.getenv('API_KEY_ANTICAPTCHA', '')

# Proxy
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

# Configuración del servidor
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8080'))
API_KEY = os.getenv('API_KEY', '')  # Opcional, para autenticar peticiones

# User-Agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:130.0) Gecko/20100101 Firefox/130.0'
]

# -------------------------------------------------------------------
# CONFIGURACIÓN FIJA DE DOMINIOS Y URLS
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

# Mapa de códigos de país a dominio
country_to_domain = {
    'CA': 'amazon.ca', 'MX': 'amazon.com.mx', 'US': 'amazon.com',
    'UK': 'amazon.co.uk', 'DE': 'amazon.de', 'FR': 'amazon.fr',
    'IT': 'amazon.it', 'ES': 'amazon.es', 'JP': 'amazon.co.jp',
    'AU': 'amazon.com.au', 'IN': 'amazon.in'
}

# URLs de login
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

register_urls = {
    'amazon.ca': 'https://www.amazon.ca/ap/register?openid.mode=checkid_setup&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns.pape=http%3A%2F%2Fspecs.openid.net%2Fextensions%2Fpape%2F1.0&showRememberMe=true&openid.pape.max_auth_age=3600&pageId=anywhere_ca&prepopulatedLoginId=&openid.assoc_handle=anywhere_v2_ca&openid.return_to=https%3A%2F%2Fwww.amazon.ca%2Fyour-account&policy_handle=Retail-Checkout',
    'amazon.com.mx': 'https://www.amazon.com.mx/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com.mx%2F%3Fref_%3Dnav_ya_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=mxflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0',
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

# Cookies iniciales
INITIAL_COOKIES = {}
for domain in domains:
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
    level=logging.INFO,
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
def test_proxy(session):
    """Prueba la conectividad del proxy y retorna la IP pública."""
    try:
        response = session.get('https://api.ipify.org?format=json', timeout=15)
        if response.status_code != 200:
            return False, f"Status code {response.status_code}"
        data = response.json()
        return True, data['ip']
    except Exception as e:
        return False, str(e)

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
# CAPTCHA RESOLUTION
# -------------------------------------------------------------------
def solve_captcha(site_key, page_url, is_image_captcha=False, image_path=None):
    """Resuelve captcha usando 2captcha o anticaptcha."""
    solution = None
    logger.debug(f"Intentando resolver captcha con site_key={site_key}, url={page_url}")

    if API_KEY_2CAPTCHA and (CAPTCHA_PROVIDER == '2captcha' or not solution):
        try:
            from twocaptcha import TwoCaptcha
            solver = TwoCaptcha(API_KEY_2CAPTCHA)
            if is_image_captcha and image_path:
                result = solver.normal(image_path)
                solution = result['code']
            else:
                result = solver.recaptcha(sitekey=site_key, url=page_url)
                solution = result['code']
        except Exception as e:
            logger.warning(f"2captcha falló: {e}")
            solution = None

    if not solution and API_KEY_ANTICAPTCHA:
        try:
            from anticaptchaofficial.recaptchav2proxyless import recaptchaV2Proxyless
            from anticaptchaofficial.imagecaptcha import imagecaptcha
            if is_image_captcha and image_path:
                solver = imagecaptcha()
                solver.set_api_key(API_KEY_ANTICAPTCHA)
                solution = solver.solve_and_return_solution(image_path)
            else:
                solver = recaptchaV2Proxyless()
                solver.set_api_key(API_KEY_ANTICAPTCHA)
                solver.set_website_url(page_url)
                solver.set_website_key(site_key)
                solution = solver.solve_and_return_solution()
        except Exception as e:
            logger.error(f"anticaptcha falló: {e}")
            solution = None

    if solution:
            logger.debug(f"✅ Captcha resuelto: {solution[:10]}...")
    else:
            logger.error("❌ No se obtuvo solución de captcha")
    return solution

# -------------------------------------------------------------------
# HERO SMS
# -------------------------------------------------------------------
async def get_hero_sms_number():
    """Solicita un número de teléfono temporal a Hero SMS."""
    if not HERO_SMS_API_KEY:
        return None
    url = "https://hero-sms.com/api/v1/numbers/rent"
    headers = {"Authorization": f"Bearer {HERO_SMS_API_KEY}"}
    payload = {
        "country": HERO_SMS_COUNTRY,
        "operator": HERO_SMS_OPERATOR,
        "service": "amazon"
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            phone = data.get('phone_number')
            request_id = data.get('request_id')
            if phone and request_id:
                return phone, request_id
        return None
    except Exception:
        return None

async def get_hero_sms_code(request_id, timeout=120):
    """Espera y obtiene el código SMS de Hero SMS."""
    url = f"https://hero-sms.com/api/v1/numbers/wait/{request_id}"
    headers = {"Authorization": f"Bearer {HERO_SMS_API_KEY}"}
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'received':
                    message = data.get('message', '')
                    code_match = re.search(r'\b(\d{5,6})\b', message)
                    if code_match:
                        return code_match.group(1)
            await asyncio.sleep(5)
        except Exception:
            await asyncio.sleep(5)
    return None

# -------------------------------------------------------------------
# CORREO TEMPORAL
# -------------------------------------------------------------------
async def generate_temp_email():
    """Genera una dirección de correo temporal."""
    services = [
        ('mail.tm', 'https://api.mail.tm'),
        ('guerrillamail', 'https://api.guerrillamail.com'),
        ('tempmail.plus', 'https://api.tempmail.plus')
    ]
    for service_name, api_url in services:
        try:
            if service_name == 'mail.tm':
                resp = requests.get(f"{api_url}/domains", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    domains_list = data.get('hydra:member', [])
                    if domains_list and domains_list[0].get('domain'):
                        domain = domains_list[0]['domain']
                        email = f"{uuid.uuid4().hex[:8]}@{domain}"
                        password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
                        acc_resp = requests.post(
                            f"{api_url}/accounts",
                            json={"address": email, "password": password},
                            timeout=10
                        )
                        if acc_resp.status_code == 201:
                            token = acc_resp.json().get('token')
                            return email, token, service_name
            elif service_name == 'guerrillamail':
                resp = requests.get(f"{api_url}/ajax.php?f=get_email_address&ip=127.0.0.1", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    email = data.get('email_addr')
                    token = data.get('sid_token')
                    if email and token:
                        return email, token, service_name
            elif service_name == 'tempmail.plus':
                resp = requests.get(f"{api_url}/generate", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    email = data.get('email')
                    token = data.get('token')
                    if email and token:
                        return email, token, service_name
        except Exception:
            continue
    return None, None, None

async def get_verification_code(email, token, service, max_attempts=15, wait_time=8):
    """Obtiene el código de verificación del correo temporal."""
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
                        text = mail.get('text', '') or mail.get('html', '') or mail.get('intro', '')
                        code = get_str(text, 'Your verification code is ', '\n')
                        if code:
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
                            return code
            elif service == 'tempmail.plus' and token:
                resp = requests.get(f"https://api.tempmail.plus/messages/{token}", timeout=10)
                if resp.status_code == 200:
                    emails = resp.json().get('messages', [])
                    for mail in emails:
                        text = mail.get('text', '') or mail.get('html', '')
                        code = get_str(text, 'Your verification code is ', '\n')
                        if code:
                            return code
        except Exception:
            pass
        await asyncio.sleep(wait_time)
    return None

# -------------------------------------------------------------------
# RE-AUTENTICACIÓN
# -------------------------------------------------------------------
async def login_again(session, domain, email, password, token=None, service=None, max_attempts=3):
    """Vuelve a iniciar sesión en la cuenta si la sesión expiró."""
    for attempt in range(max_attempts):
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        session.cookies.clear()
        for key, value in INITIAL_COOKIES[domain].items():
            session.cookies.set(key, value, domain=f".{domain}")

        resp = session.get(login_urls[domain], headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            await asyncio.sleep(2 ** attempt)
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Detectar captcha
        captcha_div = soup.find('div', {'id': 'captchacharacters'})
        recaptcha_div = soup.find('div', {'class': re.compile('g-recaptcha')})
        if 'captcha' in resp.text.lower() or captcha_div or recaptcha_div:
            if recaptcha_div:
                site_key = recaptcha_div.get('data-sitekey')
                if site_key:
                    captcha_solution = solve_captcha(site_key, login_urls[domain])
                    if captcha_solution:
                        session.post(
                            login_urls[domain],
                            data={'g-recaptcha-response': captcha_solution},
                            headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                            timeout=15,
                            allow_redirects=True
                        )
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
                            session.post(
                                login_urls[domain],
                                data={'cvf_captcha_input': solution},
                                headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                                timeout=15,
                                allow_redirects=True
                            )

        # Buscar formulario de login
        form = (soup.find('form', {'id': re.compile('ap_signin_form|signin|login', re.I)}) or
                soup.find('form', {'action': re.compile('signin|sign-in|login', re.I)}) or
                soup.find('form', {'method': 'post'}))
        if not form:
            await asyncio.sleep(2 ** attempt)
            continue

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

        soup = BeautifulSoup(login_resp.text, 'html.parser')

        # Verificar si pide verificación en dos pasos
        if 'cvf' in login_resp.url.lower() or 'verification' in login_resp.text.lower():
            verification_code = await get_verification_code(email, token, service)
            if not verification_code:
                await asyncio.sleep(2 ** attempt)
                continue

            cvf_form = (soup.find('form', {'id': 'cvf_form'}) or
                        soup.find('form', {'action': re.compile('cvf|verify', re.I)}) or
                        soup.find('form', {'method': 'post'}))
            if not cvf_form:
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
            session.post(
                cvf_action,
                data=urlencode(cvf_payload),
                headers={**headers, 'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15,
                allow_redirects=True
            )

        if login_resp.status_code == 200 and 'signin' not in login_resp.url.lower():
            return True

        await asyncio.sleep(2 ** attempt)
    return False

# -------------------------------------------------------------------
# AGREGAR DIRECCIÓN
# -------------------------------------------------------------------
async def add_address(session, domain, email, password, token=None, service=None):
    """Agrega una dirección por defecto a la cuenta."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"{base_urls[domain]}/gp/your-account?ref_=nav_AccountFlyout_ya",
        "Viewport-Width": "1536"
    }

    for key, value in INITIAL_COOKIES[domain].items():
        session.cookies.set(key, value, domain=f".{domain}")

    resp = session.get(address_book_urls[domain], headers=headers, timeout=15, allow_redirects=True)
    if resp.status_code != 200:
        return None

    if 'signin' in resp.url.lower():
        if not await login_again(session, domain, email, password, token, service):
            return None
        resp = session.get(address_book_urls[domain], headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return None

    resp = session.get(add_address_urls[domain], headers=headers, timeout=15, allow_redirects=True)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Detectar captcha
    captcha_div = soup.find('div', {'id': 'captchacharacters'})
    recaptcha_div = soup.find('div', {'class': re.compile('g-recaptcha')})
    if 'captcha' in resp.text.lower() or captcha_div or recaptcha_div:
        if recaptcha_div:
            site_key = recaptcha_div.get('data-sitekey')
            if site_key:
                captcha_solution = solve_captcha(site_key, add_address_urls[domain])
                if captcha_solution:
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
        resp = session.get(add_address_urls[domain], headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

    form = soup.find('form', {'id': 'address-ui-widgets-form'}) or soup.find('form', {'action': re.compile('add', re.I)})
    if not form:
        return None

    address_data = {
        'amazon.ca': {
            'countryCode': 'CA', 'fullName': 'Mark O. Montanez',
            'phone': f'1{random.randint(1000000000, 9999999999)}',
            'line1': '456 Bloor Street West', 'city': 'Toronto',
            'state': 'ON', 'postalCode': 'M5S 1X8'
        },
        'amazon.com.mx': {
            'countryCode': 'MX', 'fullName': 'Juan Pérez',
            'phone': f'52{random.randint(1000000000, 9999999999)}',
            'line1': 'Calle Reforma 123', 'city': 'Ciudad de México',
            'state': 'CDMX', 'postalCode': '06000'
        },
        'amazon.com': {
            'countryCode': 'US', 'fullName': 'John Doe',
            'phone': f'1{random.randint(1000000000, 9999999999)}',
            'line1': '123 Main Street', 'city': 'New York',
            'state': 'NY', 'postalCode': '10001'
        },
        'amazon.co.uk': {
            'countryCode': 'GB', 'fullName': 'James Smith',
            'phone': f'44{random.randint(1000000000, 9999999999)}',
            'line1': '123 Oxford Street', 'city': 'London',
            'state': '', 'postalCode': 'W1D 1AA'
        },
        'amazon.de': {
            'countryCode': 'DE', 'fullName': 'Hans Müller',
            'phone': f'49{random.randint(1000000000, 9999999999)}',
            'line1': 'Hauptstraße 12', 'city': 'Berlin',
            'state': '', 'postalCode': '10115'
        },
        'amazon.fr': {
            'countryCode': 'FR', 'fullName': 'Pierre Dubois',
            'phone': f'33{random.randint(1000000000, 9999999999)}',
            'line1': '12 Rue de Rivoli', 'city': 'Paris',
            'state': '', 'postalCode': '75001'
        },
        'amazon.it': {
            'countryCode': 'IT', 'fullName': 'Giuseppe Rossi',
            'phone': f'39{random.randint(1000000000, 9999999999)}',
            'line1': 'Via Roma 10', 'city': 'Roma',
            'state': '', 'postalCode': '00184'
        },
        'amazon.es': {
            'countryCode': 'ES', 'fullName': 'Carlos García',
            'phone': f'34{random.randint(1000000000, 9999999999)}',
            'line1': 'Calle Mayor 15', 'city': 'Madrid',
            'state': '', 'postalCode': '28013'
        },
        'amazon.co.jp': {
            'countryCode': 'JP', 'fullName': 'Taro Yamada',
            'phone': f'81{random.randint(1000000000, 9999999999)}',
            'line1': '1-2-3 Shibuya', 'city': 'Tokyo',
            'state': '', 'postalCode': '150-0002'
        },
        'amazon.com.au': {
            'countryCode': 'AU', 'fullName': 'Emma Wilson',
            'phone': f'61{random.randint(1000000000, 9999999999)}',
            'line1': '123 George Street', 'city': 'Sydney',
            'state': 'NSW', 'postalCode': '2000'
        },
        'amazon.in': {
            'countryCode': 'IN', 'fullName': 'Amit Sharma',
            'phone': f'91{random.randint(1000000000, 9999999999)}',
            'line1': '123 MG Road', 'city': 'Mumbai',
            'state': 'Maharashtra', 'postalCode': '400001'
        }
    }

    country_data = address_data[domain]

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

    post_url = urljoin(base_urls[domain], form.get('action') or "/a/addresses/add")
    headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": base_urls[domain],
        "Referer": add_address_urls[domain]
    })

    resp = session.post(
        post_url,
        data=urlencode(post_data),
        headers=headers,
        timeout=15,
        allow_redirects=True
    )

    if resp.status_code != 200:
        return None

    return True

# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA CAPTURAR PANTALLA
# -------------------------------------------------------------------
async def take_screenshot(page, step_name):
    """Captura la pantalla actual y la retorna en base64."""
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
    """Obtiene el contenido de la página asegurando que no esté navegando."""
    try:
        # Esperar a que la página esté completamente cargada
        await page.wait_for_function('document.readyState === "complete"', timeout=timeout*1000)
        # Pequeña pausa adicional para evitar condiciones de carrera
        await page.wait_for_timeout(500)
        return await page.content()
    except Exception as e:
        logger.warning(f"⚠️ Error en safe_get_content: {e}")
        # Reintentar una vez después de esperar
        await page.wait_for_timeout(2000)
        return await page.content()
    
    

# -------------------------------------------------------------------
# CREACIÓN DE CUENTA PRINCIPAL (versión estable con manejo de navegación)
# -------------------------------------------------------------------





async def create_amazon_account(domain, email=None, token=None, service=None, add_address_flag=True):
    """
    Crea una cuenta de Amazon y retorna los datos de la cuenta.
    Retorna: (account_data, error_message, screenshot_base64)
    """
    logger.debug(f"🏁 [ENTRADA] create_amazon_account para {domain}")
    
    playwright = None
    browser = None
    context = None
    page = None
    session = None

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

    last_screenshot = None

    try:
        # ===== PASO 1: Configurar sesión y proxy =====
        logger.debug("📦 [PASO 1] Configurando sesión requests...")
        session = requests.Session()
        if PROXY_HOST_PORT:
            proxy_url = f"http://{PROXY_HOST_PORT}"
            if PROXY_AUTH:
                proxy_url = f"http://{PROXY_AUTH}@{PROXY_HOST_PORT}"
            session.proxies = {'http': proxy_url, 'https': proxy_url}
            logger.debug(f"   ✅ Proxy configurado: {PROXY_HOST_PORT}")
        else:
            logger.warning("   ⚠️ No se configuró proxy")

        # ===== PASO 2: Probar proxy =====
        logger.debug("🔄 [PASO 2] Probando proxy...")
        ok, msg = test_proxy(session)
        if not ok:
            logger.error(f"   ❌ Proxy no funciona: {msg}")
            return None, f"Proxy error: {msg}", None
        logger.debug(f"   ✅ Proxy OK - IP: {msg}")

        # ===== PASO 3: Generar email =====
        logger.debug("📧 [PASO 3] Generando email temporal...")
        if not email:
            email, token, service = await generate_temp_email()
            if not email:
                logger.error("   ❌ No se pudo generar email temporal")
                return None, "No se pudo generar email temporal", None
            logger.debug(f"   ✅ Email generado: {email} (servicio: {service})")
        
        # ===== PASO 4: Generar credenciales =====
        logger.debug("🔑 [PASO 4] Generando credenciales...")
        password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
        first_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
        last_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
        fullname = f"{first_name} {last_name}"
        
        account_data['email'] = email
        account_data['password'] = password
        account_data['name'] = fullname
        
        logger.debug(f"   👤 Nombre: {fullname}")

        # ===== PASO 5: Iniciar Playwright =====
        logger.debug("🎬 [PASO 5] Iniciando Playwright...")
        try:
            playwright = await async_playwright().start()
            logger.debug("   ✅ Playwright iniciado")
        except Exception as e:
            logger.error(f"   ❌ Error iniciando Playwright: {e}")
            return None, f"Error iniciando Playwright: {e}", None
            
        launch_options = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                # Evitar detección de automatización
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
                '--no-zygote',
                '--no-first-run',
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
                '--enable-automation=0',  # Clave
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

        # ===== PASO 6: Lanzar browser =====
        logger.debug("🚀 [PASO 6] Lanzando browser...")
        try:
            browser = await playwright.chromium.launch(**launch_options)
            logger.debug("   ✅ Browser lanzado")
        except Exception as e:
            logger.error(f"   ❌ Error lanzando browser: {e}")
            return None, f"Error lanzando browser: {e}", None
            
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=random.choice(USER_AGENTS),
            locale='es-MX',
            timezone_id='America/Mexico_City'
        )

        # Inyectar script para ocultar automatización
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

        # ===== PASO 7: Navegar a registro =====
        register_url = register_urls.get(domain)
        logger.debug(f"🌐 [PASO 7] Navegando a: {register_url}")

        await page.set_extra_http_headers({
            'Accept-Language': 'es-MX,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Ch-Ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })

        random_delay = random.uniform(2, 4)
        logger.debug(f"   ⏱️ Delay aleatorio de {random_delay:.2f} segundos...")
        await asyncio.sleep(random_delay)

        load_success = False
        strategies = [
            {'wait': 'networkidle', 'timeout': 120000, 'name': 'networkidle (120s)'},
            {'wait': 'domcontentloaded', 'timeout': 60000, 'name': 'domcontentloaded (60s)'},
            {'wait': None, 'timeout': 30000, 'name': 'carga básica (30s)'}
        ]

        for strategy in strategies:
            try:
                logger.debug(f"   🔄 Intentando estrategia: {strategy['name']}")
                if strategy['wait']:
                    await page.goto(register_url, wait_until=strategy['wait'], timeout=strategy['timeout'])
                else:
                    await page.goto(register_url, timeout=strategy['timeout'])
                
                await page.wait_for_timeout(5000)
                body = await page.query_selector('body')
                if body:
                    logger.debug(f"   ✅ Página cargada con estrategia: {strategy['name']}")
                    load_success = True
                    break
                else:
                    logger.warning(f"   ⚠️ No se detectó body, intentando siguiente estrategia")
            except Exception as e:
                logger.warning(f"   ⚠️ Estrategia {strategy['name']} falló: {str(e)[:100]}")
                continue

        if not load_success:
            logger.error("❌ No se pudo cargar la página con ninguna estrategia")
            try:
                logger.debug("   🔄 Último recurso: recargar página")
                await page.reload(timeout=60000)
                await page.wait_for_timeout(5000)
                body = await page.query_selector('body')
                if body:
                    logger.debug("   ✅ Página cargada con recarga")
                    load_success = True
                else:
                    logger.error("   ❌ Recarga falló")
                    last_screenshot = await take_screenshot(page, "error_no_body")
                    return None, "No se pudo cargar la página de registro", last_screenshot
            except Exception as e:
                logger.error(f"   ❌ Recarga falló: {e}")
                last_screenshot = await take_screenshot(page, "error_recarga")
                return None, f"Error cargando página: {e}", last_screenshot

        last_screenshot = await take_screenshot(page, "registro_cargada")

        # ===== PASO 8: Primera página - Ingresar email =====
        logger.debug("📧 [PASO 8] Primera página: Ingresando email...")
        
        email_field = None
        email_selectors_paso1 = [
            'input#ap_email_login',
            'input[name="email"]',
            'input[type="email"]',
            'input[autocomplete="username"]'
        ]
        
        for selector in email_selectors_paso1:
            logger.debug(f"   Probando selector: {selector}")
            field = await page.query_selector(selector)
            if field and await field.is_visible():
                email_field = field
                logger.debug(f"   ✅ Campo email encontrado con selector: {selector}")
                break
        
        if not email_field:
            logger.error("❌ No se encontró campo de email visible")
            last_screenshot = await take_screenshot(page, "error_no_email_field")
            return None, "No se encontró campo de email", last_screenshot
        
        await email_field.fill(email)
        logger.debug(f"   ✅ Email llenado: {email}")
        last_screenshot = await take_screenshot(page, "email_llenado")

        # ===== PASO 9: Hacer clic en Continuar =====
        logger.debug("🖱️ [PASO 9] Haciendo clic en Continuar...")
        
        continue_button = None
        continue_selectors = [
            'input#continue',
            'input.a-button-input',
            'button#continue',
            'span input[type="submit"]',
            'input[value="Continuar"]',
            'button:has-text("Continuar")'
        ]
        
        for selector in continue_selectors:
            button = await page.query_selector(selector)
            if button and await button.is_visible():
                continue_button = button
                logger.debug(f"   ✅ Botón Continuar encontrado con selector: {selector}")
                break
        
        if not continue_button:
            logger.error("❌ No se encontró botón Continuar")
            last_screenshot = await take_screenshot(page, "error_no_continue_button")
            return None, "No se encontró botón Continuar", last_screenshot
        
        await continue_button.click()
        logger.debug("   ✅ Click realizado")
        
        # Esperar a que la navegación se complete
        await page.wait_for_load_state('networkidle', timeout=15000)
        await page.wait_for_timeout(2000)
        logger.debug(f"   📍 Nueva URL: {page.url}")
        last_screenshot = await take_screenshot(page, "despues_continuar")

        # ===== PASO 10: Página intermedia "Proceder a crear una cuenta" =====
        logger.debug("🔍 [PASO 10] Verificando página intermedia de confirmación...")
        proceed_selectors = [
            'span#intention-submit-button input.a-button-input',
            'input[type="submit"][aria-labelledby="intention-submit-button-announce"]',
            'button:has-text("Proceder a crear una cuenta")',
            'input[value="Proceder a crear una cuenta"]',
            'input[value*="Proceder"]',
            'button:has-text("Create account")',
            'input[value*="Create account"]'
        ]
        proceed_button = None
        for selector in proceed_selectors:
            try:
                button = await page.wait_for_selector(selector, state='visible', timeout=3000)
                if button:
                    proceed_button = button
                    logger.debug(f"   ✅ Botón 'Proceder' encontrado con selector: {selector}")
                    break
            except:
                continue

        if proceed_button:
            logger.debug("   🔘 Haciendo clic en 'Proceder a crear una cuenta'...")
            await proceed_button.click()
            # Esperar a que aparezca el campo de nombre (formulario de registro)
            try:
                # Esperar a que la navegación termine y el campo sea visible
                await page.wait_for_selector('#ap_customer_name', state='visible', timeout=30000)
                logger.debug("   ✅ Campo de nombre visible, página de registro cargada")
            except Exception as e:
                logger.error(f"   ❌ No apareció el campo de nombre: {e}")
                last_screenshot = await take_screenshot(page, "error_no_customer_name")
                # Verificar si hay algún mensaje de error (como JavaScript deshabilitado)
                content = await safe_get_content(page) 
                if "JavaScript se ha deshabilitado" in content:
                    return None, "Error: JavaScript deshabilitado detectado por Amazon", last_screenshot
                return None, f"Timeout esperando campo de nombre: {e}", last_screenshot
            await page.wait_for_timeout(2000)
            last_screenshot = await take_screenshot(page, "despues_proceder")
        else:
            logger.debug("   ℹ️ No se detectó página intermedia, continuando directamente")
            # Asegurarnos de que el campo de nombre esté presente
            try:
                await page.wait_for_selector('#ap_customer_name', state='visible', timeout=20000)
                logger.debug("   ✅ Campo de nombre visible directamente")
            except:
                logger.warning("   ⚠️ No se encontró campo de nombre, puede que la página sea diferente")


        # ===== PASO 11: Llenar formulario de registro =====
        logger.debug("📝 [PASO 12] Llenando formulario completo...")
        last_screenshot = await take_screenshot(page, "formulario_antes_llenar")

        # Función helper para llenar campos con reintentos
        async def safe_fill(selector, value, description):
            for attempt in range(3):
                try:
                    field = await page.wait_for_selector(selector, state='visible', timeout=5000)
                    await field.fill(value)
                    logger.debug(f"   ✅ {description} llenado con selector: {selector}")
                    return True
                except Exception as e:
                    logger.debug(f"      ⚠️ Intento {attempt+1} falló: {str(e)[:50]}")
                    await page.wait_for_timeout(1000)
            return False

        # 12.1 Campo de nombre
        name_selectors = [
            'input#ap_customer_name',
            'input[name="customerName"]',
            'input[placeholder*="nombre" i]',
            'input[placeholder*="name" i]'
        ]
        
        name_filled = False
        for selector in name_selectors:
            if await safe_fill(selector, fullname, "Nombre"):
                name_filled = True
                break
        
        if not name_filled:
            logger.warning("⚠️ No se pudo llenar campo de nombre, puede estar precargado")

        # 12.2 Campo de email (puede estar precargado)
        email_second = await page.query_selector('input[name="email"], input#ap_email, input[type="email"]')
        if email_second:
            current_email = await email_second.get_attribute('value')
            if not current_email:
                await email_second.fill(email)
                logger.debug("   ✅ Email (segunda página) llenado")
            else:
                logger.debug(f"   ℹ️ Email ya precargado: {current_email}")

        # 12.3 Campo de contraseña
        password_selectors = [
            'input#ap_password',
            'input[name="password"]',
            'input[type="password"]'
        ]
        
        password_filled = False
        for selector in password_selectors:
            if await safe_fill(selector, password, "Contraseña"):
                password_filled = True
                break
        
        if not password_filled:
            logger.error("❌ No se pudo llenar campo de contraseña")
            last_screenshot = await take_screenshot(page, "error_password")
            return None, "No se pudo llenar campo de contraseña", last_screenshot

        # 12.4 Campo de confirmación de contraseña
        confirm_selectors = [
            'input#ap_password_check',
            'input[name="passwordCheck"]',
            'input[placeholder*="confirm" i]'
        ]
        
        for selector in confirm_selectors:
            if await safe_fill(selector, password, "Confirmación"):
                break

        # 12.5 Campo de teléfono (para TODOS los países)
        phone_selectors = [
            'input#ap_phone_number',
            'input[name="phoneNumber"]',
            'input[type="tel"]'
        ]
        phone_field = None
        for selector in phone_selectors:
            field = await page.query_selector(selector)
            if field and await field.is_visible():
                phone_field = field
                break

        if phone_field:
            country_codes = {
                'amazon.com': '1', 'amazon.ca': '1', 'amazon.com.mx': '52',
                'amazon.co.uk': '44', 'amazon.de': '49', 'amazon.fr': '33',
                'amazon.it': '39', 'amazon.es': '34', 'amazon.co.jp': '81',
                'amazon.com.au': '61', 'amazon.in': '91'
            }
            code = country_codes.get(domain, '1')
            phone_number = f"+{code}{random.randint(100000000, 999999999)}"
            
            await phone_field.fill(phone_number)
            account_data['phone'] = phone_number
            logger.debug(f"   ✅ Teléfono llenado: {phone_number}")
            
            if domain == 'amazon.com' and HERO_SMS_API_KEY:
                phone_info = await get_hero_sms_number()
                if phone_info:
                    phone_number, request_id = phone_info
                    await phone_field.fill(phone_number)
                    account_data['phone'] = phone_number
                    logger.debug(f"   ✅ Número real obtenido: {phone_number}")

        # ===== PASO 14: Verificar si aparece captcha después del envío =====
        logger.debug("🔍 Verificando si aparece captcha después del envío...")
        await page.wait_for_timeout(5000)  # Esperar un poco a que cargue la página

        # Comprobar si la URL contiene "captcha" o hay elementos de captcha
        current_url = page.url.lower()
        content = await page.content()

        captcha_detected = False
        captcha_type = None
        site_key = None
        captcha_image_url = None

        # 1. Buscar reCAPTCHA
        recaptcha_div = await page.query_selector('div.g-recaptcha')
        if recaptcha_div:
            site_key = await recaptcha_div.get_attribute('data-sitekey')
            if site_key:
                captcha_detected = True
                captcha_type = 'recaptcha'
                logger.debug(f"✅ reCAPTCHA detectado con sitekey: {site_key}")

        # 2. Buscar captcha de imagen de Amazon (típico)
        if not captcha_detected:
            # Buscar un div con id="captcha" o similares
            captcha_container = await page.query_selector('#captcha, .captcha, .a-row captcha')
            if captcha_container:
                # Buscar una imagen dentro
                img = await captcha_container.query_selector('img')
                if img:
                    captcha_image_url = await img.get_attribute('src')
                    if captcha_image_url:
                        captcha_detected = True
                        captcha_type = 'image_captcha'
                        logger.debug(f"✅ Captcha de imagen detectado: {captcha_image_url}")

        # 3. Buscar por texto "captcha" en la URL o en el contenido
        if not captcha_detected and ('captcha' in current_url or 'captcha' in content.lower()):
            # Podría ser un captcha no estándar, intentamos buscar cualquier imagen
            all_images = await page.query_selector_all('img')
            for img in all_images:
                src = await img.get_attribute('src')
                if src and ('captcha' in src.lower() or 'captcha' in (await img.get_attribute('alt') or '').lower()):
                    captcha_image_url = src
                    captcha_detected = True
                    captcha_type = 'image_captcha_alt'
                    logger.debug(f"✅ Captcha de imagen alternativo detectado: {captcha_image_url}")
                    break

        if captcha_detected:
            logger.warning(f"⚠️ Captcha detectado (tipo: {captcha_type})")
            last_screenshot = await take_screenshot(page, "captcha_detectado")
            
            if captcha_type == 'recaptcha' and site_key:
                captcha_solution = solve_captcha(site_key, page.url, is_image_captcha=False)
                if captcha_solution:
                    logger.debug("✅ reCAPTCHA resuelto, enviando...")
                    # Insertar solución en el textarea de reCAPTCHA
                    await page.evaluate(f'document.getElementById("g-recaptcha-response").innerHTML="{captcha_solution}";')
                    # Hacer clic en el botón de enviar (puede ser diferente)
                    submit_btn = await page.query_selector('input[type="submit"], button[type="submit"]')
                    if submit_btn:
                        await submit_btn.click()
                    else:
                        # A veces el formulario se envía automáticamente
                        pass
                else:
                    logger.error("❌ No se pudo resolver reCAPTCHA")
                    return None, "No se pudo resolver reCAPTCHA", last_screenshot

            elif captcha_type in ['image_captcha', 'image_captcha_alt'] and captcha_image_url:
                # Descargar la imagen
                img_data = requests.get(captcha_image_url, timeout=10).content
                with open('temp_captcha.jpg', 'wb') as f:
                    f.write(img_data)
                captcha_solution = solve_captcha(None, page.url, is_image_captcha=True, image_path='temp_captcha.jpg')
                if captcha_solution:
                    logger.debug(f"✅ Captcha de imagen resuelto: {captcha_solution}")
                    # Buscar el campo de entrada para el código
                    input_field = await page.query_selector('input[name="cvf_captcha_input"], input[name="captcha"], input[type="text"]')
                    if input_field:
                        await input_field.fill(captcha_solution)
                        submit_btn = await page.query_selector('input[type="submit"], button[type="submit"]')
                        if submit_btn:
                            await submit_btn.click()
                    else:
                        logger.error("❌ No se encontró campo para ingresar el captcha")
                        return None, "No se encontró campo de captcha", last_screenshot
                else:
                    logger.error("❌ No se pudo resolver captcha de imagen")
                    return None, "No se pudo resolver captcha de imagen", last_screenshot

            # Esperar a que la página procese el captcha
            await page.wait_for_load_state('networkidle', timeout=30000)
            last_screenshot = await take_screenshot(page, "despues_captcha")

            # Verificar si aún hay mensaje de error (como JavaScript deshabilitado)
            content = await page.content()
            if "JavaScript se ha deshabilitado" in content:
                logger.error("❌ JavaScript deshabilitado después de captcha")
                return None, "JavaScript deshabilitado después de captcha", last_screenshot

        else:
            logger.debug("✅ No se detectó captcha, continuando...")

        logger.debug("📧 Verificando si se requiere confirmación de correo...")



        # ===== PASO 13: Verificación de correo electrónico =====
        await page.wait_for_timeout(3000)  # Esperar a que la página se estabilice
        content = await page.content()

        # Detectar la página de verificación de correo
        if "Verifica la dirección de correo electrónico" in content or "verify your email" in content.lower():
            logger.debug("✅ Página de verificación de correo detectada")
            
            # Buscar el campo para ingresar el código
            code_input = await page.query_selector('input[name="code"], input[type="text"]')
            if code_input:
                # Obtener el código de verificación del correo temporal
                verification_code = await get_verification_code(email, token, service)
                if verification_code:
                    await code_input.fill(verification_code)
                    logger.debug(f"✅ Código ingresado: {verification_code}")
                    
                    # Buscar el botón de confirmación (puede ser "Crear cuenta", "Verificar", etc.)
                    submit_btn = await page.query_selector('input[type="submit"], button[type="submit"]')
                    if submit_btn:
                        await submit_btn.click()
                        await page.wait_for_load_state('networkidle', timeout=30000)
                        last_screenshot = await take_screenshot(page, "despues_verificacion_correo")
                        logger.debug("✅ Código enviado, esperando respuesta...")
                    else:
                        logger.warning("⚠️ No se encontró botón de verificación")
                else:
                    logger.error("❌ No se pudo obtener código de verificación del correo")
                    last_screenshot = await take_screenshot(page, "error_verificacion_correo")
                    return None, "No se pudo obtener código de verificación", last_screenshot
            else:
                logger.warning("⚠️ No se encontró campo para ingresar el código")
                last_screenshot = await take_screenshot(page, "error_sin_campo_codigo")
                # No necesariamente es un error, puede que ya esté verificado
        else:
            logger.debug("✅ No se requiere verificación de correo, continuando...")

        # ===== PASO 14: Verificar si pide verificación de número =====
        logger.debug("📱 [PASO 14] Verificando si pide verificación de número...")
        
        await page.wait_for_load_state('networkidle', timeout=20000)
        content = await safe_get_content(page)

        soup = BeautifulSoup(content, 'html.parser')
        
        if 'verify' in page.url.lower() or 'cvf' in page.url.lower():
            phone_field = await page.query_selector('input[name="code"], input[placeholder*="código" i]')
            if phone_field:
                logger.debug("   📱 Verificación de número detectada")
                # Aquí se implementaría la lógica para obtener código SMS
                verification_code = "123456"  # Placeholder
                await phone_field.fill(verification_code)
                logger.debug("   ✅ Código de verificación llenado")
                
                submit_btn = await page.query_selector('input[type="submit"], button[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_load_state('networkidle', timeout=15000)
                    last_screenshot = await take_screenshot(page, "despues_verificacion")

        # ===== PASO 15: Verificar errores =====
        error_div = soup.find('div', {'class': re.compile('a-alert-error|a-alert-warning|a-box-error', re.I)})
        if error_div:
            error_msg = error_div.get_text(strip=True)
            logger.error(f"   ❌ Error en registro: {error_msg}")
            last_screenshot = await take_screenshot(page, "error_registro")
            return None, f"Error en registro: {error_msg}", last_screenshot

        # ===== PASO 16: Verificar éxito =====
        logger.debug("🎉 [PASO 16] Verificando éxito del registro...")
        
        if 'your-account' in page.url.lower() or 'account' in page.url.lower() or 'welcome' in page.url.lower():
            logger.debug("   ✅ Registro exitoso!")
            
            cookies = await context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
            
            account_data['cookie_dict'] = cookie_dict
            account_data['cookie_string'] = cookie_string
            logger.debug(f"   🍪 Cookies obtenidas: {len(cookie_dict)} cookies")

            for name, value in cookie_dict.items():
                session.cookies.set(name, value, domain=f".{domain}")

            # ===== PASO 17: Agregar dirección =====
            if add_address_flag:
                logger.debug("📍 [PASO 17] Agregando dirección...")
                addr_ok = await add_address(session, domain, email, password, token, service)
                account_data['address'] = "Dirección agregada" if addr_ok else "Error al agregar dirección"
                logger.debug(f"   ✅ Resultado dirección: {account_data['address']}")
            else:
                account_data['address'] = "No se agregó dirección"
                logger.debug("   ℹ️ Omisión de dirección")

            # ===== PASO 18: Visitar wallet =====
            try:
                logger.debug("💳 Visitando wallet para cookies completas...")
                await page.goto(wallet_urls[domain], wait_until='networkidle', timeout=20000)
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
            return None, f"Registro fallido, URL: {page.url}", last_screenshot

    except Exception as e:
        logger.exception(f"💥 Excepción en create_amazon_account: {str(e)}")
        if page:
            last_screenshot = await take_screenshot(page, "excepcion")
        return None, f"Excepción: {str(e)}", last_screenshot
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

# ========== FUNCIÓN DE DEBUG PARA VER ESTRUCTURA ==========
async def debug_amazon_structure(domain='amazon.com.mx'):
    """Función para ver la estructura exacta de la página de registro (MODO HEADLESS)"""
    
    print(f"\n🔍 DEBUGGEANDO ESTRUCTURA DE {domain}")
    print("="*50)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"🌐 Navegando a {register_urls[domain]}")
        await page.goto(register_urls[domain], wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        await page.screenshot(path=f'debug_{domain}.png')
        print(f"📸 Screenshot guardado como debug_{domain}.png")
        
        inputs = await page.query_selector_all('input')
        print(f"\n📋 INPUTS ENCONTRADOS ({len(inputs)}):")
        print("-"*50)
        
        for i, inp in enumerate(inputs):
            input_type = await inp.get_attribute('type') or 'N/A'
            input_name = await inp.get_attribute('name') or 'N/A'
            input_id = await inp.get_attribute('id') or 'N/A'
            input_placeholder = await inp.get_attribute('placeholder') or 'N/A'
            
            print(f"\n🔹 INPUT #{i+1}:")
            print(f"   Type: {input_type}")
            print(f"   Name: {input_name}")
            print(f"   ID: {input_id}")
            print(f"   Placeholder: {input_placeholder}")
        
        html = await page.content()
        with open(f'debug_{domain}.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n📄 HTML guardado como debug_{domain}.html")
        
        await browser.close()
        print("\n✅ Debug completado")

# ========== FUNCIÓN PARA API CON MÁS DEBUG ==========
async def generate_cookie_api(country, add_address=True):
    """
    Función para ser llamada desde la API.
    Retorna dict con success, data/error, y screenshot.
    """
    logger.debug(f"🚀 generate_cookie_api llamada con country={country}, add_address={add_address}")
    
    try:
        if country not in country_to_domain:
            error_msg = f'País no soportado: {country}'
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'country': country,
                'screenshot': None
            }
        
        domain = country_to_domain[country]
        logger.debug(f"📌 Dominio seleccionado: {domain}")
        
        logger.debug("⏳ Iniciando create_amazon_account...")
        account_data, error_msg, screenshot = await create_amazon_account(domain, add_address_flag=add_address)
        
        if account_data:
            logger.debug(f"✅ Cuenta creada exitosamente: email={account_data.get('email')}")
            return {
                'success': True,
                'data': account_data,
                'country': country,
                'screenshot': screenshot  # Puede ser None si no se pudo capturar al final
            }
        else:
            error_msg = error_msg or f'No se pudo generar cookie para {country}'
            logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'country': country,
                'screenshot': screenshot  # Última captura antes del error
            }
    except Exception as e:
        logger.exception(f"💥 Excepción en generate_cookie_api: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'country': country,
            'screenshot': None
        }

# -------------------------------------------------------------------
# API FLASK
# -------------------------------------------------------------------
# -------------------------------------------------------------------
# API FLASK
# -------------------------------------------------------------------
app = Flask(__name__)

# Configuración CORS explícita y segura
CORS(app, 
     origins=["https://ciber7erroristaschk.com"],  # Especifica tu dominio exacto
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True)

# También podemos añadir un after_request para garantizar cabeceras
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
        'service': 'Amazon Cookie Generator API',
        'endpoints': {
            '/generate': 'POST - Generar cookie (JSON: {"country": "US", "add_address": true})',
            '/health': 'GET - Verificar estado'
        }
    })

@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        # Respuesta vacía para preflight (las cabeceras las pondrá after_request)
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
    
    # Verificar API key si está configurada
    if API_KEY:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer ') or auth_header[7:] != API_KEY:
            return jsonify({'success': False, 'error': 'No autorizado'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Se requiere JSON'}), 400
    
    country = data.get('country', '').upper()
    add_address = data.get('add_address', True)
    
    if not country:
        return jsonify({'success': False, 'error': 'Falta el parámetro country'}), 400
    
    # Ejecutar la generación en un bucle asyncio nuevo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(generate_cookie_api(country, add_address))
        return jsonify(result)
    finally:
        loop.close()

@app.route('/diagnostic', methods=['GET'])
def diagnostic():
    """Endpoint de diagnóstico para verificar configuración"""
    return jsonify({
        'status': 'ok',
        'timestamp': time.time(),
        'config': {
            'proxy': 'configurado' if PROXY_HOST_PORT else 'no configurado',
            'proxy_string': PROXY_STRING[:20] + '...' if PROXY_STRING else None,
            'captcha_provider': CAPTCHA_PROVIDER,
            'has_2captcha': bool(API_KEY_2CAPTCHA),
            'has_anticaptcha': bool(API_KEY_ANTICAPTCHA),
            'hero_sms': bool(HERO_SMS_API_KEY),
            'supported_countries': list(country_to_domain.keys())
        },
        'environment': {
            'python_version': sys.version,
            'platform': sys.platform
        }
    })

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='API de generador de cookies Amazon')
    parser.add_argument('--cli', action='store_true', help='Ejecutar en modo CLI (menú interactivo)')
    parser.add_argument('--debug-structure', type=str, help='Ejecutar debug de estructura para un dominio (ej: amazon.com.mx)')
    args = parser.parse_args()

    if args.debug_structure:
        asyncio.run(debug_amazon_structure(args.debug_structure))
        sys.exit(0)

    if args.cli:
        # Modo CLI - menú interactivo
        print("="*60)
        print("🍪 Generador de Cookies Amazon - Modo CLI")
        print("="*60)
        print("\nVariables de entorno requeridas:")
        print("  - PROXY_STRING")
        print("  - API_KEY_2CAPTCHA o API_KEY_ANTICAPTCHA")
        print("="*60)

        if not API_KEY_2CAPTCHA and not API_KEY_ANTICAPTCHA:
            print("❌ ERROR: Configura al menos una API de captcha")
            sys.exit(1)
        if not PROXY_HOST_PORT:
            print("❌ ERROR: PROXY_STRING no configurada")
            sys.exit(1)

        while True:
            print("\n--- MENÚ ---")
            print("1. Generar cookie para un país")
            print("2. Salir")
            op = input("Opción: ").strip()

            if op == '1':
                print("\nPaíses disponibles: CA, MX, US, UK, DE, FR, IT, ES, JP, AU, IN")
                pais = input("Código de país: ").strip().upper()
                add_addr = input("¿Agregar dirección? (s/n, por defecto s): ").strip().lower()
                add_address_flag = add_addr != 'n'
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(generate_cookie_api(pais, add_address_flag))
                    if result['success']:
                        data = result['data']
                        print(f"\n✅ Cookie generada exitosamente:")
                        print(f"   Email: {data['email']}")
                        print(f"   Contraseña: {data['password']}")
                        print(f"   Cookie: {data['cookie_string'][:100]}...")
                        if result.get('screenshot'):
                            print(f"   📸 Screenshot disponible (base64, {len(result['screenshot'])} chars)")
                    else:
                        print(f"❌ Error: {result['error']}")
                        if result.get('screenshot'):
                            print(f"   📸 Screenshot del error disponible")
                finally:
                    loop.close()
            elif op == '2':
                print("👋 Saliendo...")
                break
    else:
        # Modo API
        print(f"🚀 Iniciando API en {API_HOST}:{API_PORT}")
        print(f"📝 Endpoints:")
        print(f"   GET  /      - Información")
        print(f"   GET  /health - Health check")
        print(f"   POST /generate - Generar cookie")
        app.run(host=API_HOST, port=API_PORT, debug=False, threaded=True)