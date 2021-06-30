# coding: utf-8

import django.dispatch
from django_auth_ldap.backend import LDAPBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.conf import settings
from pathlib import Path
from .mailman import Mailman
from .models import LDAP
from django.utils import timezone

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
    UserModel = get_user_model()
    group = kwargs.get('group')

    member = kwargs.get('member')
    if type(member) is str:
        member = UserModel.objects.get(username=member)

    # Most Important: Remove from django group
    member.groups.remove(group)

    # Mark all Parents for sync
    for g in [group] + group.groupprofile.all_parents:
        g.groupprofile.updated_at = timezone.now()
        g.groupprofile.save()

    # Remove from to LDAP group (not from parents!)
    LDAP().group_member_change(group.name, member.username, mode="remove")

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
    UserModel = get_user_model()
    group = kwargs.get('group')

    member = kwargs.get('member') # Django User
    if type(member) is str:
        member = UserModel.objects.get(username=member)

    logger.info(f"member: {member} {type(member)}")

    # Add to Django Group (and all parents)
    for g in [group] + group.groupprofile.all_parents:
        member.groups.add(g)
        g.groupprofile.updated_at = timezone.now()
        g.groupprofile.save()

        # Add to LDAP (and all parents
        LDAP().group_member_change(g.name, member.username, mode="add")

    m3 = Mailman()
    if hasattr(member, 'userprofile'):
        emails = member.userprofile.mail_for_mailinglist()
    elif isinstance(member, dict):
        emails = member['mail']
    else:
        emails = member.email
    rc = m3.subscribe(f"{group}", emails)
    rc = m3.subscribe(f"{group}-news", emails)


