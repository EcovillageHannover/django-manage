# coding: utf-8

import base64
import hmac
import os
import hashlib
import ldap
# Create your models here.

from django.db import models
import django.dispatch
from django.db.models.manager import Manager
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count
from django.conf import settings
from collections import namedtuple
from taggit.managers import TaggableManager
from django.core.signals import request_finished
from django_auth_ldap.backend import LDAPBackend

import logging
logger = logging.getLogger(__name__)

import datetime

# Create your models here.
class Invite(models.Model):
    md5 = models.CharField(max_length=255, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    count = models.IntegerField(default=0)
    groups = models.TextField(blank=True)

    @staticmethod
    def find_by_mail(email):
        md5 = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
        invite, created = Invite.objects.get_or_create(md5=md5)
        return invite

class GroupProfile(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE)
    mailinglist_intern = models.BooleanField(default=False)
    mailinglist_announce = models.BooleanField(default=False)


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
    if ',' in nachname:
        nachname = nachname.split(",")[0]
    b = nachname.split(" ")[-1]
    username = f"{a}.{b}".lower()
    repl = { 'ö': 'oe', 'ä': 'ae', 'ü': 'ue', 'ß': 'ss', 'ã': 'a', ' ': '_' }
    for k,v in repl.items():
        username = username.replace(k,v)
    assert username.encode('ascii').decode('ascii') == username
    return username


################################################################
# LDAP
ldap_conn = None
def ldap_connect():
    global ldap_conn
    if not ldap_conn:
        ldap_conn = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
        ldap_conn.simple_bind_s(settings.AUTH_LDAP_BIND_DN, settings.AUTH_LDAP_BIND_PASSWORD)
    return ldap_conn

from django.core.signals import request_finished

@django.dispatch.receiver(request_finished) 
def ldap_close_connection(*args, **kwargs):
    global ldap_conn
    if ldap_conn is not None:
        logger.info("Close own ldap_connect connection %s", ldap_conn)
        ldap_conn.unbind_s()
        ldap_conn = None



def __get_cn(dn):
    return dn.decode().split(',')[0].split('=')[1]

def ldap_users():
    conn = ldap_connect()
    ret = conn.search_s(settings.AUTH_LDAP_USER_DN,
                      ldap.SCOPE_SUBTREE,
                      "(objectClass=inetOrgPerson)",
                      ["cn", "mail", "displayName", 'memberOf', 'createTimestamp']
    )
    ret = {x['cn'][0].decode(): x for dn, x in ret}
    for dn in ret:
        groups = [x.decode().split(',')[0].split('=')[1] for x in ret[dn].get('memberOf', [])]
        ret[dn]['groups'] = groups
    return ret

class LDAP:
    def __init__(self):
        # self.conn is a well known name
        self.conn = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
        self.conn.simple_bind_s(settings.AUTH_LDAP_BIND_DN,
                                settings.AUTH_LDAP_BIND_PASSWORD)

    def __del__(self):
        logger.info("Close LDAP() Connection")
        fd = self.conn.fileno()
        self.conn.unbind_s()

    def __from_user(self, entry):
        User = namedtuple("LDAPUser", ["vorname", "nachname", "username", "mail"])
        mapping = [("cn", "username"), ("givenName", "vorname"),
                   ("sn", "nachname"), ("mail", "mail")]
        return {t: entry.get(f, [b""])[0].decode() for f,t in mapping}

    def groups(self):
        ldap_filter = f"{settings.AUTH_LDAP_GROUP_DN}"
        ret = self.conn.search_s(settings.AUTH_LDAP_GROUP_DN,
                                 ldap.SCOPE_SUBTREE,
                                 "(|(objectClass=groupOfNames)(objectClass=groupOfURLs))", ["cn"])
        return [e["cn"][0].decode() for dn, e in ret]

    def owned_groups(self, user):
        ldap_filter = f"(owner=cn={user},{settings.AUTH_LDAP_USER_DN})"
        ret = self.conn.search_s(settings.AUTH_LDAP_GROUP_DN,
                                 ldap.SCOPE_SUBTREE,
                                 ldap_filter,
                                 ["cn"])


        groups = []
        for dn, obj in ret:
            group_name = obj['cn'][0].decode()
            group,_ = Group.objects.get_or_create(name=group_name)
            groups.append(group)
        return groups

    def group_owners(self, group):
        ret = self.conn.search_s(settings.AUTH_LDAP_GROUP_DN,
                                 ldap.SCOPE_SUBTREE,
                                 f"cn={group}", ["owner"])

        owners = [x.decode().split(",")[0].split("=")[1] for x in ret[0][1].get('owner', [])]
        owners = list(map(self.search_user, owners))
        return owners


    def group_members(self, group):
        ldap_filter = f"(memberOf=cn={group},{settings.AUTH_LDAP_GROUP_DN})"
        ret = self.conn.search_s(settings.AUTH_LDAP_USER_DN,
                                 ldap.SCOPE_SUBTREE,
                                 ldap_filter,
                                 ["cn", "givenName", "sn", "mail"])

        return sorted([self.__from_user(entry) for _, entry in ret],
                      key=lambda x: x["username"])

    def search_user(self, term):
        ldap_filter = f"(|(cn={term})(mail={term}))"
        ret = self.conn.search_s(settings.AUTH_LDAP_USER_DN,
                                 ldap.SCOPE_SUBTREE,
                                 ldap_filter,
                                 ["cn", "givenName", "sn", "mail"])

        if len(ret) == 1:
            return self.__from_user(ret[0][1])

    def group_member_change(self, group, username, mode="add"):
        group_dn = f"cn={group},{settings.AUTH_LDAP_GROUP_DN}"
        user_dn = f"cn={username},{settings.AUTH_LDAP_USER_DN}"
        if mode == "add":
            modlist = [(ldap.MOD_ADD, 'member', [user_dn.encode()])]
        elif mode == "remove":
            modlist = [(ldap.MOD_DELETE, 'member', [user_dn.encode()])]
        else:
            raise RuntimeError(f"Invalid mode: {mode}")

        try:
            self.conn.modify_s(group_dn, modlist)
            logger.info(f"{mode}: user {username} in group {group} ")
            return True
        except Exception as e:
            logger.error(f"Could not {mode} user {username} in group {group}: {e}")
            return False


def ldap_addgroup(username, group):
    conn = ldap_connect()
    group_dn = f"cn={group},{settings.AUTH_LDAP_GROUP_DN}"
    user_dn = f"cn={username},{settings.AUTH_LDAP_USER_DN}"

    modlist = [(ldap.MOD_ADD, 'member', [user_dn.encode()])]
    try:
        conn.modify_s(group_dn, modlist)
        logger.info("Added user %s to group %s", username, group)
        return True
    except Exception as e:
        logger.error("Could not add user %s to group %s: %s", username, group, e)
    return False
