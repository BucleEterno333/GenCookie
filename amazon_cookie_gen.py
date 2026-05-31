#!/usr/bin/env python3
"""
Amazon Cookie Generator - Híbrido (curl_cffi + Playwright)
- Usa curl_cffi para peticiones iniciales (rápido)
- Playwright para captchas y verificación final
- Email temporal con tmailor.com
- SMS con Hero (o 5sim si se configura)
- Resolución de captchas con capsolver (WAF) y 2captcha/anticaptcha (coordenadas/funcaptcha)
"""

import os
import sys
import re
import json
import time
import random
import uuid
import asyncio
import logging
import base64
from urllib.parse import quote
from curl_cffi import requests as curl_requests
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify
from flask_cors import CORS

# ========== CONFIGURACIÓN DESDE VARIABLES DE ENTORNO ==========
API_KEY_CAPSOLVER = os.getenv('API_KEY_CAPSOLVER', '')
HERO_SMS_API_KEY = os.getenv('HERO_SMS_API_KEY', '')
FIVESIM_API_KEY = os.getenv('FIVESIM_API_KEY', '')          # opcional
PROXY_STRING = os.getenv('PROXY_STRING', '')                # opcional
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8080'))
API_KEY = os.getenv('API_KEY', '')                          # para autenticar requests

# Captcha providers (para coordenadas y FunCaptcha)
API_KEY_2CAPTCHA = os.getenv('API_KEY_2CAPTCHA', '')
API_KEY_ANTICAPTCHA = os.getenv('API_KEY_ANTICAPTCHA', '')

# Timeouts (milisegundos)
NAV_TIMEOUT = 60000
ACT_TIMEOUT = 5000
WAIT_TIMEOUT = 10000

# Configuración de captura de pantalla (calidad)
SCREENSHOT_QUALITY = 30

# ========== LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=['https://astralchk.com'], supports_credentials=True)

# ========== FUNCIONES AUXILIARES ==========
def find_between(text, start, end):
    """Extrae texto entre dos delimitadores."""
    try:
        return text.split(start, 1)[1].split(end, 1)[0].strip()
    except IndexError:
        raise ValueError(f"No se encontró '{start}' ... '{end}'")

def solve_aws_waf(capsolver_key, images, question):
    """Resuelve el captcha AWS WAF con capsolver."""
    import capsolver
    capsolver.api_key = capsolver_key
    return capsolver.solve({
        "type": "AwsWafClassification",
        "question": f"aws:grid:{question}",
        "images": images
    })

def bypass_waf(sess, captcha_url, aamation_id, client_ctx, json_opt, solver_key):
    """Bypass completo del WAF de Amazon usando capsolver."""
    for attempt in range(5):
        # Obtener el desafío
        resp = sess.get(f"{captcha_url}/problem?kind=visual&domain=www.amazon.com&locale=en-US&problem=gridcaptcha-v2-5-0.1-0&num_solutions_required=1&id={aamation_id}")
        j4 = resp.json()
        target = json.loads(j4["assets"]["target"])[0]
        images_raw = json.loads(j4["assets"]["images"])

        try:
            solved = solve_aws_waf(solver_key, images_raw, target).get("objects", [])
        except Exception as e:
            logger.warning(f"Error en capsolver: {e}")
            continue

        # Enviar solución
        payload = {
            "state": {"iv": j4["state"]["iv"], "payload": j4["state"]["payload"]},
            "key": j4["key"],
            "hmac_tag": j4["hmac_tag"],
            "client_solution": solved,
            "metrics": {"solve_time_millis": random.randint(5000, 8000)},
            "locale": "en-us"
        }
        j5 = sess.post(f"{captcha_url}/verify", json=payload).json()
        if not j5.get("captcha_voucher"):
            logger.info(f"Intento {attempt+1}/5 falló")
            continue

        captcha_jwt = j5["captcha_voucher"]
        jwt_client_id = json.loads(base64.urlsafe_b64decode(captcha_jwt.split(".")[1] + "=="))["client_id"]

        json6 = json.dumps({
            "challengeType": "WAF_ADVERSARIAL_SYNTHETIC_GRID_V2_LEVEL_1",
            "data": f'"{captcha_jwt}"'
        }, separators=(",", ":"))

        headers = sess.get(
            f"https://www.amazon.com/aaut/verify/cvf/{jwt_client_id}?context={quote(client_ctx)}&options={quote(json_opt)}&response={quote(json6)}"
        ).headers
        action_type = json.loads(headers.get("amz-aamation-resp")).get("actionType")
        logger.info(f"WAF intento {attempt+1}/5 -> actionType: {action_type}")
        if action_type == "PASS":
            return jwt_client_id

    raise Exception("WAF falló después de 5 intentos")

