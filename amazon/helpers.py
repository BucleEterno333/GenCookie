import os, sys, random, re, time, types, uuid
from urllib.parse import urljoin
from faker import Faker
from curl_cffi import requests
from bs4 import BeautifulSoup
from . import core
from .fwcim import FwcimAmazon
from .cse import CseAmazon
import logging as _logging
class Log:
    @staticmethod
    def debug(m): _logging.getLogger(__name__).debug(m)


CSE_JWK_N  = "rwLCVK_8hcUgil9KQiN7RbtmcJV5Pt12CwbhZ1h9fvdbVRILCanjv2RNSW9l-Mq0fnRq6DLTLzX3J3TuVCZQ1wjfa-Ef1BDeXnVNaY4q0Vvl2e1e9UF-uwyK5mDyiftlPt5JcsRuFXU1dMSb5TwDiFV1UlGOc-db33zi1MlmrL5L7iyfqBQmlEoa5el5pFbmeK2wSOKBZtJja-dbVzde0jrpGlVhHDZOAlH7g8aTftqwHLVP27T9Pr0UJtaj9LIX-sg_K9-Pl7H2W9BJDTJLJi_EAAqBHTrRueejO3XbEuSGrsrphCk0ZlYqoLkobey-kubWTba5kzsWL-huF--tzQ"
CSE_KEY_ID = "973900addb061fbe5bb4ea871e9d8161"
EMAIL_DOMAINS = ('gmail.com', 'outlook.com')


def generateFakeProfile() -> types.SimpleNamespace:
    p = Faker("en_US").profile()
    first, last = p['name'].split()[0], p['name'].split()[-1]
    return types.SimpleNamespace(
        f_name=first, l_name=last, name=f"{first} {last}",
        password=f"Passwd{random.randint(1000, 9999)}{uuid.uuid4().hex[:8]}",
        mail=f"{first}{random.choice('._-')}{last}{random.randint(0, 999)}@{random.choice(EMAIL_DOMAINS)}",
    )


_LOCALE = {
    'MX': 'es-MX,es;q=0.9,en;q=0.8',
    'US': 'en-US,en;q=0.9',
    'CA': 'en-CA,en;q=0.9,fr;q=0.8',
}


def phone_country_code(phone: str, amazon_country: str) -> str:
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 11 and digits.startswith('1'):
        return 'US'
    if amazon_country == 'MX' and len(digits) == 10:
        return 'MX'
    return core.AMAZON_COUNTRY_CODE_MAP.get(amazon_country, amazon_country)


def waf_cookie_domain(domain: str) -> str:
    return domain if domain.startswith('.') else f'.{domain}'


def response_needs_waf(resp) -> bool:
    action = (getattr(resp, 'headers', {}) or {}).get('x-amzn-waf-action', '')
    if isinstance(action, str) and action.lower() in ('challenge', 'captcha'):
        return True
    return page_needs_waf(getattr(resp, 'text', '') or '')


def ensure_waf_token(session, base_url, domain, proxy, ua, page_html=None, page_headers=None, on_status=None):
    from .waf import AwsWaf

    needs = page_needs_waf(page_html or '')
    if page_headers:
        action = (page_headers.get('x-amzn-waf-action') or '').lower()
        if action in ('challenge', 'captcha'):
            needs = True

    if not needs:
        try:
            probe = session.get(f'{base_url}/', timeout=15)
            needs = response_needs_waf(probe)
            if needs:
                page_html = probe.text
        except Exception:
            pass

    if not needs:
        return session

    if on_status:
        on_status("Solving WAF challenge...")
    try:
        wr = AwsWaf(
            websiteURL=f'{base_url}/',
            proxy=normalizeProxy(proxy),
            userAgent=ua,
        ).solve(html=page_html, session=session)
        if wr.get('status'):
            session.cookies.set(
                'aws-waf-token', wr['token'],
                domain=waf_cookie_domain(domain), path='/',
            )
            _logging.getLogger(__name__).info(
                f"WAF token ({wr.get('timeTaken', '?')}, domain={domain})"
            )
        else:
            _logging.getLogger(__name__).warning(f"WAF failed: {wr.get('description')}")
    except Exception as e:
        _logging.getLogger(__name__).warning(f"WAF error: {e}")
    return session


