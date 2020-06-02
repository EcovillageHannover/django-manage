# coding: utf-8

import base64
import hmac
import hashlib
import ldap
# Create your models here.

from django.db import models
from django.db.models.manager import Manager
from django.contrib.auth import get_user_model
from django.db.models import Count

from taggit.managers import TaggableManager

import datetime

# Create your models here.
class Invite(models.Model):
    md5 = models.CharField(max_length=255, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    count = models.IntegerField(default=0)


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


def ldap_users(config):
    conn = ldap.initialize(config.AUTH_LDAP_SERVER_URI)
    conn.simple_bind_s(config.AUTH_LDAP_BIND_DN, config.AUTH_LDAP_BIND_PASSWORD)
    ret = conn.search_s(config.AUTH_LDAP_USER_DN,
                      ldap.SCOPE_SUBTREE,
                      "(objectClass=inetOrgPerson)",
                      ["cn", "mail", "displayName", 'memberOf']
    )
    ret = {x['cn'][0].decode(): x for dn, x in ret}
    for dn in ret:
        groups = [x.decode().split(',')[0].split('=')[1] for x in ret[dn].get('memberOf', [])]
        ret[dn]['groups'] = groups
    return ret