# ========== SERVICIOS SMS ==========
def get_sms_number(api_key):
    """Obtiene un número de teléfono de hero-sms.com (país 36 = Australia)."""
    r = curl_requests.get(f"https://hero-sms.com/stubs/handler_api.php?api_key={api_key}&action=getNumber&service=am&country=36").text
    if not r.startswith("ACCESS_NUMBER"):
        raise Exception(f"Hero-SMS error: {r}")
    _, activation_id, phone = r.split(":")
    phone = phone.strip()
    if phone.startswith("1") and len(phone) == 11:
        phone = phone[1:]   # quitar código país
    return activation_id, phone

def get_sms_code(api_key, activation_id, timeout=60):
    """Espera y obtiene el código SMS."""
    for _ in range(timeout // 5):
        time.sleep(5)
        r = curl_requests.get(f"https://hero-sms.com/stubs/handler_api.php?api_key={api_key}&action=getStatus&id={activation_id}").text
        if r.startswith("STATUS_OK"):
            return r.split(":")[1].strip()
        if r == "STATUS_CANCEL":
            raise Exception("Activación SMS cancelada")
    raise Exception("Timeout esperando código SMS")

def set_sms_status(api_key, activation_id, status):
    """Cambia el estado de la activación SMS (6 = usado, 8 = cancelar)."""
    curl_requests.get(f"https://hero-sms.com/stubs/handler_api.php?api_key={api_key}&action=setStatus&status={status}&id={activation_id}")

# ========== EMAIL TEMPORAL ==========
def create_temp_email(sess):
    """Crea un email temporal en tmailor.com."""
    resp = sess.post("https://tmailor.com/api", json={"action": "newemail", "curentToken": "", "fbToken": None})
    data = resp.json()
    return data["email"], data["accesstoken"]

def get_email_code(sess, token, timeout=60):
    """Espera y obtiene el código de verificación del email."""
    for _ in range(timeout // 3):
        time.sleep(3)
        resp = sess.post("https://tmailor.com/api", json={
            "action": "listinbox",
            "accesstoken": token,
            "fbToken": None,
            "curentToken": token
        })
        data = resp.json()
        if not data.get("data"):
            continue
        first_id = list(data["data"].keys())[0]
        node = data["data"][first_id]
        read_resp = sess.post("https://tmailor.com/api", json={
            "action": "read",
            "accesstoken": token,
            "email_code": node["id"],
            "email_token": node["email_id"],
            "fbToken": None,
            "curentToken": token
        })
        body = read_resp.json()["data"]["body"]
        match = re.search(r'class="data">(\d+)<\/span>', body)
        if match:
            return match.group(1)
    raise Exception("Timeout esperando código de email")

# ========== FUNCIONES PARA CAPTCHAS CON PLAYWRIGHT ==========
async def take_screenshot(page, step_name):
    """Captura pantalla en base64 (calidad reducida)."""
    try:
        screenshot_bytes = await page.screenshot(type='jpeg', quality=SCREENSHOT_QUALITY)
        return base64.b64encode(screenshot_bytes).decode('utf-8')
    except Exception as e:
        logger.warning(f"Error en screenshot {step_name}: {e}")
        return None

async def smart_click(page, selector, timeout=ACT_TIMEOUT, wait_for_navigation=False):
    """Clic inteligente con espera opcional de navegación."""
    try:
        element = await page.wait_for_selector(selector, state='visible', timeout=timeout)
        if wait_for_navigation:
            async with page.expect_navigation(timeout=NAV_TIMEOUT):
                await element.click()
        else:
            await element.click()
        return True
    except Exception as e:
        logger.debug(f"Clic falló en {selector}: {e}")
        return False

async def smart_fill(page, selector, value, timeout=ACT_TIMEOUT):
    """Llena un campo de texto."""
    try:
        element = await page.wait_for_selector(selector, state='visible', timeout=timeout)
        await element.fill(value)
        return True
    except Exception as e:
        logger.debug(f"Fill falló en {selector}: {e}")
        return False

async def wait_for_text(page, text, timeout=WAIT_TIMEOUT):
    """Espera que un texto aparezca en la página."""
    try:
        await page.wait_for_function(f'document.body.innerText.includes("{text}")', timeout=timeout)
        return True
    except:
        return False

async def solve_coordinate_captcha(page, round_num=1):
    """
    Resuelve captcha de coordenadas (grid 3x3) usando 8 peticiones paralelas y consenso.
    Requiere API_KEY_2CAPTCHA o API_KEY_ANTICAPTCHA.
    """
    from collections import Counter

    NUM_REQUESTS = 8
    MIN_MATCHES = 2
    TIMEOUT = 50

    logger.debug(f"Resolviendo captcha de coordenadas (ronda {round_num})")

    # Obtener canvas
    canvas = await page.wait_for_selector('canvas', timeout=20000)
    if not canvas:
        raise Exception("Canvas no encontrado")
    screenshot_bytes = await canvas.screenshot()
    img_path = f"temp_canvas_{round_num}.png"
    with open(img_path, "wb") as f:
        f.write(screenshot_bytes)
    box = await canvas.bounding_box()
    if not box or box['width'] == 0:
        raise Exception("Bounding box inválida")

    hint = "Haz clic en todas las imágenes que contengan el objeto indicado"

    def solve_one():
        # Usar anticaptcha si está disponible, si no 2captcha
        if API_KEY_ANTICAPTCHA:
            return solve_anticaptcha_coordinates(img_path, hint)
        elif API_KEY_2CAPTCHA:
            return solve_2captcha_coordinates(img_path, hint)
        else:
            return None

    def coords_to_cells(points, cell_size=105, gap=6):
        cell_total = cell_size + gap
        cells = set()
        for p in points:
            col = p['x'] // cell_total
            row = p['y'] // cell_total
            if col > 2: col = 2
            if row > 2: row = 2
            cells.add(row * 3 + col)
        return cells

    # Lanzar tareas asíncronas
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, solve_one) for _ in range(NUM_REQUESTS)]
    done, pending = await asyncio.wait(tasks, timeout=TIMEOUT, return_when=asyncio.FIRST_COMPLETED)

    valid_responses = []
    best_cells = None
    best_points = None

    for task in done:
        try:
            points = task.result()
        except Exception:
            continue
        if points and len(points) == 5:
            cells = coords_to_cells(points)
            if len(cells) == 5:
                cells_tuple = tuple(sorted(cells))
                valid_responses.append((cells_tuple, points))
                counter = Counter(cell_set for cell_set, _ in valid_responses)
                most_common, count = counter.most_common(1)[0]
                if count >= MIN_MATCHES:
                    best_cells = most_common
                    for c, pts in valid_responses:
                        if c == best_cells:
                            best_points = pts
                            break
                    break

    # Cancelar tareas pendientes
    for t in pending:
        t.cancel()

    if not best_points:
        logger.warning("No se alcanzó consenso para coordenadas")
        return False

    # Clic en las coordenadas consensuadas
    for point in best_points:
        abs_x = box['x'] + point['x']
        abs_y = box['y'] + point['y']
        await page.mouse.click(abs_x, abs_y)
        await asyncio.sleep(0.2)

    # Clic en botón Confirmar
    confirm_btn = await page.query_selector('button:has-text("Confirmar"), input[value="Confirmar"], button[type="submit"]')
    if confirm_btn:
        await confirm_btn.click()
        await page.wait_for_load_state('domcontentloaded', timeout=10000)
        return True
    else:
        logger.warning("No se encontró botón Confirmar, asumiendo éxito")
        return True