def buildSession(baseUrl, domain, proxy):
    FwcimAmazon.reset_session()

    browser = random.choice(core.IMPERSONATE_BROWSERS)
    s = requests.Session(impersonate=browser)
    UA = random.choice(core.USER_AGENTS)

    fpProfile = FwcimAmazon._session_profile
    if not fpProfile:
        FwcimAmazon(location=baseUrl, userAgent=UA)
        fpProfile = FwcimAmazon._session_profile

    scr = fpProfile["screen"]
    vp = scr["width"]
    dpr = fpProfile["dpr"]
    devMem = str(min(8, fpProfile["deviceMemory"]))

    if proxy:
        px = proxy if '://' in proxy else f'http://{proxy}'
        s.proxies = {'http': px, 'https': px}
    s.headers.update({
        'User-Agent': UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'none', 'Sec-Fetch-User': '?1',
        'sec-ch-ua': '"Chromium";v="120", "Not:A-Brand";v="99"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"',
        'sec-ch-ua-full-version-list': '"Chromium";v="120.0.0.0", "Not:A-Brand";v="99.0.0.0"', 'sec-ch-ua-platform-version': '"10.0"',
        'device-memory': devMem, 'sec-ch-device-memory': devMem,
        'dpr': str(dpr), 'sec-ch-dpr': str(dpr),
        'viewport-width': str(vp), 'sec-ch-viewport-width': str(vp),
        'ect': '4g', 'rtt': '50', 'downlink': '10',
    })
    return s, UA


def getHiddenField(html, name):
    el = html.find('input', {'name': name})
    if el: return el.get('value', '')
    sel = html.find('select', {'name': name})
    if sel:
        opt = sel.find('option', selected=True)
        return opt.get('value', '') if opt else None
    return None


def postForm(s, url, data, referer, origin):
    return s.post(url, data=data, headers={
        'Content-Type': 'application/x-www-form-urlencoded', 'Origin': origin, 'Referer': str(referer),
        'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1', 'Upgrade-Insecure-Requests': '1',
    }, timeout=35)


def generateMetadata(location, referrer, urls, hashes, ua, email="", name=""):
    return FwcimAmazon(location=location, userAgent=ua, referrer=referrer,
        dynamicUrls=urls, inlineHashes=hashes, emailValue=email, customerName=name
    ).generateMetadata()['metadata1']


def extractScripts(htmlContent):
    urls = []
    for sc in re.findall(r'<script[\s\S]*?>[\s\S]*?<\/script>', htmlContent, re.IGNORECASE):
        for p in [re.compile(r'load\.js\([\'"](https?://[^\'"]+)[\'"]\)'),
                  re.compile(r'ue\.uels\([\'"](https?://[^\'"]+\.js)[\'"]\)'),
                  re.compile(r'src=["\'](https://static\.siege-amazon\.com/[^\'"]+\.js\?v=\d+)["\']')]:
            urls.extend(m.group(1) for m in p.finditer(sc))
    urls.reverse()
    hashes = []
    for sc in BeautifulSoup(htmlContent, 'html.parser').find_all('script'):
        if not sc.get('src') and sc.string:
            c = sc.string.strip()
            if c:
                h = 0
                for ch in c: h = (31 * h + ord(ch)) & 0xFFFFFFFF
                if h >= 0x80000000: h -= 0x100000000
                hashes.append(h)
    return urls, hashes


def submitRegister(s, page, ref, phoneShort, user, UA, flowBase, dynUrls, dynHashes, ccDefault, label):
    ph = BeautifulSoup(page.text, 'html.parser')
    pu, phh = extractScripts(page.text)
    md = generateMetadata(str(page.url), str(ref), pu or dynUrls, phh or dynHashes, UA, email=phoneShort, name=user.name)
    cse = CseAmazon(CSE_JWK_N, CSE_KEY_ID, "si:md5")
    enc = cse.encrypt(user.password)
    if not enc.get('status'):
        raise RuntimeError(f"CSE encrypt failed: {enc.get('description', enc)}")
    Log.debug(f"[{label}] md1={len(md)}c pwd={len(enc['encryptedPassword'])}c")
    return postForm(s, f'{flowBase}/ap/register', {
        'appActionToken': getHiddenField(ph, 'appActionToken'), 'appAction': 'REGISTER',
        'openid.return_to': getHiddenField(ph, 'openid.return_to'), 'prevRID': getHiddenField(ph, 'prevRID'),
        'workflowState': getHiddenField(ph, 'workflowState'), 'anti-csrftoken-a2z': getHiddenField(ph, 'anti-csrftoken-a2z'),
        'claimCollectionLayoutType': getHiddenField(ph, 'claimCollectionLayoutType') or 'unifiedAuthClaimCollection',
        'unifiedAuthTreatment': getHiddenField(ph, 'unifiedAuthTreatment') or 'T2',
        'countryCode': getHiddenField(ph, 'countryCode') or ccDefault,
        'email': phoneShort, 'customerName': user.name,
        'encryptedPwd': enc['encryptedPassword'], 'encryptedPwdCheck': enc['encryptedPasswordCheck'],
        'metadata1': md, 'encryptedPasswordExpected': '',
    }, page.url, flowBase)


