import json
import random
import re
import capsolver
import logging as _logging
_Log = type("_Log", (), {"error": staticmethod(lambda m: _logging.getLogger(__name__).error(m)), "detail": staticmethod(lambda k,v: _logging.getLogger(__name__).debug(f"{k}: {v}")), "success": staticmethod(lambda m: _logging.getLogger(__name__).info(m)), "info": staticmethod(lambda m: _logging.getLogger(__name__).info(m))})()


class Captcha:

    HANDLE_LANG = {
        'usflex': 'en', 'caflex': 'en', 'mxflex': 'es',
    }

    @staticmethod
    def solve(session, page_text, page_url, base_domain, capsolver_api_key, assoc_handle='usflex', on_status=None):
        def _status(msg):
            if on_status:
                try:
                    on_status(msg)
                except Exception:
                    pass
            _Log.info(msg)

        capsolver.api_key = capsolver_api_key
        from bs4 import BeautifulSoup

        html = BeautifulSoup(page_text, 'html.parser')
        csrf_el = html.find('input', {'name': 'anti-csrftoken-a2z'})
        csrf = csrf_el.get('value', '') if csrf_el else None

        data_context = re.findall(r'"data-context":\s*\'({[^\']*})\'', page_text)
        data_context = data_context[0] if data_context else None

        def _between(data, first, last):
            try:
                s = data.index(first) + len(first)
                return data[s:data.index(last, s)]
            except ValueError:
                return None

        ext_id = _between(page_text, '"data-external-id": "', '"')
        client_ctx = _between(page_text, '<input type="hidden" name="clientContext" value="', '"')
        verify_token = _between(page_text, '<input type="hidden" name="verifyToken" value="', '"')
        return_to = _between(page_text, '<input type="hidden" name="openid.return_to" value="', '"')
        if return_to:
            return_to = return_to.replace('&amp;', '&')

        if not data_context or not ext_id:
            _status(f"Captcha: datos faltantes (context={bool(data_context)}, ext_id={bool(ext_id)})")
            return None

        _status(f"Captcha: external-id={ext_id[:24]}...")

        _status("Captcha: cargando widget...")
        options = json.dumps({
            "clientData": data_context,
            "challengeType": "WAF_ADVERSARIAL_SYNTHETIC_GRID_V2_LEVEL_1",
            "locale": "en-US", "externalId": ext_id,
            "enableHeaderFooter": False, "enableBypassMechanism": False,
            "enableModalView": False, "eventTrigger": None,
            "aaExternalToken": None, "forceJsFlush": False, "aamationToken": None
        }, separators=(',', ':'))

        w = session.get(f'{base_domain}/aaut/verify/cvf', params={'options': options}, headers={
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }, timeout=60)
        amz = json.loads(w.headers.get('amz-aamation-resp', '{}'))
        client_side_ctx = amz.get('clientSideContext')

        problem = _between(w.text, '"problem":"', '"')
        cap_id = _between(w.text, '"id":"', '"')
        cap_url = _between(w.text, '<script src="', '"')
        cap_domain = _between(cap_url, 'https://', '/ait/') if cap_url else None

        if not cap_domain or not problem:
            _status("Captcha: widget sin domain/problem")
            return None

        _status(f"Captcha: descargando problema ({cap_domain})...")
        prob = session.get(f'https://{cap_domain}/ait/ait/ait/problem', params={
            'kind': 'visual', 'domain': base_domain.replace('https://', ''),
            'locale': 'en-us', 'problem': problem,
            'num_solutions_required': '1', 'id': cap_id,
        }, timeout=60)
        pj = prob.json()

        target = pj['assets']['target']
        images = json.loads(pj['assets']['images'])
        target = target.replace("[", "").replace("]", "").replace("'", "").replace('"', "").replace("_", " ").strip()
        _status(f"Captcha: objetivo «{target}» ({len(images)} imágenes)")

        _status("Captcha: enviando a CapSolver...")
        sol = capsolver.solve({
            "type": "AwsWafClassification",
            "question": f"aws:grid:{target}",
            "images": images,
        })
        if not sol.get('objects'):
            _status("Captcha: CapSolver no devolvió solución")
            return None
        _status(f"Captcha: CapSolver respondió → celdas {sol['objects']}")

        _status("Captcha: verificando solución con Amazon...")
        vr = session.post(f'https://{cap_domain}/ait/ait/ait/verify', json={
            "hmac_tag": pj['hmac_tag'],
            "state": {"iv": pj['state']['iv'], "payload": pj['state']['payload']},
            "key": pj['key'],
            "client_solution": sol['objects'],
            "metrics": {"solve_time_millis": random.randint(3000, 8000)},
            "locale": "en-us"
        }, timeout=60)
        vj = vr.json()
        if not vj.get('success'):
            _status("Captcha: Amazon rechazó la solución")
            return None
        _status("Captcha: solución aceptada por Amazon")

        _status("Captcha: canjeando voucher...")
        voucher = vj['captcha_voucher']
        vr2 = session.get(f'{base_domain}/aaut/verify/cvf/{cap_id}', params={
            'context': client_side_ctx,
            'options': options,
            'response': json.dumps({
                "challengeType": "WAF_ADVERSARIAL_SYNTHETIC_GRID_V2_LEVEL_1",
                "data": f'"{voucher}"'
            }, separators=(',', ':')),
        }, headers={
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }, timeout=60)
        amz2 = json.loads(vr2.headers.get('amz-aamation-resp', '{}'))
        sess_token = amz2.get('sessionToken')
        if not sess_token:
            _status("Captcha: sin session token tras voucher")
            return None
        _status(f"Captcha: session token obtenido ({len(sess_token)} chars)")

        _status("Captcha: enviando CVF verify...")
        cvf_data = {
            'anti-csrftoken-a2z': csrf,
            'cvf_aamation_response_token': sess_token,
            'cvf_captcha_captcha_action': 'verifyAamationChallenge',
            'cvf_aamation_error_code': '',
            'clientContext': client_ctx,
            'openid.pape.max_auth_age': '900',
            'openid.return_to': return_to or '',
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
            'openid.assoc_handle': assoc_handle,
            'openid.mode': 'checkid_setup',
            'openid.ns.pape': 'http://specs.openid.net/extensions/pape/1.0',
            'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
            'pageId': assoc_handle,
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'language': Captcha.HANDLE_LANG.get(assoc_handle, 'en'),
            'verifyToken': verify_token,
        }

        cvf = session.post(f'{base_domain}/ap/cvf/verify', data=cvf_data, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': base_domain, 'Referer': str(page_url),
            'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }, timeout=60, allow_redirects=True)

        _status(f"Captcha: CVF verify HTTP {cvf.status_code} → {str(cvf.url)[:70]}")
        return cvf
