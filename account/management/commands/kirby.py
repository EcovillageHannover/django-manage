# coding: utf-8

from django_auth_ldap.backend import LDAPBackend
from django.core.management.base import BaseCommand, CommandError
from account.models import *
import evh.settings_local as config
from pathlib import Path
from account.signals import user_changed
from datetime import datetime
import os

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update Kirby Accounts'

    def handle(self, *args, **options):
        users = ldap_users()
        for username, user in users.items():
            user_changed.send(sender=self.__class__, username=username)
        #for username, user in users.items():
        #    date = datetime.strptime(user["createTimestamp"][0].decode()[:8], "%Y%m%d")
        #    if date.month != 6:
        #        print("{} <{}>,".format(user['displayName'][0].decode(), user['mail'][0].decode()))