def normalizeProxy(proxy):
    if not proxy: return None
    return proxy if '://' in proxy else f'http://{proxy}'


def page_needs_waf(html: str) -> bool:
    return bool(re.search(r'src="https://[^"]+/challenge[^"]*\.js"', html))


def export_session_cookies(session, domain: str) -> str:
    dom = domain.lstrip(".")
    parts = []
    seen = set()
    try:
        for c in session.cookies.jar:
            cd = (getattr(c, "domain", None) or "").lstrip(".")
            if dom in cd or cd.endswith(dom):
                key = (c.name, cd)
                if key not in seen:
                    seen.add(key)
                    parts.append(f"{c.name}={c.value}")
    except Exception:
        pass
    if not parts:
        parts = [f"{k}={session.cookies.get(k)}" for k in session.cookies.keys()]
    return "; ".join(parts)


def _is_transient_curl_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in (
        'curl', 'tls', 'ssl', 'connection reset', 'timed out',
        'connection refused', 'invalid library', 'openssl',
    ))


def get_with_retry(session, url, timeout=35, retries=2, proxy=None, base_url=None, domain=None):
    s = session
    last_err = None
    for attempt in range(retries):
        try:
            return s.get(url, timeout=timeout), s
        except Exception as e:
            last_err = e
            if attempt >= retries - 1 or not _is_transient_curl_error(e):
                raise
            _logging.getLogger(__name__).warning(
                f"HTTP retry {attempt + 1}/{retries}: {e}"
            )
            time.sleep(2 * (attempt + 1))
            if proxy is not None and base_url and domain:
                s, _ = buildSession(base_url, domain, proxy)
    raise last_err


def post_with_retry(session, url, data, referer, origin, timeout=60, retries=3,
                    proxy=None, base_url=None, domain=None):
    s = session
    last_err = None
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded', 'Origin': origin, 'Referer': str(referer),
        'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1', 'Upgrade-Insecure-Requests': '1',
    }
    for attempt in range(retries):
        try:
            return s.post(url, data=data, headers=headers, timeout=timeout), s
        except Exception as e:
            last_err = e
            if attempt >= retries - 1 or not _is_transient_curl_error(e):
                raise
            _logging.getLogger(__name__).warning(
                f"HTTP retry {attempt + 1}/{retries}: {e}"
            )
            time.sleep(1.0 * (attempt + 1))
            if proxy is not None and base_url and domain:
                s, _ = buildSession(base_url, domain, proxy)
    raise last_err


def isOtp(t, url: str = '') -> bool:
    if isCaptcha(t):
        return False
    low = t.lower()
    if 'se ha producido un error' in low:
        return False
    if any(k in low for k in [
        'verify your identity', 'verification code', 'we sent a code',
        'confirma tu identidad', 'confirme su identidad', 'verify mobile',
        'enviamos un código', 'te enviamos un código', 'enviamos un codigo',
        'código de verificación', 'codigo de verificacion',
        'introduce el código', 'ingresa el código', 'ingresa el codigo',
        'verificar tu identidad', 'verificación de identidad',
        'verificacion de identidad', 'te enviamos un sms',
        'mensaje de texto', 'two-step verification', 'verificación en dos pasos',
    ]): # Keys de Verificacion
        return True
    if re.search(r'name=["\'](code|otpcode|otc|cvf_otp_code)["\']', t, re.I):
        return True
    if 'requestedcontacttype' in low:
        return True
    if any(k in low for k in ('/ap/cvf', 'cvf_request', 'auth-validate', 'verifyotp')):
        return True
    url_low = (url or '').lower()
    if '/ap/cvf' in url_low or '/cvf/' in url_low:
        return True
    return False


def isCaptcha(t):
    return 'data-external-id' in t and ('aamation' in t.lower() or 'Authentication required' in t)

def isUnusual(t):
    return any(k in t.lower() for k in ['unusual activity', "aren't able to create", 'actividad inusual', 'no podemos crear'])

def isRegForm(t):
    return 'appActionToken' in t and ('REGISTER' in t or 'register' in t.lower())
