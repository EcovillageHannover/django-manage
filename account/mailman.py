from django.conf import settings
from mailmanclient import Client as Mailman3Client
from six.moves.urllib_error import HTTPError

import logging
logger = logging.getLogger(__name__)

class Mailman:
    def __init__(self):
        self.m3 = Mailman3Client(
            'https://{0}:{1}/3.1'.format(settings.MAILMAN_HOST,
                                         getattr(settings, "MAILMAN_PORT", "443")),
            settings.MAILMAN_USER,
            settings.MAILMAN_PASSWORD
        )

    def get_lists(self):
        domain = self.m3.get_domain(settings.MAILMAN_LIST_DOMAIN)
        return {mlist.list_name: mlist for mlist in domain.lists}

    def config_list(self, mlist, strict=True):
        config = dict(
            send_welcome_message=False,
            archive_policy="private",
            preferred_language="de",
            dmarc_mitigate_action="munge_from",
            subscription_policy="confirm",
            reply_goes_to_list="point_to_list",
            allow_list_posts=True,
            default_nonmember_action="accept",
        )
        if not strict:
            config['subscription_policy'] = "open"
            config["allow_list_posts"] = False
            config["default_nonmember_action"]="reject"



        if mlist.list_name in ('vorstand', 'aufsichtsrat'):
            config['archive_policy'] = 'never'
            print(mlist.settings)

        
        # Write some settings
        save = False
        for k, v in config.items():
            if k in mlist.settings and mlist.settings[k] != v:
                logger.info(f"Set option {k} on list {mlist} to {v}")
                mlist.settings[k] = v
                save = True
        if save:
            mlist.settings.save()


    def sync_list(self, mlist, members, owners=None, strict=True):
        members_mails = set([u['mail'] for u in members])
        subscriber_mails = set([m.address.email for m in mlist.members])

        def sync_tag(tag, should_set, is_set, add, remove):
            for element in should_set - is_set:
                logger.info(f"Add[{tag}] {element} to list {mlist}")
                add(element)

            # If we do not sync strict, we are fine here
            if not strict: return

            for element in is_set - should_set:
                logger.info(f"Remove[{tag}] {element} from list {mlist}")
                remove(element)

        sync_tag('subscriber', members_mails, subscriber_mails,
                 add=lambda subscriber: mlist.subscribe(subscriber,
                                                   pre_verified=True,
                                                   pre_confirmed=True,
                                                   pre_approved=True),
                 remove=lambda subscriber: mlist.unsubscribe(subscriber))

        if owners:
            owner_mails = set([u['mail'] for u in owners])
            moderator_mails = set([m.address.email for m in mlist.moderators])
            sync_tag('moderator', owner_mails, moderator_mails,
                     add=lambda mail: mlist.add_moderator(mail),
                     remove=lambda mail: mlist.remove_moderator(mail))

            if not strict:
                m3_owner_mails = set([m.address.email for m in mlist.owners])
                sync_tag('owner', owner_mails, m3_owner_mails,
                         add=lambda mail: mlist.add_owner(mail),
                        remove=lambda mail: mlist.remove_owner(mail))
