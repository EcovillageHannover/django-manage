# coding: utf-8

from django.db import models
import base64
import hmac
import hashlib
# Create your models here.

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

def make_username(vorname, nachname):
    a = vorname.split(" ")[0]
    b = nachname.split(" ")[-1]
    username = f"{a}.{b}".lower()
    repl = { 'ö': 'oe', 'ä': 'ae', 'ü': 'ue', 'ß': 'ss', 'ã': 'a', ' ': '_' }
    for k,v in repl.items():
        username = username.replace(k,v)
    return username
