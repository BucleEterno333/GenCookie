import os
import secrets, re, time, logging
import requests

logger = logging.getLogger(__name__)


class HeroSms:

    COUNTRY_ID = 187
    SERVICE = 'am'
    DEFAULT_MAX_PRICE = 0.12

    def __init__(self, apiKey: str, maxPrice: float = None, targetCountry: str = 'CA') -> None:
        self.apiKey = apiKey
        self.apiUrl = (
            os.getenv("HERO_SMS_API")
            or "https://hero-sms.com/stubs/handler_api.php"
        )
        self.session = requests.Session()
        self.maxPrice = float(maxPrice if maxPrice is not None else self.DEFAULT_MAX_PRICE)
        self.targetCountry = targetCountry

    def _price_param(self) -> str:
        return f"{self.maxPrice:.2f}"

    def __normalizeNumber(self, phone: str) -> str:
        phone_digits = re.sub(r"\D", "", phone)
        if phone_digits.startswith("1") and len(phone_digits) == 11:
            phone_digits = phone_digits[1:]
        if len(phone_digits) > 10:
            phone_digits = phone_digits[-10:]
        return phone_digits

    def __parseResponse(self, response):
        try:
            return response.json()
        except Exception:
            return response.text.strip()

    def getNumber(self, retries=0, no_numbers_retries=0) -> dict:
        try:
            params = {
                "action": "getNumberV2",
                "api_key": self.apiKey,
                "service": self.SERVICE,
                "country": self.COUNTRY_ID,
                "operator": "any",
                "maxPrice": self._price_param(),
                "fixedPrice": "true",
                "ref": secrets.token_hex(8),
            }
            resp = self.session.get(self.apiUrl, params=params, timeout=30)
            data = self.__parseResponse(resp)

            if isinstance(data, str):
                fatal = {"BAD_KEY", "NO_BALANCE", "BANNED:KEY"}
                code = data.split(":")[0] if ":" in data else data
                if code in fatal:
                    error_map = {
                        "BAD_KEY": "API key inválida.",
                        "NO_BALANCE": "Saldo insuficiente.",
                        "BANNED:KEY": "API key baneada.",
                    }
                    raise RuntimeError(f"HeroSMS: {error_map.get(code, code)}")
                if code == "NO_NUMBERS" and no_numbers_retries < 8:
                    logger.debug(f"HeroSMS sin números, reintento {no_numbers_retries + 1}/8...")
                    time.sleep(1.5)
                    return self.getNumber(retries, no_numbers_retries + 1)
                raise RuntimeError(f"HeroSMS: {data}")

            if isinstance(data, dict):
                error = data.get("title") or data.get("error") or data.get("msg")
                if error:
                    if str(error) == "NO_NUMBERS" and no_numbers_retries < 8:
                        logger.debug(f"HeroSMS sin números, reintento {no_numbers_retries + 1}/8...")
                        time.sleep(1.5)
                        return self.getNumber(retries, no_numbers_retries + 1)
                    raise RuntimeError(f"HeroSMS: {error}")
                if "phoneNumber" not in data:
                    raise RuntimeError(f"HeroSMS: Respuesta inesperada: {data}")
                price = float(data.get("activationCost", 0))
                activation_id = str(data["activationId"])
                phone_number = str(data["phoneNumber"])
                logger.info(
                    f"Number: {phone_number} | ID: {activation_id} | "
                    f"Country: {self.COUNTRY_ID} | maxPrice=${self._price_param()} | paid=${price}"
                )
                return {
                    "activationId": activation_id,
                    "number": phone_number,
                    "normalizedNumber": self.__normalizeNumber(phone_number),
                }
            raise RuntimeError(f"HeroSMS: Respuesta inválida: {data}")

        except RuntimeError:
            raise
        except Exception as e:
            if retries < 3:
                logger.warning(f"Retrying getNumber ({retries + 1}/3): {str(e)} — esperando 2s...")
                time.sleep(1.0)
                return self.getNumber(retries + 1, no_numbers_retries)
            raise RuntimeError(f"Failed to get number: {str(e)}")

    def markReady(self, activationId: str) -> None:
        try:
            self.session.get(self.apiUrl, params={
                "action": "setStatus", "status": 1,
                "id": activationId, "api_key": self.apiKey,
            }, timeout=15)
        except Exception:
            pass

    def getSMS(self, activationId: str, timeout: int = 120) -> str:
        deadline = time.time() + timeout
        params = {"action": "getStatusV2", "api_key": self.apiKey, "id": activationId}
        while True:
            resp = self.session.get(self.apiUrl, params=params, timeout=30)
            try:
                data = resp.json()
                sms = data.get("sms") or {}
                code = sms.get("code", "")
                if code:
                    logger.info(f"[HeroSMS] SMS code received: {code}")
                    return str(code)
            except Exception:
                text = resp.text.strip()
                if text.startswith("STATUS_OK:"):
                    return text.split(":", 1)[1]
                if text == "STATUS_CANCEL":
                    raise RuntimeError(f"Activation {activationId} was cancelled.")
            if time.time() > deadline:
                self.cancelActivation(activationId)
                raise RuntimeError(f"Activation {activationId} timed out after {timeout}s.")
            time.sleep(1.5)

    def cancelActivation(self, activationId: str) -> None:
        try:
            params = {"action": "cancelActivation", "id": activationId, "api_key": self.apiKey}
            self.session.get(self.apiUrl, params=params, timeout=30)
        except Exception:
            pass

    def finishActivation(self, activationId: str) -> None:
        try:
            params = {"action": "finishActivation", "id": activationId, "api_key": self.apiKey}
            self.session.get(self.apiUrl, params=params, timeout=30)
        except Exception:
            pass