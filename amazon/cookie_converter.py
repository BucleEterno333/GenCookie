import re
from typing import Optional, Dict

class CookieConverter:

    REGIONS = {
        'US': {'suffix': 'main',  'currency': 'USD', 'locale': 'en_US', 'domain': 'amazon.com'},
        'CA': {'suffix': 'acbca', 'currency': 'CAD', 'locale': 'en_CA', 'domain': 'amazon.ca'},
        'MX': {'suffix': 'acbmx', 'currency': 'MXN', 'locale': 'es_MX', 'domain': 'amazon.com.mx'},
        'UK': {'suffix': 'acbuk', 'currency': 'GBP', 'locale': 'en_GB', 'domain': 'amazon.co.uk'},
        'FR': {'suffix': 'acbfr', 'currency': 'EUR', 'locale': 'fr_FR', 'domain': 'amazon.fr'},
        'IT': {'suffix': 'acbit', 'currency': 'EUR', 'locale': 'it_IT', 'domain': 'amazon.it'},
        'ES': {'suffix': 'acbes', 'currency': 'EUR', 'locale': 'es_ES', 'domain': 'amazon.es'},
        'AU': {'suffix': 'acbau', 'currency': 'AUD', 'locale': 'en_AU', 'domain': 'amazon.com.au'},
    }

    _ALL_SUFFIXES = {v['suffix'] for v in REGIONS.values()}

    @classmethod
    def detect_region(cls, cookie_text: str) -> Optional[str]:
        for code, cfg in cls.REGIONS.items():
            if f"-{cfg['suffix']}" in cookie_text:
                return code
        return None

    @classmethod
    def convert(cls, cookie_text: str, target_region: str) -> str:
        target_region = target_region.upper()
        if target_region not in cls.REGIONS:
            return cookie_text

        source = cls.detect_region(cookie_text)
        if not source or source == target_region:
            return cookie_text

        src = cls.REGIONS[source]
        dst = cls.REGIONS[target_region]

        out = cookie_text

        out = re.sub(
            rf'-{re.escape(src["suffix"])}\b',
            f'-{dst["suffix"]}',
            out,
        )

        out = re.sub(
            rf'\b{re.escape(src["suffix"])}\b',
            dst['suffix'],
            out,
        )

        out = re.sub(
            rf'(i18n-prefs=){re.escape(src["currency"])}',
            rf'\1{dst["currency"]}',
            out,
        )

        out = re.sub(
            re.escape(src['locale']),
            dst['locale'],
            out,
        )

        return out

    @classmethod
    def convert_all(cls, cookie_text: str) -> Dict[str, str]:
        return {code: cls.convert(cookie_text, code) for code in cls.REGIONS}