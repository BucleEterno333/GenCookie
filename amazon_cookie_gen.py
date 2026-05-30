#!/usr/bin/env python3
"""
Amazon Account Generator - API ligera (capsolver + tmailor + hero-sms)
- Sin Playwright, solo requests/curl_cffi
- Resuelve WAF de Amazon con capsolver
- Email temporal con tmailor.com
- SMS temporal con hero-sms.com
- Proxy opcional (formato user:pass@host:port o ip:port)
"""

import os
import re
import json
import time
import base64
import random
import logging
from urllib.parse import quote, urlparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from curl_cffi import requests
from faker import Faker

# ========== CONFIGURACIÓN ==========
API_KEY_CAPSOLVER = os.getenv('API_KEY_CAPSOLVER', '')
HERO_SMS_API_KEY = os.getenv('HERO_SMS_API_KEY', '')
PROXY_STRING = os.getenv('PROXY_STRING', '')   # opcional
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '5000'))

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=['https://tu-frontend.com'], methods=['POST', 'OPTIONS'])

# ========== CONSTANTES ==========
MAIL_API = "https://tmailor.com/api"
SMS_API = "https://hero-sms.com/stubs/handler_api.php"

def find_between(text: str, start: str, end: str) -> str:
    """Extrae texto entre dos delimitadores."""
    try:
        return text.split(start, 1)[1].split(end, 1)[0].strip()
    except IndexError:
        raise ValueError(f"No se encontró '{start}' ... '{end}'")

def solve_aws_waf(capsolver_key: str, images: list, question: str) -> dict:
    """Resuelve el captcha de tipo AWS WAF con capsolver."""
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

def get_sms_number(api_key: str) -> tuple:
    """Obtiene un número de teléfono de hero-sms.com para el servicio Amazon (código de país 36 = Australia)."""
    r = requests.get(f"{SMS_API}?api_key={api_key}&action=getNumber&service=am&country=36").text
    if not r.startswith("ACCESS_NUMBER"):
        raise Exception(f"Hero-SMS error: {r}")
    _, activation_id, phone = r.split(":")
    phone = phone.strip()
    if phone.startswith("1") and len(phone) == 11:
        phone = phone[1:]   # quitar código país si es de 11 dígitos
    return activation_id, phone

