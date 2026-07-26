import base64, os, struct
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA1

class CseAmazon:
    __ALGORITHM_ID = 0x0014
    __VERSION = 1
    __TYPE = 128

    def __init__(self, jwk_n: str, key_id: str, provider_id: str = "si:md5") -> None:
        self.__jwkN = jwk_n
        self.__keyId = key_id
        self.__providerId = provider_id

    def encrypt(self, password: str) -> dict:
        try:
            enc1 = self.__encryptMessage(password)
            enc2 = self.__encryptMessage(password)
            return {
                'status': True,
                'payload': password,
                'encryptedPassword': base64.b64encode(enc1).decode('utf-8'),
                'encryptedPasswordCheck': base64.b64encode(enc2).decode('utf-8'),
            }
        except Exception as error:
            return {'status': False, 'description': str(error)}

    def __b64UrlDecode(self, s: str) -> bytes:
        return base64.urlsafe_b64decode(s + "=" * ((4 - len(s) % 4) % 4))

    def __importPublicKey(self):
        n = int.from_bytes(self.__b64UrlDecode(self.__jwkN), 'big')
        e = int.from_bytes(self.__b64UrlDecode('AQAB'), 'big')
        return RSA.construct((n, e))

    def __serializeEncryptionContext(self, context: dict) -> bytes:
        if not context:
            return struct.pack('>H', 0)
        items = sorted(context.items())
        result = struct.pack('>H', len(items))
        for key, value in items:
            kb, vb = key.encode('utf-8'), value.encode('utf-8')
            result += struct.pack('>H', len(kb)) + kb + struct.pack('>H', len(vb)) + vb
        return result

    def __serializeEncryptedDataKey(self, provider_id: str, key_id: str, encrypted_key: bytes) -> bytes:
        pb = provider_id.encode('utf-8')
        kb = key_id.encode('utf-8')
        return (
            struct.pack('>H', len(pb)) + pb +
            struct.pack('>H', len(kb)) + kb +
            struct.pack('>H', len(encrypted_key)) + encrypted_key
        )

    def __buildHeaderIv(self) -> bytes:
        return bytes(12)

    def __buildFrameIv(self, seq: int) -> bytes:
        return struct.pack('>Q', 0) + struct.pack('>I', seq)

    def __encryptMessage(self, password: str) -> bytes:
        message_id = os.urandom(16)
        data_key = os.urandom(16)

        public_key = self.__importPublicKey()
        oaep_cipher = PKCS1_OAEP.new(public_key, hashAlgo=SHA1)
        encrypted_data_key = oaep_cipher.encrypt(data_key)

        edk_serialized = self.__serializeEncryptedDataKey(
            self.__providerId, self.__keyId, encrypted_data_key
        )

        header = bytearray()
        header.append(self.__VERSION)
        header.append(self.__TYPE)
        header.extend(struct.pack('>H', self.__ALGORITHM_ID))
        header.extend(message_id)
        header.extend(self.__serializeEncryptionContext({}))
        header.extend(struct.pack('>H', 1))
        header.extend(edk_serialized)
        header.append(2)
        header.extend(struct.pack('>I', 0))
        header.append(12)
        header.extend(struct.pack('>I', len(password) + 1))

        raw_header = bytes(header)

        header_iv = self.__buildHeaderIv()
        header_cipher = AES.new(data_key, AES.MODE_GCM, nonce=header_iv)
        header_cipher.update(raw_header)
        _, header_auth_tag = header_cipher.encrypt_and_digest(b'')

        password_bytes = password.encode('utf-8')
        frame_iv = self.__buildFrameIv(1)

        final_frame_marker = struct.pack('>I', 0xFFFFFFFF)
        seq_num_bytes = struct.pack('>I', 1)
        content_len_bytes = struct.pack('>I', len(password_bytes))

        frame_cipher = AES.new(data_key, AES.MODE_GCM, nonce=frame_iv)
        ciphertext, frame_tag = frame_cipher.encrypt_and_digest(password_bytes)
        encrypted_content = ciphertext + frame_tag

        return (
            raw_header +
            header_iv +
            header_auth_tag +
            final_frame_marker +
            seq_num_bytes +
            frame_iv +
            content_len_bytes +
            encrypted_content
        )
# Modificado a Pycryptodome 
