import random, re, string, json
from typing import Optional, Dict
from . import core
from .helpers import normalizeProxy
from curl_cffi import requests as curl
from urllib.parse import urlencode, quote
from bs4 import BeautifulSoup


class AccountBuilder:

    COUNTRY_MAP: Dict[str, Dict[str, str]] = {"US": {"code": "main", "currency": "USD", "lc": "lc-main", "lc_value": "en_US", "domain": "amazon.com"}, "CA": {"code": "acbca", "currency": "CAD", "lc": "lc-acbca", "lc_value": "en_CA", "domain": "amazon.ca"}, "MX": {"code": "acbmx", "currency": "MXN", "lc": "lc-acbmx", "lc_value": "es_MX", "domain": "amazon.com.mx"}}

    def __init__(self, cookie: str, country: str = None, proxy: str = None) -> None:
        px = normalizeProxy(proxy)
        self.proxy_dict = {"http": px, "https": px} if px else None
        if country and country.upper() in self.COUNTRY_MAP:
            target = self.COUNTRY_MAP[country.upper()]
            self.countryCode = country.upper()
            self.domain = target['domain']
            self.cookie = cookie
            self.session = self.__buildSessionForCountry(cookie, target['domain'])
        else:
            cookieBuilded = self.buildCookieData(cookie)
            self.cookieNonBuild = cookie
            self.cookie = cookieBuilded['cookie']
            self.domain = cookieBuilded['domain']
            self.countryCode = cookieBuilded['country_code']
            self.session = self.createCookieJarFromString(self.cookie, self.domain)

    def __buildSessionForCountry(self, cookie: str, target_domain: str) -> curl.Session:
        session = curl.Session(impersonate=random.choice(core.IMPERSONATE_BROWSERS), proxies=self.proxy_dict)
        for pair in cookie.split(";"):
            if "=" not in pair:
                continue
            name, value = map(str.strip, pair.split("=", 1))
            session.cookies.set(name, value, domain=target_domain, path="/")
            if target_domain != "amazon.com":
                session.cookies.set(name, value, domain="amazon.com", path="/")
        session.allow_redirects = True
        session.headers.update({"Connection": "keep-alive"})
        return session

    def extractBetween(self, haystack: Optional[str], start: str, end: str, index: int = 1) -> Optional[str]:
        if haystack is None:
            return None
        try:
            return haystack.split(start)[index].split(end)[0]
        except Exception:
            return None

    def extractRegionCode(self, cookie: str) -> Optional[str]:
        m = re.search(r"\b(main|acb[a-z]{2})\b", cookie, re.I)
        return m.group(1).lower() if m else None

    def createCookieJarFromString(self, cookie: str, domain: str) -> curl.Session:
        session = curl.Session(impersonate=random.choice(core.IMPERSONATE_BROWSERS), proxies=self.proxy_dict)
        for pair in cookie.split(";"):
            if "=" not in pair:
                continue
            name, value = map(str.strip, pair.split("=", 1))
            session.cookies.set(name, value, domain=domain, path="/")
        session.allow_redirects = True
        session.headers.update({"Connection": "keep-alive"})
        return session

    def buildCookieData(self, cookie: str) -> dict:
        region_code = self.extractRegionCode(cookie.strip())
        if not region_code:
            return {"status": False, "message": "Region code not found in cookie."}
        country_map = {v["code"]: v for v in self.COUNTRY_MAP.values()}
        if region_code not in country_map:
            return {"status": False, "message": f"Unsupported region code: {region_code}."}
        country = country_map[region_code]
        all_codes = {v["code"] for v in self.COUNTRY_MAP.values()} | {"acbuc"}
        parts = []
        for pair in cookie.split(";"):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                parts.append(pair)
                continue
            name, value = pair.split("=", 1)
            name = name.strip()
            for code in sorted(all_codes, key=len, reverse=True):
                if name.endswith(f"-{code}"):
                    name = name[:-len(code)] + country["code"]
                    break
            if name == "i18n-prefs":
                value = country["currency"]
            if name == country["lc"]:
                value = country["lc_value"]
            parts.append(f"{name}={value}")
        cookie = "; ".join(parts)
        return {
            "status": True,
            "cookie": cookie,
            "domain": country["domain"],
            "country_code": next(k for k, v in self.COUNTRY_MAP.items() if v == country),
        }

    def addBillingAddress(self) -> bool:
        COUNTRY_DATA = {
            'US': {'countryCode': 'AF', 'fullName': 'Ahmad Wali', 'phone': '0700123456', 'line1': 'Street 1 Wazir Akbar Khan', 'city': 'Kabul', 'state': 'Kabul', 'postalCode': '1001'},
            'CA': {'countryCode': 'AF', 'fullName': 'Ahmad Wali', 'phone': '0700123456', 'line1': 'Street 1 Wazir Akbar Khan', 'city': 'Kabul', 'state': 'Kabul', 'postalCode': '1001'},
            'MX': {'countryCode': 'AF', 'fullName': 'Ahmad Wali', 'phone': '0700123456', 'line1': 'Street 1 Wazir Akbar Khan', 'city': 'Kabul', 'state': 'Kabul', 'postalCode': '1001'},
        }
        data = COUNTRY_DATA.get(self.countryCode.upper(), COUNTRY_DATA['US'])
        headers1 = {
            "host": f"www.{self.domain}",
            "referer": f"https://www.{self.domain}/a/addresses?ref_=ya_d_c_addr",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "viewport-width": "1536",
        }

        try:
            req = self.session.get(
                url=f"https://www.{self.domain}/a/addresses/add?ref=ya_address_book_add_button",
                headers=headers1,
                timeout=20,
            )
            request1 = req.text
        except Exception:
            return False

        start_time = self.extractBetween(request1, 'name="address-ui-widgets-form-load-start-time" value="', '"')
        request_id = self.extractBetween(request1, '=AddView&hostPageRID=', '&', 1)
        csrf_token = self.extractBetween(request1, 'type="hidden" name="address-ui-widgets-csrfToken" value="', '"')
        address_jwt = self.extractBetween(request1, 'type="hidden" name="address-ui-widgets-previous-address-form-state-token" value="', '"')
        customer_id = self.extractBetween(request1, '"customerID":"', '"')
        interaction_id = self.extractBetween(request1, 'name="address-ui-widgets-address-wizard-interaction-id" value="', '"')
        csrf_token_address = self.extractBetween(request1, "type='hidden' name='csrfToken' value='", "'")

        if not csrf_token and not csrf_token_address:
            return False

        headers3 = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Origin": f"https://www.{self.domain}",
            "Referer": f"https://www.{self.domain}/a/addresses/add?ref=ya_address_book_add_button",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }
        payload3 = {
            "csrfToken": csrf_token_address or "",
            "addressID": "",
            "address-ui-widgets-countryCode": data["countryCode"],
            "address-ui-widgets-enterAddressFullName": data["fullName"],
            "address-ui-widgets-enterAddressLine1": data["line1"],
            "address-ui-widgets-enterAddressPostalCode": data["postalCode"],
            "address-ui-widgets-enterAddressStateOrRegion": data["state"],
            "address-ui-widgets-enterAddressCity": data["city"],
            "address-ui-widgets-enterAddressDistrictOrCounty": data.get("district", ""),
            "address-ui-widgets-enterAddressPhoneNumber": data["phone"],
            "address-ui-widgets-previous-address-form-state-token": address_jwt or "",
            "address-ui-widgets-addressFormButtonText": "save",
            "address-ui-widgets-addressFormHideHeading": "true",
            "address-ui-widgets-enableAddressDetails": "true",
            "address-ui-widgets-returnLegacyAddressID": "false",
            "address-ui-widgets-enableDeliveryInstructions": "true",
            "address-ui-widgets-clientName": "YourAccountAddressBook",
            "address-ui-widgets-obfuscated-customerId": customer_id or "",
            "address-ui-widgets-csrfToken": csrf_token or "",
            "address-ui-widgets-form-load-start-time": start_time or "",
            "address-ui-widgets-clickstream-related-request-id": request_id or "",
            "address-ui-widgets-address-wizard-interaction-id": interaction_id or "",
        }
        resp = self.session.post(
            f"https://www.{self.domain}/a/addresses/add?ref=ya_address_book_add_post",
            headers=headers3,
            data=payload3,
            timeout=30,
        )
        self.countryData = data

        addr_id = (
            self.extractBetween(resp.text, 'addressId=', '&')
            or self.extractBetween(resp.text, 'addressId=', '"')
            or self.extractBetween(resp.text, '"addressId":"', '"')
        )
        if addr_id:
            self._addressId = addr_id
            return True

        self._addressId = self.__getAddressIdFromBook()
        return resp.status_code == 200

    def __getAddressIdFromBook(self) -> Optional[str]:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"}
            resp = self.session.get(f"https://www.{self.domain}/a/addresses", headers=headers, timeout=20)
            addr_id = self.extractBetween(resp.text, 'data-addressid="', '"')
            if addr_id:
                return addr_id
            addr_id = self.extractBetween(resp.text, 'addressId=', '&')
            if addr_id:
                return addr_id
            addr_id = self.extractBetween(resp.text, 'addressID=', '&')
            if addr_id:
                return addr_id
            return self.extractBetween(resp.text, '"addressId":"', '"')
        except Exception:
            return None

    def getBillingAddressId(self) -> Optional[str]:
        if hasattr(self, '_addressId') and self._addressId:
            return self._addressId
        return self.__getAddressIdFromBook()

    def handleBillingAddress(self) -> dict:
        added = self.addBillingAddress()
        if not added:
            return {'status': False, 'message': 'Failed Adding Billing Address'}
        addressId = self.getBillingAddressId()
        if not addressId:
            addressId = self.getBillingAddressId()
        if addressId:
            return {'status': True, 'message': 'Billing Address Added', 'data': self.countryData, 'addressId': addressId}
        return {'status': False, 'message': 'Failed Adding Billing Address'}


class AmazonRegisterError(Exception):
    pass
