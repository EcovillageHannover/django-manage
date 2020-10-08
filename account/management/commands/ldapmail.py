# coding: utf-8
from django.core.management.base import BaseCommand, CommandError

import hashlib
from collections import namedtuple, defaultdict
import evh.settings_local as config
from account.models import *

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Debug LDAP Mailconfiguration'

    def add_arguments(self, parser):
        parser.add_argument("--addresses", '-a', action='store_true', default=False,
                            help="Dump Mailaddress->Mailbox Configuration")
        parser.add_argument("--aliases", '-A', action='store_true', default=False,
                            help="Dump Mailaddress->Mailbox Configuration")

    def __get_cn(self, dn):
        first = dn.split(",")[0]
        assert first.startswith("cn=")
        return first.split("=",1)[1]

    def query_mailboxes(self):
        L = LDAP()
        
        ret = L.conn.search_s(settings.AUTH_LDAP_BASE_DN,
                                 ldap.SCOPE_SUBTREE,
                                 "(|(mailEnable=TRUE)(mailalias=*))", ["cn", "mail", "mailalias"])

        mailboxes = defaultdict(lambda: defaultdict(list))
        for dn, entry in ret:
            box = self.__get_cn(dn)
            for alias in entry.get('mailalias', []):
                mailboxes[box]['alias'].append(alias.decode())
            for address in entry.get('mail', []):
                mailboxes[box]['address'].append(address.decode())


        return mailboxes

    def dump_mailboxes(self):
        mailboxes = self.query_mailboxes()

        for name, properties in sorted(mailboxes.items()):
            print(f"Mailbox: {name}")
            print(f"  Addresses: {properties['address']}")
            if properties['alias']:
                print(f"  Alias: {properties['alias']}")

            print()

    def dump_addresses(self, addresses, aliases):
        mailboxes = self.query_mailboxes()
        conf = {}
        for name, properties in sorted(mailboxes.items()):
            addrs = []
            if addresses:
                addrs += properties['address']
            if aliases:
                addrs += properties['alias']
            for addr in addrs:
                conf[addr] = name

        for addr,name in sorted(conf.items()):
            print(addr, "->", name)

    def handle(self, *args, **options):
        if options['addresses'] or options['aliases']:
            self.dump_addresses(addresses=options['addresses'], aliases=options['aliases'])
            return
        else:
            self.dump_mailboxes()