def get_sms_code(api_key: str, activation_id: str, timeout: int = 60) -> str:
    """Espera y obtiene el código SMS."""
    for _ in range(timeout // 5):
        time.sleep(5)
        r = requests.get(f"{SMS_API}?api_key={api_key}&action=getStatus&id={activation_id}").text
        if r.startswith("STATUS_OK"):
            return r.split(":")[1].strip()
        if r == "STATUS_CANCEL":
            raise Exception("Activación SMS cancelada")
    raise Exception("Timeout esperando código SMS")

def set_sms_status(api_key: str, activation_id: str, status: int):
    """Cambia el estado de la activación SMS (6 = usado, 8 = cancelar)."""
    requests.get(f"{SMS_API}?api_key={api_key}&action=setStatus&status={status}&id={activation_id}")

def create_temp_email(sess) -> tuple:
    """Crea un email temporal en tmailor.com."""
    resp = sess.post(MAIL_API, json={"action": "newemail", "curentToken": "", "fbToken": None})
    data = resp.json()
    return data["email"], data["accesstoken"]

def get_email_code(sess, token: str, timeout: int = 60) -> str:
    """Espera y obtiene el código de verificación del email."""
    for _ in range(timeout // 3):
        time.sleep(3)
        resp = sess.post(MAIL_API, json={
            "action": "listinbox",
            "accesstoken": token,
            "fbToken": None,
            "curentToken": token
        })
        data = resp.json()
        if not data.get("data"):
            continue
        # Tomar el primer mensaje
        first_id = list(data["data"].keys())[0]
        node = data["data"][first_id]
        # Leer el cuerpo
        read_resp = sess.post(MAIL_API, json={
            "action": "read",
            "accesstoken": token,
            "email_code": node["id"],
            "email_token": node["email_id"],
            "fbToken": None,
            "curentToken": token
        })
        body = read_resp.json()["data"]["body"]
        # Extraer el código OTP (formato típico: <span class="data">123456</span>)
        match = re.search(r'class="data">(\d+)<\/span>', body)
        if match:
            return match.group(1)
        raise Exception("Código OTP no encontrado en el email")
    raise Exception("Timeout esperando código de email")

def generate_profile() -> dict:
    """Genera un perfil falso para la dirección de envío."""
    fake = Faker("en_US")
    first = fake.first_name()
    last = fake.last_name()
    # Lista de ciudades/estados comunes
    locations = [
        {"street": "Broadway", "city": "Los Angeles", "state": "CA", "zip": "90001", "area": "213"},
        {"street": "Michigan Ave", "city": "Detroit", "state": "MI", "zip": "48226", "area": "313"},
        {"street": "Collins Ave", "city": "Denver", "state": "CO", "zip": "80202", "area": "303"},
        {"street": "Congress Ave", "city": "Austin", "state": "TX", "zip": "78701", "area": "512"},
        {"street": "Las Vegas Blvd", "city": "Las Vegas", "state": "NV", "zip": "89101", "area": "702"},
    ]
    loc = random.choice(locations)
    return {
        "first_name": first,
        "last_name": last,
        "full_name": f"{first} {last}",
        "phone": f"{loc['area']}555{random.randint(1000, 9999)}",
        "street": f"{random.randint(100, 999)} {loc['street']}",
        "city": loc["city"],
        "state": loc["state"],
        "zip": loc["zip"],
        "user_agent": f"Mozilla/5.0 (Linux; Android {random.randint(10, 14)}; {random.choice(['Pixel 8', 'SM-S918B'])}) AppleWebKit/537.36 Chrome/{random.randint(120, 135)}.0.0.0 Mobile Safari/537.36"
    }

# ========== FLUJO PRINCIPAL ==========
def generate_account(capsolver_key: str, hero_key: str, proxy: str = None, email: str = None, mail_token: str = None) -> dict:
    """
    Crea una cuenta de Amazon y devuelve cookies y datos.
    """
    start_time = time.time()
    sess = None
    activation_id = None
    sms_phone = None

    try:
        # Configurar sesión con curl_cffi (emula Chrome real)
        sess = requests.Session(impersonate="chrome")
        if proxy:
            sess.proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}

        # 1. Obtener email temporal si no se proporcionó
        if not email:
            email, mail_token = create_temp_email(sess)
        logger.info(f"Email usado: {email}")

        # 2. Perfil de usuario
        profile = generate_profile()
        password = "Pass123!" + str(random.randint(1000, 9999))
        assoc_handle = "anywhere_v2_us"
        arb = "88b7dd8f-6e15-491a-87df-9351dcbfc80f"  # fijo pero puede cambiarse

        # 3. Iniciar el proceso de registro
        sess.get(f"https://www.amazon.com/ax/claim?arb={arb}")

        data1 = {
            "arb": arb,
            "email": email,
            "claimCollectionLayoutType": "unifiedAuthClaimCollection",
        }
        url_register = "https://www.amazon.com/ap/register?openid.mode=checkid_setup&openid.ns=http://specs.openid.net/auth/2.0&openid.identity=http://specs.openid.net/auth/2.0/identifier_select&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select&openid.assoc_handle=anywhere_v2_us&openid.return_to=https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button"
        r1 = sess.post(url_register, data=data1)
        if "already an account" in r1.text:
            raise Exception("El email ya está registrado")

        # Extraer tokens
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
            "customerName": profile["full_name"],
            "email": email,
            "password": password,
            "showPasswordChecked": "true"
        }
        r2 = sess.post("https://www.amazon.com/ap/register", data=data2)

        # Verificar si pide captcha WAF
        if "detected unusual activity" in r2.text:
            raise Exception("Actividad inusual detectada, no se puede continuar")

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

            jwt_client_id = bypass_waf(sess, captcha_url, aamation_id, client_ctx, json3, capsolver_key)

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

        # 4. Verificación por email
        otp_code = get_email_code(sess, mail_token)
        logger.info(f"Código de email: {otp_code}")

        base_openid = {
            "forceMobileLayout": "1",
            "openid.assoc_handle": assoc_handle,
            "openid.mode": "checkid_setup",
            "language": "en_US",
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "shouldShowPersistentLabels": "true"
        }
        data5 = {**base_openid,
                 "autoReadStatus": "manual",
                 "verificationPageContactType": "email",
                 "action": "code",
                 "verifyToken": verifyToken,
                 "code": otp_code}
        r5 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data5)
        anti_csrf = find_between(r5.text, "name='anti-csrftoken-a2z' value='", "'")
        verifyToken = find_between(r5.text, 'name="verifyToken" value="', '"')

        # 5. Obtener número SMS
        activation_id, sms_phone = get_sms_number(hero_key)
        logger.info(f"Número SMS obtenido: +{sms_phone}")

        data6 = {**base_openid,
                 "anti-csrftoken-a2z": anti_csrf,
                 "verifyToken": verifyToken,
                 "cvf_phone_cc": "CA",
                 "cvf_phone_num": sms_phone,
                 "cvf_action": "collect"}
        r6 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data6)

        # Esperar código SMS
        sms_code = get_sms_code(hero_key, activation_id)
        logger.info(f"Código SMS: {sms_code}")
        set_sms_status(hero_key, activation_id, 6)  # marcar como usado

        anti_csrf = find_between(r6.text, "name='anti-csrftoken-a2z' value='", "'")
        verifyToken = find_between(r6.text, 'name="verifyToken" value="', '"')
        data7 = {**base_openid,
                 "anti-csrftoken-a2z": anti_csrf,
                 "verificationPageContactType": "sms",
                 "verifyToken": verifyToken,
                 "code": sms_code,
                 "cvf_action": "code",
                 "resendContactType": "sms"}
        r7 = sess.post("https://www.amazon.com/ap/cvf/verify", data=data7)

        if "new_account=1" not in r7.url:
            raise Exception("La cuenta no se creó correctamente")

        # 6. Agregar dirección de envío (opcional, pero recomendado)
        csrf_addr = quote(find_between(r7.text, "name='csrfToken' value='", "'"))
        customer_id = find_between(r7.text, 'name="address-ui-widgets-obfuscated-customerId" value="', '"')
        wizard_id = find_between(r7.text, 'name="address-ui-widgets-address-wizard-interaction-id" value="', '"')
        prev_token = find_between(r7.text, 'name="address-ui-widgets-previous-address-form-state-token" value="', '"')
        widget_csrf = quote(find_between(r7.text, 'name="address-ui-widgets-csrfToken" value="', '"'))
        form_load = find_between(r7.text, 'name="address-ui-widgets-form-load-start-time" value="', '"')

        address_payload = (
            f"csrfToken={csrf_addr}&addressID=&address-ui-widgets-addressFormButtonText=save"
            f"&address-ui-widgets-addressFormHideHeading=true&address-ui-widgets-addressFormHideSubmitButton=false"
            f"&address-ui-widgets-enableAddressDetails=true&address-ui-widgets-enableAddressWizardForm=true"
            f"&address-ui-widgets-address-wizard-interaction-id={wizard_id}"
            f"&address-ui-widgets-obfuscated-customerId={customer_id}"
            f"&address-ui-widgets-csrfToken={widget_csrf}"
            f"&address-ui-widgets-form-load-start-time={form_load}"
            f"&address-ui-widgets-isAddressSuggestionsView=true&address-ui-widgets-suggested-address-selection=original-address-"
            f"&original-address-address-ui-widgets-enterAddressFullName={quote(profile['full_name'])}"
            f"&original-address-address-ui-widgets-enterAddressLine1={quote(profile['street'])}"
            f"&original-address-address-ui-widgets-enterAddressLine2="
            f"&original-address-address-ui-widgets-enterAddressCity={quote(profile['city'])}"
            f"&original-address-address-ui-widgets-enterAddressStateOrRegion={profile['state']}"
            f"&original-address-address-ui-widgets-enterAddressPostalCode={profile['zip']}"
            f"&original-address-address-ui-widgets-countryCode=US"
            f"&original-address-address-ui-widgets-enterAddressPhoneNumber={profile['phone']}"
            f"&address-ui-widgets-use-as-my-default=true"
            f"&address-ui-widgets-previous-address-form-state-token={prev_token}"
            f"&address-ui-widgets-saveOriginalOrSuggestedAddress=Submit+Query"
        )
        sess.post("https://www.amazon.com/a/addresses/add?ref=ya_address_book_add_button", data=address_payload)

        # 7. Extraer cookies formateadas
        cookie_str = "; ".join(f"{k}={v}" for k, v in sess.cookies.items())
        elapsed = round(time.time() - start_time, 2)

        return {
            "success": True,
            "data": {
                "email": email,
                "password": password,
                "phone": sms_phone,
                "name": profile["full_name"],
                "cookie_string": cookie_str,
                "time_seconds": elapsed
            }
        }

    except Exception as e:
        # Cancelar SMS si hubo error
        if activation_id:
            try:
                set_sms_status(hero_key, activation_id, 8)  # cancelar
            except:
                pass
        elapsed = round(time.time() - start_time, 2)
        return {
            "success": False,
            "error": str(e),
            "time_seconds": elapsed
        }
    finally:
        if sess:
            sess.close()

