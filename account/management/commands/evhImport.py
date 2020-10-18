# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from collections import defaultdict

from account.models import *
from account.mailman import Mailman
import evh.settings_local as config
import csv
import os

import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync Account/Group Information with outside world'
    def add_arguments(self, parser):
        parser.add_argument("--csv", '-c', default="genossen.csv",
                            help="CSV to Read")

    def handle(self, *args, **options):
        UserModel = get_user_model()

        snowflakes = {} # Mail -> Username
        with open('invites/snowflakes.csv') as fd:
            sfs = csv.DictReader(fd)
            for sf in sfs:
                snowflakes[sf['mail'].lower().strip()] = sf['username'].strip().lower()


        genossen_users = {}

        invite_fd = open('invites/genossenschaft.csv', 'w+')
        invites = csv.DictWriter(invite_fd, fieldnames=['vorname', 'nachname', 'email', 'username'])
        invites.writeheader()

        mail_addresses = defaultdict(lambda: [0, None])
        with open(options['csv']) as fd:
            genossen = csv.DictReader(fd)
            for g in genossen:
                email = g['E-Mail-Adresse'].strip().lower()
                mail_addresses[email][0] += 1

        for email,(count,_) in list(mail_addresses.items()):
            if count > 1:
                logger.info("Familienmailaddresse: %s (mitglieder=%d)", email, count)

        with open(options['csv']) as fd:
            genossen = csv.DictReader(fd)
            for g in genossen:
                email = g['E-Mail-Adresse'].strip()
                mnr = int(g['Mitgliedsnummer'], 10)
                if not email: continue
                if not '@' in email: continue

                if email in snowflakes:
                    username = snowflakes[email]
                else:
                    username = make_username(g['Vorname'].strip(), g['Familienname'].strip())

                try: # 1. Try: by username
                    user = UserModel.objects.get(username=username)
                except UserModel.DoesNotExist:
                    if mail_addresses[email] == 1:
                        # Generate an invite
                        invites.writerow(dict(
                            vorname=g['Vorname'],
                            nachname=g['Familienname'],
                            email=email,
                            username=snowflakes.get(email)
                        ))
                    # print(f"Not found: {username} ({email})")
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
                
                # 1. Set the Mitgliedsnummer
                if mnr != user.userprofile.evh_mitgliedsnummer:
                    user.userprofile.evh_mitgliedsnummer = mnr
                    user.userprofile.save()
                    logger.info("Mitgliedsnummer of %s = %d (%s, %s)", user, mnr, g['Vorname'], g['Familienname'])

                # 2. Replace
                

        ################################################################
        # Check Group Memberships in both directions
        django_group = Group.objects.get(name='genossenschaft')
        django_group_members = django_group.user_set.all()
        for user in django_group_members:
            if user not in genossen_users:
                logger.warning(f'LDAP > CSV: User {user} is in LDAP group but not in CSV')

        for user in genossen_users:
            if user not in django_group_members:
                logger.warning(f'CSV > LDAP: User {user} is in CSV group but not in LDAP')

        ################################################################
        # Subscribe to genossenschaft und genossenschaft-news
        mailman = Mailman()
        subscribers = [v[1] or k.lower() for k, v in mail_addresses.items() if '@' in k]

        # Rundbrief
        mlist = mailman.get_list('genossenschaft-mitglieder')
        mailman.config_list(django_group,
                            mlist, type="news",
                            display_name=f"EVH Mitglieder",
                            subject_prefix=f"[EVH Mitglieder] ",
                            )
        mailman.sync_list(mlist, members=subscribers, strict=True)

        # Newsletter
        mlist = mailman.get_list('genossenschaft-news')
        mailman.config_list(django_group,
                            mlist, type="news",
                            display_name=f"EVH Alle",
                            subject_prefix=f"[EVH Alle] ",
                            )
        mailman.sync_list(mlist, members=subscribers, strict=False)
