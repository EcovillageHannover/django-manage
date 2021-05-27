# coding: utf-8

import django.dispatch
from django_auth_ldap.backend import LDAPBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from pathlib import Path
from .mailman import Mailman
from .models import LDAP

import time
import os

import logging
logger = logging.getLogger(__name__)

KIRBY_TEMPLATE = """<?php
return [
    'id' => '{username}',
    'name' => '{fullname}',
    'email' => '{email}',
    'language' => 'de',
    'role' => 'LdapUser'
];

"""

user_changed = django.dispatch.Signal(providing_args=["username"])
@django.dispatch.receiver(user_changed)
def user_changed_hook(sender, **kwargs):
    username = kwargs['username']
    logger.info("User Changed Hook: %s", username)
    user = LDAPBackend().populate_user(username)
    groups = set(user.ldap_user.group_names)

    ################################################################
    # Kirby
    directory = Path(settings.KIRBY_ACCOUNTS_DIRECTORY) / username
    index_php = directory / "index.php"
    if groups & set(['genossenschaft',
                     'wettbewerb-jury',
                     'wettbewerb-externe',
                     'amsel-kollektiv',
                     'vorstand',
                     'mitarbeiterinnen',
                     'praktikantinnen']):
        if not os.path.exists(directory):
            os.mkdir(directory)

        index_php_content = KIRBY_TEMPLATE.format(
            fullname=user.get_full_name(),
            username=user.username,
            email=user.email,
        )
        if not index_php.exists() or open(index_php).read() != index_php_content:
            with open(index_php, "w+") as fd:
                fd.write(index_php_content)
            logger.info("Created/Updated Kirby Login for %s", user.username)
    else:
        if directory.exists():
            if index_php.exists():
                index_php.unlink()
            directory.rmdir()
            logger.info("Deleted Kirby Login for %s", user.username)

group_member_remove = django.dispatch.Signal(providing_args=["group", "member"])
@django.dispatch.receiver(group_member_remove)
def group_member_remove_hook(sender, **kwargs):
    group = kwargs.get('group')
    member = kwargs.get('member')

    m3 = Mailman()
    if hasattr(member, 'userprofile'):
        emails = member.userprofile.mail_for_mailinglist()
    elif isinstance(member, dict):
        emails = member['mail']
    else:
        emails = member.email

    rc = m3.unsubscribe(f"{group}", emails)
    rc = m3.unsubscribe(f"{group}-news", emails)


group_member_add = django.dispatch.Signal(providing_args=["group", "member"])
@django.dispatch.receiver(group_member_add)
def group_member_add_hook(sender, **kwargs):
    group = kwargs.get('group')
    member = kwargs.get('member') # Django User

    logger.info(f"member: {member} {type(member)}")

    m3 = Mailman()
    if hasattr(member, 'userprofile'):
        emails = member.userprofile.mail_for_mailinglist()
    elif isinstance(member, dict):
        emails = member['mail']
    else:
        emails = member.email
    rc = m3.subscribe(f"{group}", emails)
    rc = m3.subscribe(f"{group}-news", emails)


group_changed = django.dispatch.Signal(providing_args=["group"])
@django.dispatch.receiver(group_changed)
def group_changed_hook(sender, **kwargs):
    UserModel = get_user_model()
    group = Group.objects.get(name=kwargs['group'])
    logger.info("Group Changed Hook: %s", group)

    #assert group.groupprofile is not None
    #print(group.groupprofile.all_children())

    m3 = Mailman()
    mlists = m3.get_lists()
    mlist_discuss = f"{group.name}"
    mlist_news = f"{group.name}-news"

    group_name = str(group).title().replace("Ag-", "AG-").replace('Wg-', 'WG-').replace("Evh", "EVH")
    group_name = group_name.replace('laeufe', 'läufe')

    group_nosync = f"{group.name}" in set(['ag-gastgeber', 'genossenschaft',
                                      'ecotopia-vorstand', 'ecotopia-aufsichtsrat', 'ecotopia-mitglieder'])
    if 'member_sync' not in kwargs:
        group_nosync = True


    # If the Mailinglist exists, we sync it.
    if mlist_discuss in mlists or mlist_news in mlists:
        l = LDAP()
        members = l.group_members(group)
        for member in members:
            try:
                member['user'] = UserModel.objects.get(username=member['username'])
            except UserModel.DoesNotExist:
                user = LDAPBackend().populate_user(member['username'])
                member['user'] = user
                member['user_not_found'] = True
                pass
        owners = l.group_owners(group.name)

        if mlist_discuss in mlists:
            mlist = mlists[mlist_discuss]
            logger.info(f"Sync Mailinglist {mlist}")
            m3.config_list(group, mlist, type="discuss",
                           display_name=f"{group_name}",
                           subject_prefix=f"[{group_name}] ",
                           )
            start = time.time()
            if not group_nosync:
                logger.warning("Syncing members for group: %s", mlist)
                m3.sync_list(mlist, members=members, owners=owners, strict=True)
            else:
                logger.warning("Not syncing members for group: %s", mlist)
            end = time.time()
            logger.info("... took %.2f seconds", end-start)

        if mlist_news in mlists:
            mlist = mlists[mlist_news]
            logger.info(f"Sync Mailinglist {mlist}")
            prefix = f"{group_name}: Ankündigung"
            if group == 'genossenschaft':
                prefix = 'EVH Newsletter'
            m3.config_list(group, mlist, type="news",
                           display_name=prefix,
                           subject_prefix=f"[{prefix}] ",
                           )
            start = time.time()
            if  str(group).startswith('kronsberg-h'):
                strict=True
            else:
                strict=False

            if not group_nosync:
                logger.warning("Syncing members for group: %s", mlist)
                m3.sync_list(mlist, members=members, owners=owners, strict=strict)
            else:
                logger.warning("Not syncing members for group: %s", mlist)
            end = time.time()
            logger.info("... took %.2f seconds", end-start)


    