def solve_2captcha_coordinates(image_path, hint):
    """Resuelve captcha de coordenadas usando 2captcha API HTTP."""
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
        resp = curl_requests.post(url, data=data, timeout=60)
        if resp.status_code != 200:
            return None
        result = resp.json()
        if result.get('status') != 1:
            return None
        captcha_id = result['request']
        start = time.time()
        while time.time() - start < 120:
            time.sleep(5)
            res = curl_requests.get(f"http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={captcha_id}&json=1", timeout=10)
            if res.status_code != 200:
                continue
            res_data = res.json()
            if res_data.get('status') == 1:
                coord_data = res_data['request']
                points = []
                if isinstance(coord_data, str):
                    for pair in coord_data.split(';'):
                        if pair:
                            x, y = pair.split(',')
                            points.append({'x': int(x), 'y': int(y)})
                elif isinstance(coord_data, list):
                    for item in coord_data:
                        if isinstance(item, dict):
                            points.append({'x': int(item['x']), 'y': int(item['y'])})
                        elif isinstance(item, list) and len(item) == 2:
                            points.append({'x': int(item[0]), 'y': int(item[1])})
                return points
            elif res_data.get('request') == 'CAPCHA_NOT_READY':
                continue
            else:
                break
    except Exception as e:
        logger.warning(f"2captcha error: {e}")
    return None

