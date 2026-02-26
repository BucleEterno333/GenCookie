#!/usr/bin/env python3
"""
Amazon Cookie Generator - Versión API REST
- Mantiene toda la funcionalidad original
- Configuración mediante variables de entorno
- 2captcha con fallback a anticaptcha
- Integración con Hero SMS para verificación telefónica
- AHORA: Modo API con soporte para peticiones JSON
- AHORA: Control de agregar dirección desde el frontend
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
# CREACIÓN DE CUENTA PRINCIPAL
# -------------------------------------------------------------------
async def create_amazon_account(domain, email=None, token=None, service=None, add_address_flag=True):
    """
    Crea una cuenta de Amazon y retorna los datos de la cuenta.
    """
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

    try:
        session = requests.Session()
        if PROXY_HOST_PORT:
            proxy_url = f"http://{PROXY_HOST_PORT}"
            if PROXY_AUTH:
                proxy_url = f"http://{PROXY_AUTH}@{PROXY_HOST_PORT}"
            session.proxies = {'http': proxy_url, 'https': proxy_url}

        ok, msg = test_proxy(session)
        if not ok:
            return None

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

        browser = await playwright.chromium.launch(**launch_options)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=random.choice(USER_AGENTS)
        )
        page = await context.new_page()

        await page.goto(register_urls[domain], wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(3000)

        # Llenar formulario
        try:
            await page.wait_for_selector('input[name="customerName"]', timeout=5000)
            await page.fill('input[name="customerName"]', fullname)
        except:
            pass

        try:
            await page.fill('input[name="email"]', email)
        except:
            try:
                await page.fill('input[type="email"]', email)
            except:
                return None

        try:
            await page.fill('input[name="password"]', password)
        except:
            try:
                await page.fill('input[type="password"]', password)
            except:
                return None

        try:
            await page.wait_for_selector('input[name="passwordCheck"]', timeout=2000)
            await page.fill('input[name="passwordCheck"]', password)
        except:
            pass

        request_id = None
        if domain == 'amazon.com':
            phone_number = None
            if HERO_SMS_API_KEY:
                phone_info = await get_hero_sms_number()
                if phone_info:
                    phone_number, request_id = phone_info
                else:
                    phone_number = f"+1{random.randint(200,999)}{random.randint(1000000,9999999)}"
            else:
                phone_number = f"+1{random.randint(200,999)}{random.randint(1000000,9999999)}"

            try:
                await page.wait_for_selector('input[name="phoneNumber"]', timeout=5000)
                await page.fill('input[name="phoneNumber"]', phone_number)
                account_data['phone'] = phone_number
            except:
                try:
                    await page.fill('input[type="tel"]', phone_number)
                    account_data['phone'] = phone_number
                except:
                    pass

        try:
            await page.click('input[type="submit"], button[type="submit"], #continue')
        except Exception:
            return None

        await page.wait_for_load_state('networkidle', timeout=30000)

        current_url = page.url
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')

        error_div = soup.find('div', {'class': re.compile('a-alert-error|a-alert-warning|a-box-error', re.I)})
        if error_div:
            return None

        if 'verification' in current_url.lower() or 'cvf' in current_url.lower():
            if domain == 'amazon.com' and request_id:
                code = await get_hero_sms_code(request_id)
                if code:
                    try:
                        await page.fill('input[name="code"]', code)
                        await page.click('button[type="submit"]')
                        await page.wait_for_load_state('networkidle', timeout=15000)
                    except:
                        return None
                else:
                    return None
            else:
                code = await get_verification_code(email, token, service)
                if code:
                    try:
                        await page.fill('input[name="code"]', code)
                        await page.click('button[type="submit"]')
                        await page.wait_for_load_state('networkidle', timeout=15000)
                    except:
                        return None
                else:
                    return None

        if 'your-account' in page.url.lower() or 'account' in page.url.lower():
            cookies = await context.cookies()
            cookie_dict = {c['name']: c['value'] for c in cookies}
            cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
            
            account_data['cookie_dict'] = cookie_dict
            account_data['cookie_string'] = cookie_string

            for name, value in cookie_dict.items():
                session.cookies.set(name, value, domain=f".{domain}")

            if add_address_flag:
                addr_ok = await add_address(session, domain, email, password, token, service)
                account_data['address'] = "Dirección agregada" if addr_ok else "Error al agregar dirección"
            else:
                account_data['address'] = "No se agregó dirección"

            try:
                await page.goto(wallet_urls[domain], wait_until='networkidle', timeout=20000)
                await page.wait_for_timeout(3000)
                cookies = await context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])
                account_data['cookie_dict'] = cookie_dict
                account_data['cookie_string'] = cookie_string
            except Exception:
                pass

            return account_data
        else:
            return None

    except Exception as e:
        logger.exception("Error en create_amazon_account")
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
# FUNCIÓN PARA API
# -------------------------------------------------------------------
async def generate_cookie_api(country, add_address=True):
    """
    Función para ser llamada desde la API.
    """
    try:
        if country not in country_to_domain:
            return {
                'success': False,
                'error': f'País no soportado: {country}',
                'country': country
            }
        
        domain = country_to_domain[country]
        account_data = await create_amazon_account(domain, add_address_flag=add_address)
        
        if account_data:
            return {
                'success': True,
                'data': account_data,
                'country': country
            }
        else:
            return {
                'success': False,
                'error': f'No se pudo generar cookie para {country}',
                'country': country
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'country': country
        }

# -------------------------------------------------------------------
# API FLASK
# -------------------------------------------------------------------
app = Flask(__name__)
CORS(app)  # Permitir CORS para peticiones desde el frontend

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

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'proxy': 'configured' if PROXY_HOST_PORT else 'not configured',
        'captcha': API_KEY_2CAPTCHA or API_KEY_ANTICAPTCHA
    })

@app.route('/generate', methods=['POST'])
def generate():
    """
    Endpoint para generar cookie.
    Espera JSON: {"country": "US", "add_address": true}
    """
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
    
    # Ejecutar la generación de cookie en un bucle asyncio nuevo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(generate_cookie_api(country, add_address))
        return jsonify(result)
    finally:
        loop.close()

# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='API de generador de cookies Amazon')
    parser.add_argument('--cli', action='store_true', help='Ejecutar en modo CLI (menú interactivo)')
    args = parser.parse_args()

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
                    else:
                        print(f"❌ Error: {result['error']}")
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