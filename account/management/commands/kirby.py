# coding: utf-8

from django_auth_ldap.backend import LDAPBackend
from django.core.management.base import BaseCommand, CommandError
from account.models import *
import evh.settings_local as config
from pathlib import Path
from account.signals import *
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

        for group in LDAP().groups():
            group_changed.send(sender=self.__class__, group=group)