def solve_anticaptcha_coordinates(image_path, hint):
    """Resuelve captcha de coordenadas usando Anti-Captcha API HTTP."""
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
        resp = curl_requests.post(url, json=data, timeout=30)
        if resp.status_code != 200:
            return None
        result = resp.json()
        if result.get('errorId') != 0:
            return None
        task_id = result['taskId']
        start = time.time()
        while time.time() - start < 120:
            time.sleep(5)
            res = curl_requests.post("https://api.anti-captcha.com/getTaskResult", json={"clientKey": API_KEY_ANTICAPTCHA, "taskId": task_id}, timeout=10)
            if res.status_code != 200:
                continue
            res_data = res.json()
            if res_data.get('status') == 'ready':
                coords = res_data['solution'].get('coordinates')
                if not coords:
                    return None
                points = []
                if isinstance(coords, list):
                    for item in coords:
                        if isinstance(item, dict):
                            points.append({'x': int(item['x']), 'y': int(item['y'])})
                        elif isinstance(item, list) and len(item) == 2:
                            points.append({'x': int(item[0]), 'y': int(item[1])})
                elif isinstance(coords, str):
                    for pair in coords.split(';'):
                        if pair:
                            x, y = pair.split(',')
                            points.append({'x': int(x), 'y': int(y)})
                return points
            elif res_data.get('status') == 'processing':
                continue
            else:
                break
    except Exception as e:
        logger.warning(f"anticaptcha error: {e}")
    return None

async def solve_funcaptcha(page, site_key, surl=None):
    """Resuelve FunCaptcha usando 2captcha o anticaptcha."""
    if API_KEY_2CAPTCHA:
        token = await solve_funcaptcha_2captcha(page.url, site_key, surl)
        if token:
            return token
    if API_KEY_ANTICAPTCHA:
        token = await solve_funcaptcha_anticaptcha(page.url, site_key, surl)
        if token:
            return token
    return None

