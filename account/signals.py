import django.dispatch
from django_auth_ldap.backend import LDAPBackend
from django.conf import settings
from pathlib import Path
import os

import logging
logger = logging.getLogger(__name__)

user_changed = django.dispatch.Signal(providing_args=["username"])


KIRBY_TEMPLATE = """<?php
return [
    'id' => '{username}',
    'name' => '{username}',
    'email' => '{email}',
    'language' => 'de',
    'role' => 'LdapUser'
];
"""

@django.dispatch.receiver(user_changed)
def user_changed_hook(sender, **kwargs):
    username = kwargs['username']
    logger.info("User Changed Hook: %s", username)
    user = LDAPBackend().populate_user(username)
    groups = user.ldap_user.group_names

    if 'genossenschaft' in groups or 'wettbewerb-jury' in groups:
        directory = Path(settings.KIRBY_ACCOUNTS_DIRECTORY) / username
        if not os.path.exists(directory):
            os.mkdir(directory)

        index_php = directory / "index.php"
        index_php_content = KIRBY_TEMPLATE.format(
            username=user.username,
            email=user.email
        )
        if not index_php.exists() or open(index_php).read() != index_php_content:
            with open(index_php, "w+") as fd:
                fd.write(index_php_content)
            logger.info("Created/Updated Kirby Login for %s", user.username)
