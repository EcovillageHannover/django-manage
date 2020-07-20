# coding: utf-8

from django_auth_ldap.backend import LDAPBackend
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
import hashlib
from account.models import *
import csv
from collections import namedtuple
import evh.settings_local as config
from django.urls import reverse
from django.template.loader import render_to_string
from account.signals import user_changed

from .invite  import read_csv


import logging
logger = logging.getLogger(__name__)

    



class Command(BaseCommand):
    help = 'Send account invite mails'

    def add_arguments(self, parser):
        # Sources
        parser.add_argument("--source:csv", help="CSV-File")
        parser.add_argument("--source:csv:encoding", help="special CSV encoding")

        # Modify
        parser.add_argument("--modify:group", help="Add group to all users")

        # Filters
        parser.add_argument("--filter:group", '--group', metavar="GROUP",
                            help="Send mail only to group")
        parser.add_argument("--filter:all", metavar="GROUP",
                            help="No filters")

        parser.add_argument('--action:send', help="actually send the mails",
                            action="store_true", required=False)


        parser.add_argument('--send:msgid', help="In reply to MSGID!",
                            metavar='MSGID', required=False)

        parser.add_argument('--msg', help="Message Template",
                            metavar='FILE', required=True)
        parser.add_argument('--subject', help="Subject",
                            metavar='SUBJECT', required=True)


    def send_nachricht(self, account,  msgid=False):
        context = {
            **account._asdict(),
        }
        context['fullname'] = f"{account.vorname} {account.nachname}"

        receiver = "{vorname} {nachname} <{email}>".format(**context)
        receiver = receiver.replace(",", " ")
        headers = {}
        if self.options['send:msgid']:
            headers['References'] = self.options['send:msgid']

        from django.template import engines
        django_engine = engines['django']
        template = django_engine.from_string(open(self.options['msg']).read())
        msg_plain = template.render(context)

        msg = EmailMultiAlternatives(subject="[EVH] " + self.options['subject'],
                                     body=msg_plain,
                                     from_email=config.EMAIL_FROM,
                                     #to=['support@my-evh.de'],
                                     to=[receiver, 'support@my-evh.de'],
                                     reply_to=[config.EMAIL_FROM],
                                     headers=headers)
        if self.do_send_mail:
            msg.send()
            print(f"Sent mail to: {receiver}")
        else:
            print(receiver)

    def handle(self, *args, **options):
        self.options = options
        accounts = list(read_csv(options['source:csv'], encoding=options['source:csv:encoding']))

        logger.info("Read %s Accounts", len(accounts))

        if options['modify:group']:
            for a in accounts:
                if options['modify:group'] not in a.group:
                    a.group.append(options['modify:group'])

        existing_users = ldap_users()
        ################################################################
        # Sanity Checks
        usernames = set()
        for a in accounts:
            assert a.username not in usernames, "Duplicate Username: %s" % a.username
            usernames.add(a.username)

        for a in accounts:
                ldap_user = existing_users.get(a.username)
                if not ldap_user: continue
                missing_groups = set(a.group) - set(ldap_user['groups'])

        ################################################################
        # Filter!
        if options['filter:group']:
            accounts = [a for a in accounts if options['filter:group'] in a.group]


        ################################################################
        # Send and List
        self.do_send_mail = False
        if options['action:send']:
            print(f"Empfänger({len(accounts)})", repr([a.email for a in accounts]))
            answer = input(f"Do you want to send {len(accounts)} mails? (y/N)> ")
            if answer != 'y':
                print("Not sending anything...\n\n")
                return

            self.do_send_mail = True

        for account in accounts:
            self.send_nachricht(account)
        