async def solve_funcaptcha_2captcha(page_url, site_key, surl=None):
    """Resuelve FunCaptcha con 2captcha (HTTP)."""
    data = {
        'key': API_KEY_2CAPTCHA,
        'method': 'funcaptcha',
        'publickey': site_key,
        'pageurl': page_url,
        'json': 1
    }
    if surl:
        data['surl'] = surl
    try:
        resp = curl_requests.post('http://2captcha.com/in.php', data=data, timeout=30)
        result = resp.json()
        if result.get('status') != 1:
            return None
        captcha_id = result['request']
        start = time.time()
        while time.time() - start < 120:
            await asyncio.sleep(5)
            res = curl_requests.get(f'http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={captcha_id}&json=1', timeout=10)
            if res.status_code != 200:
                continue
            res_data = res.json()
            if res_data.get('status') == 1:
                return res_data['request']
            elif res_data.get('request') == 'CAPCHA_NOT_READY':
                continue
            else:
                break
    except Exception as e:
        logger.warning(f"2captcha FunCaptcha error: {e}")
    return None

async def solve_funcaptcha_anticaptcha(page_url, site_key, surl=None):
    """Resuelve FunCaptcha con anticaptcha (usando su librería)."""
    try:
        from anticaptchaofficial.funcaptchaproxyless import FunCaptchaTaskProxyless
        solver = FunCaptchaTaskProxyless()
        solver.set_verbose(0)
        solver.set_key(API_KEY_ANTICAPTCHA)
        solver.set_website_url(page_url)
        solver.set_website_key(site_key)
        if surl:
            solver.set_data('surl', surl)
        loop = asyncio.get_event_loop()
        token = await loop.run_in_executor(None, solver.solve_and_return_solution)
        return token if token else None
    except ImportError:
        logger.warning("anticaptchaofficial no instalada, omitiendo")
        return None

async def handle_captcha_if_present(page, step_name="captcha"):
    """Detecta y resuelve captchas de Amazon (coordenadas o FunCaptcha)."""
    logger.debug(f"Verificando captcha en paso: {step_name}")
    await page.wait_for_timeout(3000)
    content = await page.content()

    # Captcha de coordenadas
    if any(indicator in content for indicator in ["Resuelve esta adivinanza", "Selecciona todas las imágenes"]):
        logger.warning("Captcha de coordenadas detectado")
        max_attempts = 5
        for att in range(1, max_attempts+1):
            success = await solve_coordinate_captcha(page, att)
            if success:
                # Esperar a que cambie la página o aparezca el siguiente paso
                await page.wait_for_timeout(3000)
                if await page.query_selector('#cvf-input-code, #ap_customer_name'):
                    logger.debug("Captcha de coordenadas resuelto")
                    return True
            else:
                # Refrescar canvas
                refresh_btn = await page.query_selector('button:has-text("Obtenga un nuevo rompecabezas"), button:has-text("New puzzle")')
                if refresh_btn:
                    await refresh_btn.click()
                    await page.wait_for_timeout(2000)
        raise Exception("No se pudo resolver captcha de coordenadas")

    # FunCaptcha
    title = await page.title()
    if "Confirma tu identidad" in title or "Verify your identity" in title:
        logger.debug("Página de FunCaptcha detectada")
        # Extraer site_key
        iframe = await page.query_selector('#cvf-aamation-challenge-iframe')
        site_key = None
        surl = None
        if iframe:
            src = await iframe.get_attribute('src')
            if src:
                match = re.search(r'[?&]pk=([A-Za-z0-9]{20,})', src)
                if match:
                    site_key = match.group(1)
                surl_match = re.search(r'surl=([^&]+)', src)
                if surl_match:
                    surl = surl_match.group(1)
        if not site_key:
            page_content = await page.content()
            match = re.search(r'"data-external-id":\s*"([^"]+)"', page_content)
            if match:
                site_key = match.group(1)
        if site_key:
            token = await solve_funcaptcha(page, site_key, surl)
            if token:
                await page.evaluate(f"""
                    document.getElementById('cvf_aamation_response_token').value = '{token}';
                    document.getElementById('cvf-aamation-challenge-form').submit();
                """)
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                return True
        raise Exception("No se pudo resolver FunCaptcha")
    return False

