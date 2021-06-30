# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from collections import defaultdict
from django_auth_ldap.backend import LDAPBackend

from account.models import *
from account.mailman import Mailman
from account import signals

import evh.settings_local as config
import csv
import os

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync Account/Group Information with outside world'
    def add_arguments(self, parser):
        parser.add_argument("--mode", default="ecotopia")


    def read_csv(self):
        fn = self.options['mode'] + ".csv"
        with open(fn) as fd:
            while True: # Skip 3 Lines
                keys = fd.readline().strip().split(",")
                if 'Mitgliedsnummer' in keys:
                    break
            genossen = []
            for g in csv.DictReader(fd, fieldnames=keys):
                if g.get('Mitgliedsnummer'):
                    genossen.append(g)

        logger.info("Read in %d Genossen", len(genossen))
        return genossen

    def scan_mailaddresses(self, genossen):
        mail_addresses = defaultdict(lambda: [set(), None])
        for g in genossen:
            email = g['E-Mail-Adresse'].strip().lower()
            mail_addresses[email][0].add(g['Mitgliedsnummer'])

        for email,(mnrs,_) in list(mail_addresses.items()):
            if len(mnrs) > 1:
                logger.info("Familienmailaddresse: %s (mitglieder=%s)", email, mnrs)
        return mail_addresses


    def match_against_django(self, genossen, mail_addresses):
        UserModel = get_user_model()

        snowflakes = {} # Mail -> Username
        with open('invites/snowflakes.csv') as fd:
            sfs = csv.DictReader(fd)
            for sf in sfs:
                snowflakes[sf['mail'].lower().strip()] = sf['username'].strip().lower()

        ################################################################
        # Open File for Invites
        invite_fd = open(f'invites/{self.options["mode"]}.csv', 'w+')
        invites = csv.DictWriter(invite_fd, fieldnames=['vorname', 'nachname', 'email', 'username'])
        invites.writeheader()

        genossen_users = {}
        for g in genossen:
            email = g['E-Mail-Adresse'].strip().lower()
            mnr = int(g['Mitgliedsnummer'], 10)
            if not email:        continue
            if not '@' in email: continue

            if email in snowflakes:
                username = snowflakes[email]
            else:
                username = make_username(g['Vorname'].strip(), g['Familienname'].strip())


            try: # 1. Try: by username
                user = UserModel.objects.get(username=username)
            except UserModel.DoesNotExist:
                assert email in mail_addresses
                if len(mail_addresses[email][0]) == 1:
                    # Generate an invite
                    invites.writerow(dict(
                        vorname=g['Vorname'],
                        nachname=g['Familienname'],
                        email=email,
                        username=username
                    ))

                else:
                    print(f"Not found and no invite: {username} ({email})")
                continue

            genossen_users[user] = g

            if not hasattr(user, 'userprofile'):
                x = UserProfile.objects.create(user=user)
                x.save()

            if email.lower() not in (user.email.lower(), user.userprofile.recovery_mail.lower()):
                logger.info("User %s exists, but cannot connect to mail %s", username, email)
                continue
            else:
                mail_addresses[email.lower()][1] = user

            ################################################################
            # We found a user!
            if self.options['mode'] == 'ecovillage':
                if mnr != user.userprofile.evh_mitgliedsnummer:
                    user.userprofile.evh_mitgliedsnummer = mnr
                    user.userprofile.save()
                    logger.info("Mitgliedsnummer of %s = %d (%s, %s)", user, mnr, g['Vorname'], g['Familienname'])

        return genossen_users

    def handle(self, *args, **options):
        UserModel = get_user_model()

        self.options = options



        genossen = self.read_csv()

        mail_addresses = self.scan_mailaddresses(genossen)

        genossen_users = self.match_against_django(genossen, mail_addresses)

        ################################################################
        # Check Group Memberships in both directions
        if self.options['mode'] == 'ecotopia':
            django_group = Group.objects.get(name='ecotopia-mitglieder')
        elif self.options['mode'] == 'ecovillage':
            django_group = Group.objects.get(name='genossenschaft')

        django_group_members = django_group.user_set.all()
        for user in django_group_members:
            if user not in genossen_users:
                logger.warning(f'LDAP > CSV: User {user} is in LDAP group but not in CSV')

        logging.info(f"{len(django_group_members)} users in group {django_group}")

        for user in genossen_users:
            if user not in django_group_members:
                logger.warning(f'CSV > LDAP: User {user} is in CSV group but not in LDAP')
                signals.group_member_add.send(sender=self.match_against_django,
                                              group=django_group,
                                              member=user)

        ################################################################
        # Subscribe to genossenschaft und genossenschaft-news
        mailman = Mailman()
        subscribers = [v[1] or k.lower() for k, v in mail_addresses.items() if '@' in k]

        if self.options['mode'] == 'ecotopia':
            list_mitglieder = ('ecotopia-mitglieder', 'Ecotopia Mitglieder')
            list_news =       None # Uncomment if desired('ecotopia-news',       'Ecotopia Newsletter')
        elif self.options['mode'] == 'ecovillage':
            list_mitglieder = ('genossenschaft-mitglieder', 'EVH Mitglieder')
            list_news = ('genossenschaft-news', 'EVH Newsletter')

        # Rundbrief
        if list_mitglieder:
            mlist = mailman.get_list(list_mitglieder[0])
            mailman.config_list(django_group,
                                mlist, type="news",
                                display_name=list_mitglieder[1],
                                subject_prefix=f"[{list_mitglieder[1]}] ",
                                )
            mailman.sync_list(mlist, members=subscribers, strict=True)

        # Newsletter
        if list_news:
            mlist = mailman.get_list(list_news[0])
            mailman.config_list(django_group,
                                mlist, type="news",
                                display_name=list_news[1],
                                subject_prefix=f"[{list_news[1]}] ",
                                )
            mailman.sync_list(mlist, members=subscribers, strict=False)
