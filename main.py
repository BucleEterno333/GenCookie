#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ======================================================================
# PARCH SSL GLOBAL - CORRECTO (sin modificar el constructor de Session)
# ======================================================================
import os
import sys
import ssl

# 1. Desactivar verificación SSL a nivel de módulo ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# 2. Variables de entorno para curl_cffi y requests
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

# 3. Parchear 'requests' estándar (parcheando el método request de Session)
import requests as std_requests
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
try:
    import curl_cffi
    from curl_cffi import requests as cffi_requests

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
except ImportError:
    print("⚠️ curl_cffi no instalado, omitiendo parche para curl_cffi")

# 5. Desactivar advertencias de urllib3
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

print("🚀 SSL desactivado globalmente")

# ======================================================================
# AHORA IMPORTS DEL RESTO DEL PROYECTO
# ======================================================================
import json
import time
import logging
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# Los módulos de amazon ya no darán error SSL
from amazon import core, helpers, AmazonRegisterError, AccountBuilder, AwsWaf, CookieConverter
from amazon.sms import HeroSms
from amazon.captcha import Captcha

# ======================================================================
# CONFIGURACIÓN
# ======================================================================
ROOT = Path(__file__).resolve().parent
CONFIG = {
    "SMS_TIMEOUT": "75",
    "SMS_MAX_PRICE": "0.18",
    "ACCOUNTS_FILE": "accounts.txt",
    "COOKIES_FILE": "cookies.txt",
}

def load_env():
    for key, value in CONFIG.items():
        if value is not None and str(value) != "" and not os.environ.get(key):
            os.environ[key] = str(value)

logger = logging.getLogger(__name__)
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "35"))
CAPTCHA_MAX = 4
load_env()

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
        self.sms_service   = HeroSms(herosms_api_key, maxPrice=_sms_price, targetCountry=country)
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
                if needs_new_number:
                    self._emit("Acquiring new number...")
                    try:
                        self.phone_data = self.sms_service.getNumber()
                    except Exception as sms_err:
                        logger.warning(f"No se pudo obtener número: {sms_err}")
                        return self._error(str(sms_err))
        return self._error("Unexpected exit")

    def _attempt(self, retry: int) -> dict:
        self._emit(f"Attempt #{retry + 1}")
        init_time = time.time()

        if not self.phone_data:
            self._emit("Acquiring phone number...")
            self.phone_data = self.sms_service.getNumber()
            self._emit(f"Phone: {self.phone_data['number']}")
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


# ======================================================================
# FUNCIONES AUXILIARES
# ======================================================================
def _json_pretty(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

def _save_account(result: dict, base_dir) -> None:
    out = _to_json_output(result)
    if not out.get("cookie"):
        return
    root = Path(base_dir)
    accounts = root / os.environ.get("ACCOUNTS_FILE", "accounts.txt")
    cookies_only = root / os.environ.get("COOKIES_FILE", "cookies.txt")
    block = _json_pretty(out) + "\n\n"
    with accounts.open("a", encoding="utf-8") as f:
        f.write(block)
    with cookies_only.open("a", encoding="utf-8") as f:
        f.write(out["cookie"] + "\n")
    logger.info(f"Guardado en {accounts.name} y {cookies_only.name}")

def _to_json_output(result: dict) -> dict:
    if not result.get("status"):
        return {"error": result.get("message", "unknown")}
    p = result.get("profile", {})
    country = (result.get("country") or "MX").upper()
    raw_cookie = result.get("cookies", "")
    cookie = CookieConverter.convert(raw_cookie, country) if raw_cookie else ""
    return {
        "email": p.get("email"),
        "number": p.get("phone"),
        "pass": p.get("password"),
        "cookie": cookie,
    }


# ======================================================================
# MAIN
# ======================================================================
def main():
    print("🔧 Iniciando creación de cuenta...")
    creator = AmazonAccountCreator(
        herosms_api_key="86A8d0e8568d6b58cAf6e1f8f08bb7e2",
        capsolver_api_key="CAP-C7546CC57C21C38502C8D400BC2DD03F3E3BC4CDD444DD0394E0F747EF821E76",
        country="CA",
        proxy="smart-exjkik2gduu2_area-MX_city-MEXICOCITY:vxwFNkrhvAeeIqA2@proxy.smartproxy.net:3121",
    )
    result = creator.create(max_retries=10)
    out = _to_json_output(result)
    print(_json_pretty(out), flush=True)
    if result.get("status"):
        _save_account(result, ROOT)

if __name__ == "__main__":
    main()