# ========== FLUJO PRINCIPAL HÍBRIDO ==========
async def generate_account(country_code, add_address=True, max_retries=3):
    """Crea cuenta de Amazon usando curl_cffi + Playwright."""
    for attempt in range(1, max_retries+1):
        logger.info(f"Intento {attempt}/{max_retries}")
        sess = None
        playwright = None
        browser = None
        context = None
        page = None
        activation_id = None

        try:
            # ---- 1. Configurar sesión curl_cffi ----
            sess = curl_requests.Session(impersonate="chrome")
            if PROXY_STRING:
                sess.proxies = {"http": f"http://{PROXY_STRING}", "https": f"http://{PROXY_STRING}"}

            # ---- 2. Email temporal ----
            email, mail_token = create_temp_email(sess)
            logger.info(f"Email: {email}")

            # ---- 3. Perfil y credenciales ----
            first = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            last = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=5)).capitalize()
            fullname = f"{first} {last}"
            password = f"Pass{random.randint(1000,9999)}{uuid.uuid4().hex[:8]}"
            arb = "88b7dd8f-6e15-491a-87df-9351dcbfc80f"
            assoc_handle = "anywhere_v2_us"
            base_openid = {
                "forceMobileLayout": "1",
                "openid.assoc_handle": assoc_handle,
                "openid.mode": "checkid_setup",
                "language": "en_US",
                "openid.ns": "http://specs.openid.net/auth/2.0",
                "shouldShowPersistentLabels": "true"
            }

            # ---- 4. Registro inicial con curl ----
            sess.get(f"https://www.amazon.com/ax/claim?arb={arb}")
            data1 = {
                "arb": arb,
                "email": email,
                "claimCollectionLayoutType": "unifiedAuthClaimCollection",
            }
            url_register = "https://www.amazon.com/ap/register?openid.mode=checkid_setup&openid.ns=http://specs.openid.net/auth/2.0&openid.identity=http://specs.openid.net/auth/2.0/identifier_select&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select&openid.assoc_handle=anywhere_v2_us&openid.return_to=https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button"
            r1 = sess.post(url_register, data=data1)
            if "already an account" in r1.text:
                raise Exception("Email ya registrado")

            appActionToken = find_between(r1.text, 'name="appActionToken" value="', '"')
            workflowState = find_between(r1.text, 'name="workflowState" value="', '"')
            openid_return_to = find_between(r1.text, 'name="openid.return_to" value="', '"')
            prevRID = find_between(r1.text, 'name="prevRID" value="', '"')

            data2 = {
                "appActionToken": appActionToken,
                "appAction": "REGISTER",
                "shouldShowPersistentLabels": "true",
                "openid.return_to": openid_return_to,
                "prevRID": prevRID,
                "workflowState": workflowState,
                "customerName": fullname,
                "email": email,
                "password": password,
                "showPasswordChecked": "true"
            }
            r2 = sess.post("https://www.amazon.com/ap/register", data=data2)
            if "detected unusual activity" in r2.text:
                raise Exception("Actividad inusual detectada")

            # ---- 5. Manejar WAF si aparece ----
            verifyToken = None
            if "data-context" in r2.text and "data-external-id" in r2.text:
                verifyToken = find_between(r2.text, 'name="verifyToken" value="', '"')
                data_external_id = re.search(r'"data-external-id":\s*"([^"]+)"', r2.text).group(1)
                anti_csrf = find_between(r2.text, "name='anti-csrftoken-a2z' value='", "'")

                json3 = json.dumps({
                    "clientData": json.dumps({
                        "sessionId": sess.cookies.get("session-id", ""),
                        "marketplaceId": "ATVPDKIKX0DER",
                        "clientUseCase": "/ap/register"
                    }, separators=(",", ":")),
                    "challengeType": "WAF_ADVERSARIAL_SYNTHETIC_GRID_V2_LEVEL_1",
                    "locale": "en-US",
                    "externalId": data_external_id,
                    "enableHeaderFooter": False,
                    "enableBypassMechanism": False,
                    "enableModalView": False,
                    "eventTrigger": None,
                    "aaExternalToken": None,
                    "forceJsFlush": False,
                    "aamationToken": None,
                }, separators=(",", ":"))

                r3 = sess.get(f"https://www.amazon.com/aaut/verify/cvf?options={quote(json3)}")
                client_ctx = json.loads(r3.headers.get("amz-aamation-resp")).get("clientSideContext")
                aamation_id = re.search(r'"id"\s*:\s*"([^"]+)"', r3.text).group(1)
                captcha_url = re.search(r'<script src="(https://ait\.[^"]+)/captcha\.js"', r3.text).group(1)

                jwt_client_id = bypass_waf(sess, captcha_url, aamation_id, client_ctx, json3, API_KEY_CAPSOLVER)

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
                r4 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data4)
                verifyToken = find_between(r4.text, 'name="verifyToken" value="', '"')

            # ---- 6. Verificación por email (OTP) ----
            otp_code = get_email_code(sess, mail_token)
            logger.info(f"Código email: {otp_code}")

            data5 = {**base_openid,
                     "autoReadStatus": "manual",
                     "verificationPageContactType": "email",
                     "action": "code",
                     "verifyToken": verifyToken,
                     "code": otp_code}
            r5 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data5)
            anti_csrf = find_between(r5.text, "name='anti-csrftoken-a2z' value='", "'")
            verifyToken = find_between(r5.text, 'name="verifyToken" value="', '"')

            # ---- 7. Obtener número SMS ----
            activation_id, sms_phone = get_sms_number(HERO_SMS_API_KEY)
            logger.info(f"Número SMS: +{sms_phone}")

            data6 = {**base_openid,
                     "anti-csrftoken-a2z": anti_csrf,
                     "verifyToken": verifyToken,
                     "cvf_phone_cc": "CA",
                     "cvf_phone_num": sms_phone,
                     "cvf_action": "collect"}
            r6 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data6)

            # ---- 8. Iniciar Playwright para el resto del flujo ----
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36"
            )
            # Transferir cookies de la sesión curl
            for name, value in sess.cookies.items():
                await context.add_cookies([{'name': name, 'value': value, 'domain': '.amazon.com', 'path': '/'}])
            page = await context.new_page()

            # Navegar a la página de verificación SMS
            await page.goto(r6.url, wait_until='domcontentloaded')
            await page.wait_for_timeout(3000)

            # Resolver posibles captchas antes de pedir SMS
            await handle_captcha_if_present(page, "pre_sms")

            # ---- 9. Esperar código SMS y enviarlo ----
            sms_code = get_sms_code(HERO_SMS_API_KEY, activation_id, timeout=90)
            logger.info(f"Código SMS: {sms_code}")
            set_sms_status(HERO_SMS_API_KEY, activation_id, 6)  # usado

            # Rellenar código
            code_input = await page.wait_for_selector('#cvf-input-code', timeout=30000)
            await code_input.fill(sms_code)
            await smart_click(page, 'input[type="submit"]', wait_for_navigation=True)

            # ---- 10. Verificar éxito y obtener cookies ----
            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            if 'your-account' in page.url.lower() or 'account' in page.url.lower():
                cookies = await context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])

                # ---- 11. Agregar dirección (opcional) ----
                address_status = "No agregada"
                if add_address:
                    try:
                        # Ir a agregar dirección
                        await page.goto("https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button", wait_until='domcontentloaded')
                        await page.wait_for_selector('#address-ui-widgets-enterAddressLine1', timeout=15000)
                        # Datos ficticios
                        street = f"{random.randint(100,999)} Broadway"
                        city = "New York"
                        state = "NY"
                        zipcode = "10001"
                        phone = f"212555{random.randint(1000,9999)}"
                        await smart_fill(page, '#address-ui-widgets-enterAddressFullName', fullname)
                        await smart_fill(page, '#address-ui-widgets-enterAddressLine1', street)
                        await smart_fill(page, '#address-ui-widgets-enterAddressCity', city)
                        # Seleccionar estado (dropdown)
                        state_dropdown = await page.wait_for_selector('#address-ui-widgets-enterAddressStateOrRegion', timeout=5000)
                        await state_dropdown.click()
                        await page.keyboard.type(state)
                        await page.wait_for_timeout(500)
                        await page.keyboard.press('Enter')
                        await smart_fill(page, '#address-ui-widgets-enterAddressPostalCode', zipcode)
                        await smart_fill(page, '#address-ui-widgets-enterAddressPhoneNumber', phone)
                        # Enviar
                        submit_btn = await page.query_selector('input[value="Agregar dirección"], input[value="Add address"]')
                        if submit_btn:
                            await submit_btn.click()
                            await page.wait_for_timeout(3000)
                            address_status = "Agregada"
                    except Exception as e:
                        logger.warning(f"Error agregando dirección: {e}")
                        address_status = f"Error: {e}"

                return {
                    "success": True,
                    "data": {
                        "email": email,
                        "password": password,
                        "phone": sms_phone,
                        "name": fullname,
                        "cookie_string": cookie_string,
                        "address": address_status,
                        "country": country_code
                    }
                }
            else:
                raise Exception("No se llegó a la página de cuenta")

        except Exception as e:
            logger.error(f"Error en intento {attempt}: {e}")
            if activation_id:
                try:
                    set_sms_status(HERO_SMS_API_KEY, activation_id, 8)  # cancelar
                except:
                    pass
            if attempt == max_retries:
                return {"success": False, "error": str(e)}
            await asyncio.sleep(5)
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            if sess:
                sess.close()

    return {"success": False, "error": "Max retries exceeded"}