# ========== ENDPOINT API ==========
@app.route('/generate', methods=['POST', 'OPTIONS'])
def api_generate():
    if request.method == 'OPTIONS':
        return '', 200

    # Autenticación simple (opcional)
    auth_header = request.headers.get('Authorization', '')
    expected_key = os.getenv('API_KEY', '')
    if expected_key and auth_header != f'Bearer {expected_key}':
        return jsonify({"success": False, "error": "No autorizado"}), 401

    data = request.get_json() or {}
    proxy = data.get('proxy') or PROXY_STRING
    email = data.get('email')   # opcional, si ya tienes un email temporal
    mail_token = data.get('mail_token')

    if not API_KEY_CAPSOLVER:
        return jsonify({"success": False, "error": "Falta API_KEY_CAPSOLVER en entorno"}), 500
    if not HERO_SMS_API_KEY:
        return jsonify({"success": False, "error": "Falta HERO_SMS_API_KEY en entorno"}), 500

    result = generate_account(API_KEY_CAPSOLVER, HERO_SMS_API_KEY, proxy, email, mail_token)
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "amazon-generator-ligero"})

if __name__ == '__main__':
    logger.info(f"Iniciando API en {API_HOST}:{API_PORT}")
    app.run(host=API_HOST, port=API_PORT, debug=False, threaded=True)