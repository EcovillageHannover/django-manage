import django.dispatch
from django_auth_ldap.backend import LDAPBackend
from django.conf import settings
from pathlib import Path
from .mailman import Mailman
from .models import LDAP
import os

import logging
logger = logging.getLogger(__name__)

KIRBY_TEMPLATE = """<?php
return [
    'id' => '{username}',
    'name' => '{username}',
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
                     'amsel-kollektiv',
                     'vorstand']):
        if not os.path.exists(directory):
            os.mkdir(directory)

        index_php_content = KIRBY_TEMPLATE.format(
            username=user.username,
            email=user.email
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


group_changed = django.dispatch.Signal(providing_args=["group"])
@django.dispatch.receiver(group_changed)
def group_changed_hook(sender, **kwargs):
    group = kwargs['group']
    logger.info("Group Changed Hook: %s", group)

    m3 = Mailman()
    mlists = m3.get_lists()
    mlist_discuss = f"{group}"
    mlist_news = f"{group}-news"

    if mlist_discuss in mlists or mlist_news in mlists:
        l = LDAP()
        members = l.group_members(group)
        owners = l.group_owners(group)

        if mlist_discuss in mlists:
            mlist = mlists[mlist_discuss]
            logger.info(f"Sync Mailinglist {mlist}")
            m3.config_list(mlist, strict=True)
            m3.sync_list(mlist, members=members, owners=owners, strict=True)

        if mlist_news in mlists:
            mlist = mlists[mlist_news]
            logger.info(f"Sync Mailinglist {mlist}")
            m3.config_list(mlist, strict=False)
            m3.sync_list(mlist, members=members, owners=owners, strict=False)

    
