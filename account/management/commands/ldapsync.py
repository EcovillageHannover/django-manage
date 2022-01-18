# coding: utf-8

from django_auth_ldap.backend import LDAPBackend
from django.core.management.base import BaseCommand, CommandError
from account.models import *
import evh.settings_local as config
from pathlib import Path
from account.signals import *
from datetime import datetime
from account.mailman import Mailman
import os

import logging
logger = logging.getLogger(__name__)

UserModel = get_user_model()

class Command(BaseCommand):
    help = 'Sync Account/Group Information with outside world'
    def add_arguments(self, parser):
        parser.add_argument("--user", '-u', default=None,
                            help="Update only User")

        parser.add_argument("--group", '-g', default=None,
                            help="Update only Group")

        parser.add_argument("--group-members", '-G', default=False,
                            help="Sync Group Members", action='store_true')

        parser.add_argument("--force", '-f', default=False,
                            help="Force Sync all Groups", action='store_true')


    def sync_group_hierarchical_memberships(self, group):
        """Adds or removes members to parent groups. recursively"""
        # Hierarchical Group Syncer
        all_children =group.groupprofile.all_children
        if all_children:
            # logger.info("Hierarchical Children: %s -> %s", group, all_children)
            group_members = set(group.user_set.all())
            child_members = set()
            for child_group in all_children:
                child_members.update(child_group.user_set.all())
    
            for must_add in child_members - group_members:
                logger.info("ADD(hierarchical) %s", must_add)
                must_add.groups.add(group)
    
            for must_del in group_members - child_members:
                logger.info("DEL(hierarchical) %s", must_del)
                must_del.groups.remove(group)

                # FIXME: Unsubscribe from news list

    def sync_group_to_ldap(self, group):
        """Sync Group Memberships from Django to LDAP"""
        if group.name in set(['ldap-user', 'mail-user']):
            return

        group_members = group.user_set.all()
        group_member_names = set([m.username for m in group.user_set.all()])
        ldap_members = set([m['username'] for m in self.ldap.group_members(group)])
        for must_add in group_member_names - ldap_members:
            self.ldap.group_member_change(group.name, must_add, mode="add")
            logger.info("ADD(ldap) %s", must_add)
        for must_del in ldap_members - group_member_names:
            self.ldap.group_member_change(group.name, must_del, mode="remove")
            logger.info("DEL(ldap) %s", must_del)


    def sync_group_mailman(self,group):
        if group.name in set(['genossenschaft',
                              'ecotopia-vorstand',
                              'ecotopia-aufsichtsrat',
                              'ecotopia-mitglieder']):
            return

        # Mailinglists
        if not self.mlists:
            self.m3     = Mailman()
            self.mlists = self.m3.get_lists()
        
        mlist_discuss = f"{group.name}"
        mlist_news = f"{group.name}-news"

        group_name = str(group).title().replace("Ag-", "AG-").replace('Wg-', 'WG-').replace("Evh", "EVH")
        group_name = group_name.replace('laeufe', 'läufe')

        group_members = group.user_set.all()

        # FIXME: Owners are only encoded in LDAP currently
        owners = self.ldap.group_owners(group.name)

        if mlist_discuss in self.mlists:
            mlist = self.mlists[mlist_discuss]
            logger.info(f"Sync Mailinglist {mlist}")
            self.m3.config_list(group, mlist, type="discuss",
                           display_name=f"{group_name}",
                           subject_prefix=f"[{group_name}] ",
                           )

            if self.options['group_members']:
                start = time.time()
                self.m3.sync_list(mlist, members=group_members, owners=owners, strict=True)
                end = time.time()
                logger.info("... took %.2f seconds", end-start)

        if mlist_news in self.mlists:
            mlist = self.mlists[mlist_news]
            logger.info(f"Sync Mailinglist {mlist}")
            prefix = f"{group_name}: Ankündigung"
            if group == 'genossenschaft':
                prefix = 'EVH Newsletter'
            self.m3.config_list(group, mlist, type="news",
                           display_name=prefix,
                           subject_prefix=f"[{prefix}] ",
                           )
            if  str(group).startswith('kronsberg-') or str(group).startswith("verein-"):
                strict=True
            else:
                strict=False

            if self.options['group_members']:
                logger.warning("Syncing members for group: %s", mlist)
                start = time.time()
                self.m3.sync_list(mlist, members=group_members, owners=owners, strict=strict)
                end = time.time()
                logger.info("... took %.2f seconds", end-start)



    def sync_group(self, group):
        # Get or Create Groupprofile
        profile,_ = GroupProfile.objects.get_or_create(group=group)

        if not self. options['force'] and profile.synced_at and \
           ((profile.updated_at and profile.synced_at > profile.updated_at) \
            or not profile.updated_at):
            return
        
        logger.info("Sync Group Memberships: %s (%s %s)", group, group.groupprofile.updated_at, group.groupprofile.synced_at)

        self.sync_group_hierarchical_memberships(group)
        self.sync_group_to_ldap(group)
        self.sync_group_mailman(group)

        # Update the Timestamp
        profile.synced_at = timezone.now()
        profile.save()

    def handle(self, *args, **options):
        users = UserModel.objects.all()
        ## Sync LDAP -> Django
        #print(users)
        #for U in  users:
        #    LDAPBackend().populate_user(U)
        #    print(U)
        #return
        self.options = options
        self.ldap = LDAP()
        self.mlists = None

        if options['user']:
            for user in users:
                if options['user'] in ('all', user.username):
                    user_changed.send(sender=self.__class__, user=user)

        for group in Group.objects.all():
            if options['user']: break 
            if options['group'] and \
               (options['group'] != "all" and not group.name.startswith(options['group'])):
                continue

            self.sync_group(group)

