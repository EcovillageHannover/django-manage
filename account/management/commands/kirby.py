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
    def add_arguments(self, parser):
        parser.add_argument("--user", '-u', default=None,
                            help="Update only User")

        parser.add_argument("--group", '-g', default=None,
                            help="Update only Groyp")

    def handle(self, *args, **options):
        users = ldap_users()

        for username, user in users.items():
            if (options['user'] or options['group']) and \
               (options['user'] != "all" and username != options['user']):
                continue
            user_changed.send(sender=self.__class__, username=username)

        for group in LDAP().groups():
            if (options['user'] or options['group']) and \
               (options['group'] != "all" and group != options['group']):
                continue
            group_changed.send(sender=self.__class__, group=group)
