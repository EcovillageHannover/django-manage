# coding: utf-8

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
import hashlib
from account.models import *
import csv
from collections import namedtuple
import evh.settings_local as config
from django.urls import reverse
from django.template.loader import render_to_string

import logging
logger = logging.getLogger(__name__)

AccountInformation = namedtuple('AccountInformation',
                                ['vorname',
                                 'nachname',
                                 'username',
                                 'email',
                                 'group', # Optional
                                 ])

def read_csv(fn, encoding=None):
    with open(fn, encoding=encoding) as fd:
        group = []
        for record in csv.DictReader(fd):
            for field in record:
                if record[field]:
                    record[field] = record[field].strip()

            if record['vorname'].startswith("#"):
                if 'group' in record['vorname'] and '=' in record['vorname']:
                    group = record['vorname'].lstrip('#').split("=")[1].strip()
                    if not group:
                        group = []
                    else:
                        group = [group.lower()]
                continue

            if not record.get('username'):
                record['username'] = make_username(
                    record['vorname'],
                    record['nachname']
                )
            yield AccountInformation(**record, group=group)

def send_invite_mail(account, msgid=False, preface=None):
    fields = ['create', account.vorname, account.nachname, account.username, account.email]
    token = format_token(config.SECRET_KEY, fields)
    assert fields == parse_token(config.SECRET_KEY, token)
    token = token.decode('utf-8')

    context = dict(
        config=config,
        token=token,
        url=config.ACCOUNT_URL + token,
        **account._asdict(),
        preface=preface
    )

    msg_plain = render_to_string('registration/invite.txt', context)
    msg_html = render_to_string('registration/invite.html', context)

    receiver = "{vorname} {nachname} <{email}>".format(**context)
    headers = {}
    if msgid: headers['References'] = msgid

    msg = EmailMultiAlternatives(subject="[EVH Account] Link zur Account-Erstellung",
                                 body=msg_plain,
                                 from_email=config.EMAIL_FROM,
                                 to=[receiver],
                                 reply_to=[config.EMAIL_FROM],
                                 headers=headers)
    msg.attach_alternative(msg_html, "text/html")
    msg.send()

    invite,creates = Invite.objects.get_or_create(
        md5=hashlib.md5(account.email.lower().encode('utf-8')).hexdigest(),
    )
    invite.count += 1
    invite.save()

    print(f"Sent mail to: {receiver} (try: {invite.count})")




class Command(BaseCommand):
    help = 'Send account invite mails'

    def add_arguments(self, parser):
        # Sources
        parser.add_argument("--source:csv", help="CSV-File")
        parser.add_argument("--source:csv:encoding", help="special CSV encoding")
        parser.add_argument("--source:argv", help="vorname,nachname,email,username")

        # Modify
        parser.add_argument("--modify:override", help="Python file to override")
        parser.add_argument("--modify:group", help="Add group to all users")

        # Filters
        parser.add_argument("--filter:group", '--group', metavar="GROUP",
                            help="Send mail only to group")
        parser.add_argument("--filter:resend",  metavar="USERNAME",
                            help="Resend the Mail although the user already has an account")

        # Actions
        parser.add_argument('--action:list', help="actually send the mails",
                            action="store_true", required=False)
        parser.add_argument('--action:group', help="Add existing users to groups",
                            action="store_true", required=False)
        parser.add_argument('--action:send', help="actually send the mails",
                            action="store_true", required=False)

        parser.add_argument('--send:preface', help="Preface Message for the Account Mail",
                            metavar='FILE', required=False)
        parser.add_argument('--send:msgid', help="In reply to MSGID!",
                            metavar='MSGID', required=False)


    def handle(self, *args, **options):
        if options['source:csv']:
            accounts = list(read_csv(options['source:csv'], encoding=options['source:csv:encoding']))
        elif options['source:argv']:
            info = [x.strip() for x in options['source:argv'].split(",")]
            if len(info) == 3:
                info.append(make_username(info[0],info[1]))
            accounts = [AccountInformation(vorname=info[0],nachname=info[1],email=info[2],
                                           username=info[3],group=None)]

        logger.info("Read %s Accounts", len(accounts))

        if options['modify:override']:
            import importlib.util
            spec = importlib.util.spec_from_file_location("override", options['modify:override'])
            foo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(foo)

            accounts = [foo.override(a) for a in accounts]
            accounts = [a for a in accounts if a]

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
                if missing_groups:
                    logger.warning("User %s is not in groups %s",
                                   a.username, missing_groups)
                if options['action:group']:
                    for group in missing_groups:
                        ldap_addgroup(a.username, group)
                        
        ################################################################
        # Filter!
        if options['filter:group']:
            accounts = [a for a in accounts if options['filter:group'] in a.group]


        if options['action:list']:
            pass
        elif options['filter:resend']:
            accounts = [a for a in accounts
                        if options['filter:resend'] in (a.username, a.group)]
        else:
            # Remove all existing users
            accounts = [a for a in accounts if a.username not in existing_users]

        logger.info("after filtering: %s accounts", len(accounts))

        ################################################################
        # Send and List
        if options['action:send']:
            print(f"Empfänger({len(accounts)})", repr([a.email for a in accounts]))
            answer = input(f"Do you want to send {len(accounts)} mails? (y/N)> ")
            if answer != 'y':
                print("Not sending anything...\n\n")
                return

            if options['send:preface']:
                with open(options['send:preface']) as fd:
                    preface = fd.read()
            else:
                preface=None

            for account in accounts:
                send_invite_mail(account, msgid=options['send:msgid'], preface=preface)
        else:
            for a in accounts:
                name = a.vorname + ' ' +a.nachname
                exists = ' ' 
                if a.username in existing_users:
                    exists = 'x'
                    recorded_mail = existing_users[a.username]['mail'][0].decode()
                    if recorded_mail != a.email and not (
                            'my-evh' in recorded_mail or 'ecovillage' in recorded_mail
                    ):
                        logger.error("Not matching email-addresses for existing account %s != %s",
                                       a, recorded_mail)
                exists = {False: ' ', True: 'x'}[a.username in existing_users]
                print(f"{exists} {name:<30} {'('+a.username+')':<30} {a.email} {a.group}")
