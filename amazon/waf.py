import os, re, json, time, zlib, uuid, base64, random, hashlib, itertools
from typing import Optional
from urllib.parse import urlparse
from curl_cffi import requests
import requests as std_requests
# Modificado a PyCryptodome
from Crypto.Cipher import AES
class AwsWaf:
    _JS_CONFIG_CACHE: dict = {}
    _HTTP_TIMEOUT = 15
    __AES_KEY = bytes.fromhex("6f71a512b1e035eaab53d8be73120d3fb68a0ca346b9560aab3e5cdf753d5e98")

    __CHALLENGE_SCRYPT    = "h72f957df656e80ba55f5d8ce2e8c7ccb59687dba3bfb273d54b08a261b2f3002"
    __CHALLENGE_SHA256    = "h7b0c470f0cfe3a80a9e26526ad185f484f6817d0832712a4a37a908786a6a67f"
    __CHALLENGE_BANDWIDTH = "ha9faaffd31b4d5ede2a2e19d2d7fd525f66fee61911511960dcbb52d3c48ce25"

    __DEFAULT_BANDWIDTH_SIZES = {1: 0x400, 2: 0xA * 0x400, 3: 0x64 * 0x400, 4: 0x100000, 5: 0xA * 0x100000}

    __FP_VERSION = "2.4.0"
    __DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"

    __GPU_PROFILES = [
        {"vendor": "Google Inc. (Apple)",  "model": "ANGLE (Apple, ANGLE Metal Renderer: Apple M2 Pro, Unspecified Version)", "extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_clip_control;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_float_blend;EXT_frag_depth;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_sRGB;OES_element_index_uint;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw"},
        {"vendor": "Google Inc. (AMD)",    "model": "ANGLE (AMD, AMD Radeon(TM) Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)", "extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_float_blend;EXT_frag_depth;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_sRGB;OES_element_index_uint;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw"},
        {"vendor": "Google Inc. (Intel)",  "model": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)", "extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_float_blend;EXT_frag_depth;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_sRGB;OES_element_index_uint;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw"},
        {"vendor": "Google Inc. (NVIDIA)", "model": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)", "extensions": "ANGLE_instanced_arrays;EXT_blend_minmax;EXT_color_buffer_half_float;EXT_depth_clamp;EXT_float_blend;EXT_frag_depth;EXT_shader_texture_lod;EXT_texture_compression_bptc;EXT_texture_compression_rgtc;EXT_texture_filter_anisotropic;EXT_sRGB;OES_element_index_uint;OES_standard_derivatives;OES_texture_float;OES_texture_float_linear;OES_texture_half_float;OES_texture_half_float_linear;OES_vertex_array_object;WEBGL_color_buffer_float;WEBGL_compressed_texture_s3tc;WEBGL_compressed_texture_s3tc_srgb;WEBGL_debug_renderer_info;WEBGL_debug_shaders;WEBGL_depth_texture;WEBGL_draw_buffers;WEBGL_lose_context;WEBGL_multi_draw"},
    ]

    def __init__(self, websiteURL: str, proxy: str = None, userAgent: str = None, impersonate: str = "chrome") -> None:
        self.__websiteURL  = websiteURL
        self.__proxy       = proxy
        self.__userAgent   = userAgent or self.__DEFAULT_UA
        self.__impersonate = impersonate
        self.__jsConfig    = None

    # ==================== AES-GCM ================
    def __aesEncrypt(self, plaintext: bytes) -> str:
        iv = os.urandom(12)
        cipher = AES.new(self.__AES_KEY, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        return f"{base64.b64encode(iv).decode()}::{tag.hex()}::{ciphertext.hex()}"
    # =================================================================

    def solve(self, html: str = None, session: requests.Session = None) -> dict:
        try:
            start = time.time()
            token, challengeInfo = self.__solveChallenge(html=html, session=session)
            elapsed = time.time() - start

            return {
                'status': True,
                'context': 'AWS WAF Challenge Token Bypass',
                'url': self.__websiteURL,
                'proxy': self.__proxy or 'direct',
                'token': token,
                'challenge': challengeInfo,
                'timeTaken': f'{elapsed:.2f}s',
            }
        except Exception as error:
            return {'status': False, 'description': str(error)}

    def __makeSession(self) -> requests.Session:
        kwargs = {"impersonate": self.__impersonate}
        if self.__proxy:
            kwargs["proxies"] = {"https": self.__proxy, "http": self.__proxy}
        return requests.Session(**kwargs)

    def __pageHeaders(self) -> dict:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": self.__userAgent
        }

    def __apiHeaders(self, origin: str = None, referer: str = None) -> dict:
        h = {
            "connection": "keep-alive",
            "sec-ch-ua-platform": '"Windows"',
            "user-agent": self.__userAgent,
            "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "accept": "*/*",
            "sec-fetch-site": "cross-site",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9"
        }
        if origin:  h["origin"] = origin
        if referer: h["referer"] = referer
        return h

    def __crc32(self, data: bytes) -> str:
        return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"

    def __generateFingerprint(self) -> dict:
        ts = int(time.time() * 1000)
        gpu = random.choice(self.__GPU_PROFILES)
        bins = [random.randrange(0, 40) for _ in range(256)]
        bins[0] = random.randrange(14473, 16573)
        bins[-1] = random.randrange(14473, 16573)

        return {
            "metrics": {"fp2": 1, "browser": 0, "capabilities": 1, "gpu": 7, "dnt": 0, "math": 0, "screen": 0, "navigator": 0, "auto": 1, "stealth": 0, "subtle": 0, "canvas": 5, "formdetector": 1, "be": 0},
            "start": ts,
            "flashVersion": None,
            "plugins": [{"name": "PDF Viewer", "str": "PDF Viewer "}, {"name": "Chrome PDF Viewer", "str": "Chrome PDF Viewer "}, {"name": "Chromium PDF Viewer", "str": "Chromium PDF Viewer "}, {"name": "Microsoft Edge PDF Viewer", "str": "Microsoft Edge PDF Viewer "}, {"name": "WebKit built-in PDF", "str": "WebKit built-in PDF "}],
            "dupedPlugins": "PDF Viewer Chrome PDF Viewer Chromium PDF Viewer Microsoft Edge PDF Viewer WebKit built-in PDF ||1920-1080-1032-24-*-*-*",
            "screenInfo": "1920-1080-1032-24-*-*-*",
            "referrer": "",
            "userAgent": self.__userAgent,
            "location": "",
            "webDriver": False,
            "capabilities": {"css": {"textShadow": 1, "WebkitTextStroke": 1, "boxShadow": 1, "borderRadius": 1, "borderImage": 1, "opacity": 1, "transform": 1, "transition": 1}, "js": {"audio": True, "geolocation": random.choice([True, False]), "localStorage": "supported", "touch": False, "video": True, "webWorker": random.choice([True, False])}, "elapsed": 1},
            "gpu": {"vendor": gpu["vendor"], "model": gpu["model"], "extensions": gpu["extensions"].split(";")},
            "dnt": None,
            "math": {"tan": "-1.4214488238747245", "sin": "0.8178819121159085", "cos": "-0.5753861119575491"},
            "automation": {"wd": {"properties": {"document": [], "window": [], "navigator": []}}, "phantom": {"properties": {"window": []}}},
            "stealth": {"t1": 0, "t2": 0, "i": 1, "mte": 0, "mtd": False},
            "crypto": {"crypto": 1, "subtle": 1, "encrypt": True, "decrypt": True, "wrapKey": True, "unwrapKey": True, "sign": True, "verify": True, "digest": True, "deriveBits": True, "deriveKey": True, "getRandomValues": True, "randomUUID": True},
            "canvas": {"hash": random.randrange(645172295, 735192295), "emailHash": None, "histogramBins": bins},
            "formDetected": False, "numForms": 0, "numFormElements": 0,
            "be": {"si": False},
            "end": ts + random.randint(1, 5),
            "errors": [],
            "version": self.__FP_VERSION,
            "id": str(uuid.uuid4()),
        }

    def __encodeFingerprint(self, fp: dict) -> tuple:
        payload = json.dumps(fp, separators=(",", ":")).encode("utf-8")
        checksum = self.__crc32(payload)
        combined = checksum.encode("ascii") + b"#" + payload
        return checksum, combined

    def __buildSignalPayload(self) -> tuple:
        fp = self.__generateFingerprint()
        checksum, raw = self.__encodeFingerprint(fp)
        encrypted = self.__aesEncrypt(raw)
        return checksum, encrypted

    @staticmethod
    def __checkDifficulty(digest: bytes, difficulty: int) -> bool:
        full, rem = divmod(difficulty, 8)
        if digest[:full] != b"\x00" * full:
            return False
        if rem and (digest[full] >> (8 - rem)):
            return False
        return True

    def __solveScrypt(self, challengeInput: str, checksum: str, difficulty: int) -> str:
        combined = challengeInput + checksum
        salt = checksum.encode("utf-8")
        for nonce in itertools.count(0):
            password = (combined + str(nonce)).encode("utf-8")
            digest = hashlib.scrypt(password, salt=salt, n=128, r=8, p=1, dklen=16)
            if self.__checkDifficulty(digest, difficulty):
                return str(nonce)

    def __solveSha256(self, challengeInput: str, checksum: str, difficulty: int) -> str:
        combined = (challengeInput + checksum).encode("utf-8")
        for nonce in itertools.count(0):
            digest = hashlib.sha256(combined + str(nonce).encode("utf-8")).digest()
            if self.__checkDifficulty(digest, difficulty):
                return str(nonce)

    def __solveBandwidth(self, challengeInput: str, checksum: str, difficulty: int) -> str:
        sizes = self.__jsConfig.get("bandwidth_sizes") if self.__jsConfig else self.__DEFAULT_BANDWIDTH_SIZES
        size = sizes.get(difficulty, 0x400)
        return base64.b64encode(b"\x00" * size).decode("utf-8")

    @staticmethod
    def __buildMetrics() -> list:
        return [
            {"name": "2", "value": random.uniform(0, 1), "unit": "2"},
            {"name": "100", "value": 0, "unit": "2"}, {"name": "101", "value": 0, "unit": "2"},
            {"name": "102", "value": 0, "unit": "2"}, {"name": "103", "value": 8, "unit": "2"},
            {"name": "104", "value": 0, "unit": "2"}, {"name": "105", "value": 0, "unit": "2"},
            {"name": "106", "value": 0, "unit": "2"}, {"name": "107", "value": 0, "unit": "2"},
            {"name": "108", "value": 1, "unit": "2"}, {"name": "undefined", "value": 0, "unit": "2"},
            {"name": "110", "value": 0, "unit": "2"}, {"name": "111", "value": 2, "unit": "2"},
            {"name": "112", "value": 0, "unit": "2"}, {"name": "undefined", "value": 0, "unit": "2"},
            {"name": "3", "value": 4, "unit": "2"},
            {"name": "7", "value": 0, "unit": "4"},
            {"name": "1", "value": random.uniform(10, 20), "unit": "2"},
            {"name": "4", "value": 36.5, "unit": "2"},
            {"name": "5", "value": random.uniform(0, 1), "unit": "2"},
            {"name": "6", "value": random.uniform(50, 60), "unit": "2"},
            {"name": "0", "value": random.uniform(130, 140), "unit": "2"},
            {"name": "8", "value": 1, "unit": "4"},
        ]

    @staticmethod
    def __extractGokuProps(html: str) -> Optional[dict]:
        m = re.search(r"window\.gokuProps\s*=\s*(\{.*?\})\s*;", html, re.DOTALL)
        return json.loads(m.group(1)) if m else None

    @staticmethod
    def __extractWafHost(html: str) -> str:
        m = re.search(r'src="https://([^"]+)/challenge[^"]*\.js"', html)
        if not m:
            raise ValueError("challenge.js src not found in page")
        return m.group(1)

    @staticmethod
    def __extractChallengeJsUrl(html: str) -> Optional[str]:
        m = re.search(r'src="(https://[^"]+/challenge[^"]*\.js)"', html)
        return m.group(1) if m else None

    @staticmethod
    def __extractDomain(url: str) -> str:
        h = urlparse(url).hostname or url
        return h if h.startswith("www.") else "www." + h

    @staticmethod
    def __parseChallengeJs(jsText: str) -> dict:
        challengeTypes = {}
        for m in re.finditer(r"'(h[0-9a-f]{8,})'[+].*?=\s*'((?:mp_)?verify)'", jsText):
            challengeTypes[m.group(1)] = m.group(2)

        mpSolutionField, mpMetadataField = "solution_data", "solution_metadata"
        fieldMatch = re.search(r"'verify'\s*,\s*'\w+'\s*:\s*'(solution_\w+)'\s*,\s*'\w+'\s*:\s*'(solution_\w+)'", jsText)
        if fieldMatch:
            mpSolutionField = fieldMatch.group(1)
            mpMetadataField = fieldMatch.group(2)

        bandwidthSizes = {}
        sizeMatch = re.search(
            r"case\s+0x1:return\s+(0x[0-9a-f]+);"
            r"case\s+0x2:return[^;]*\((0x[0-9a-f]+),(0x[0-9a-f]+)\);"
            r"case\s+0x3:return[^;]*\((0x[0-9a-f]+),(0x[0-9a-f]+)\);"
            r"case\s+0x4:return[^;]*\((0x[0-9a-f]+),(0x[0-9a-f]+)\);"
            r"case\s+0x5:return[^;]*\((0x[0-9a-f]+),(0x[0-9a-f]+)\)", jsText)
        if sizeMatch:
            bandwidthSizes = {
                1: int(sizeMatch.group(1), 16),
                2: int(sizeMatch.group(2), 16) * int(sizeMatch.group(3), 16),
                3: int(sizeMatch.group(4), 16) * int(sizeMatch.group(5), 16),
                4: int(sizeMatch.group(6), 16) * int(sizeMatch.group(7), 16),
                5: int(sizeMatch.group(8), 16) * int(sizeMatch.group(9), 16),
            }

        return {
            "challenge_types": challengeTypes,
            "mp_field_names": (mpSolutionField, mpMetadataField),
            "bandwidth_sizes": bandwidthSizes
        }

    def __getEndpoint(self, challengeType: str) -> str:
        if challengeType == self.__CHALLENGE_BANDWIDTH:
            return "mp_verify"
        if self.__jsConfig:
            ct = self.__jsConfig["challenge_types"]
            if challengeType in ct:
                return ct[challengeType]
            for prefix, endpoint in ct.items():
                if challengeType.startswith(prefix):
                    return endpoint
        return "verify"

    def __getSolver(self, challengeType: str) -> tuple:
        solvers = {
            self.__CHALLENGE_SCRYPT:    (self.__solveScrypt,    "scrypt"),
            self.__CHALLENGE_SHA256:    (self.__solveSha256,    "sha256"),
            self.__CHALLENGE_BANDWIDTH: (self.__solveBandwidth, "bandwidth"),
        }
        if challengeType in solvers:
            return solvers[challengeType]
        if self.__getEndpoint(challengeType) == "mp_verify":
            return (self.__solveBandwidth, "bandwidth")
        raise ValueError(f"Unknown challenge_type: {challengeType}")

    def __solveChallenge(self, html: str = None, session: requests.Session = None) -> tuple:
        session = session or self.__makeSession()
        url = self.__websiteURL
        domain = self.__extractDomain(url)
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.hostname}"
        wafAction = None
        timeout = self._HTTP_TIMEOUT

        if html is None:
            session.headers = self.__pageHeaders()
            resp = session.get(url, timeout=timeout)
            html = resp.text
            wafAction = resp.headers.get("x-amzn-waf-action")

        challengeJsUrl = self.__extractChallengeJsUrl(html)
        if not challengeJsUrl:
            raise RuntimeError(f"No AWS WAF challenge detected on {url}")

        gokuProps = self.__extractGokuProps(html)
        wafHost = self.__extractWafHost(html)

        if challengeJsUrl in self._JS_CONFIG_CACHE:
            self.__jsConfig = self._JS_CONFIG_CACHE[challengeJsUrl]
        else:
            try:
                session.headers = self.__apiHeaders(origin=origin, referer=url)
                jsResp = session.get(challengeJsUrl, timeout=timeout)
                self.__jsConfig = self.__parseChallengeJs(jsResp.text)
                self._JS_CONFIG_CACHE[challengeJsUrl] = self.__jsConfig
            except Exception:
                self.__jsConfig = None

        session.headers = self.__apiHeaders(origin=origin, referer=url)
        inputs = session.get(f"https://{wafHost}/inputs?client=browser", timeout=timeout).json()

        checksum, encryptedSignals = self.__buildSignalPayload()

        challengeType = inputs["challenge_type"]
        difficulty = inputs["difficulty"]
        challenge = inputs["challenge"]
        challengeInput = challenge.get("input", "")

        solverFn, solverName = self.__getSolver(challengeType)
        solution = solverFn(challengeInput, checksum, difficulty)

        endpointName = self.__getEndpoint(challengeType)
        session.headers = self.__apiHeaders(origin=origin, referer=url)

        if endpointName == "mp_verify":
            solutionField, metadataField = (
                self.__jsConfig["mp_field_names"] if self.__jsConfig
                else ("solution_data", "solution_metadata")
            )
            metadata = json.dumps({
                "challenge": challenge,
                "solution": None,
                "signals": [{"name": "Zoey", "value": {"Present": encryptedSignals}}],
                "checksum": checksum,
                "client": "Browser",
                "domain": domain,
                "metrics": self.__buildMetrics(),
                "existing_token": None,
                **({"goku_props": gokuProps} if gokuProps else {}),
            }, separators=(",", ":"))

            mp_headers = {"user-agent": self.__userAgent}
            mp_files = {solutionField: (None, solution), metadataField: (None, metadata)}

            if self.__proxy:
                resp = std_requests.post(
                    f"https://{wafHost}/{endpointName}",
                    files=mp_files,
                    headers=mp_headers,
                    proxies={"https": self.__proxy, "http": self.__proxy},
                    timeout=timeout,
                )
            else:
                session.headers = mp_headers
                resp = session.post(f"https://{wafHost}/{endpointName}", files=mp_files, timeout=timeout)
            result = resp.json()
        else:
            payload = {
                "challenge": challenge,
                "checksum": checksum,
                "solution": solution,
                "signals": [{"name": "Zoey", "value": {"Present": encryptedSignals}}],
                "existing_token": None,
                "client": "Browser",
                "domain": domain,
                "metrics": self.__buildMetrics()
            }
            session.headers = {**self.__apiHeaders(origin=origin, referer=url), "content-type": "text/plain;charset=UTF-8"}
            resp = session.post(f"https://{wafHost}/verify", json=payload, timeout=timeout)
            result = resp.json()

        if "token" not in result:
            raise RuntimeError(f"No token in response: {result}")

        challengeInfo = {
            "solver": solverName,
            "endpoint": f"/{endpointName}",
            "wafAction": wafAction or "challenge"
        }

        return result["token"], challengeInfo
