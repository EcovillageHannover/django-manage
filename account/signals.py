import django.dispatch
from django_auth_ldap.backend import LDAPBackend
from django.conf import settings
from pathlib import Path
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