# ========== API FLASK ==========
@app.route('/health', methods=['GET', 'OPTIONS'])
def health():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({"status": "ok", "timestamp": time.time()})

@app.route('/generate', methods=['POST', 'OPTIONS'])
def generate():
    if request.method == 'OPTIONS':
        return '', 200
    # Autenticación opcional
    auth_header = request.headers.get('Authorization', '')
    if API_KEY and auth_header != f'Bearer {API_KEY}':
        return jsonify({"success": False, "error": "No autorizado"}), 401

    data = request.get_json() or {}
    country = data.get('country', 'US').upper()
    add_address = data.get('add_address', True)
    max_retries = data.get('max_retries', 3)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(generate_account(country, add_address, max_retries))
    loop.close()
    return jsonify(result)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'service': 'Amazon Cookie Generator (Hybrid)',
        'endpoints': ['/health', '/generate']
    })

if __name__ == '__main__':
    # Verificar dependencias mínimas
    if not API_KEY_CAPSOLVER:
        logger.error("Falta API_KEY_CAPSOLVER en variables de entorno")
        sys.exit(1)
    if not HERO_SMS_API_KEY:
        logger.error("Falta HERO_SMS_API_KEY en variables de entorno")
        sys.exit(1)
    logger.info(f"Iniciando API en {API_HOST}:{API_PORT}")
    app.run(host=API_HOST, port=API_PORT, threaded=True)