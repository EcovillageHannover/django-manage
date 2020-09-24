import base64
import hmac
import hashlib

def format_token(key, fields):
    payload = ("|".join(fields)).encode('utf-8')
    signature = hmac.new(key.encode(), payload, digestmod=hashlib.md5).digest()
    msg = signature + payload
    return base64.urlsafe_b64encode(msg)


def parse_token(key, token):
    msg = base64.urlsafe_b64decode(token)
    signature_got, payload = msg[:16], msg[16:]
    signature_own = hmac.new(key.encode(), payload, digestmod=hashlib.md5).digest()
    if signature_own != signature_got:
        raise RuntimeError("Signature mismatch")

    return [x.decode('utf-8') for x in payload.split(b'|')]
