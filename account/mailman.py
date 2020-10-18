from django.conf import settings
from mailmanclient import Client as Mailman3Client
from six.moves.urllib_error import HTTPError
from evh.utils import bidict
from django.urls import reverse
from django.contrib.auth import get_user_model


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

    @property
    def domain(self):
        return self.m3.get_domain(settings.MAILMAN_LIST_DOMAIN)


    def get_lists(self, subscriber=None):
        if subscriber is None:
            domain = self.m3.get_domain(settings.MAILMAN_LIST_DOMAIN)
            return {mlist.list_name: mlist for mlist in domain.lists}
        else:
            try:
                # FIXME: This also returns lists where I'm only the owner
                mlists = self.m3.find_lists(subscriber=subscriber,
                                            role='member',
                                            mail_host=settings.MAILMAN_LIST_DOMAIN)
                logger.info("%s: %s", subscriber, mlists)
            except HTTPError as e:
                return {}
            return {mlist.list_name: mlist for mlist in mlists}

    def config_list(self, group, mlist, type, **kwargs):
        config = dict(
            send_welcome_message=False,
            archive_policy="private",
            preferred_language="de",
            dmarc_mitigate_action="munge_from",
            max_message_size=1024,
            admin_immed_notify=False,
        )
        config.update(kwargs)
        if type == "discuss":
            config['subscription_policy'] = "confirm"
            config["allow_list_posts"] = True
            config['reply_goes_to_list'] = "point_to_list"
            config['default_member_action'] = "accept"
            config['default_nonmember_action'] = "accept"
            config['advertised'] = False


        elif type == "news":
            config['subscription_policy'] = "open"
            config["allow_list_posts"] = False
            config['reply_goes_to_list'] = "no_munging"
            config["default_member_action"] = "hold"
            config["default_nonmember_action"] = "hold"
            config['advertised'] = True

            mlist.set_template('list:member:regular:footer',
                               settings.BASE_URL + reverse('account:group_mailman', args=[group]))


        if mlist.list_name in ('vorstand', 'aufsichtsrat',
                               'ecotopia-vorstand', 'ecotopia-aufsichtsrat'):
            config['archive_policy'] = 'never'

        #for k,v in mlist.settings.items():
        #    logger.info(f"{k}: {v}")

        
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
        subscribers = []
        page_idx = 1
        while True:
            page = mlist.get_member_page(page=page_idx, count=100)
            page_idx += 1
            subscribers.extend(page)
            logger.debug("Getting Subscriber Page %d", page_idx)
            if len(page) < 100: break
        subscriber_mails = set([m.address.email.lower() for m in subscribers])

        member_should_set = set()
        member_should_not_set = set()

        for member in members:
            if member['user'] and hasattr(member['user'], 'userprofile'):
                primary, secondaries = member['user'].userprofile.mail_for_mailinglist()
                member_should_set.add(primary.lower())
                for m in secondaries:
                    member_should_not_set.add(m.lower())
            else:
                member_should_set.add(member['mail'].lower())

        def sync_tag(tag, is_set, should_set, add, remove, should_not_set=set(), strict=True):
            for element in should_set - is_set:
                logger.info(f"Add[{tag}] {element} to list {mlist}")
                add(element)

            for element in is_set & should_not_set:
                logger.info(f"Remove[{tag}] {element} to list {mlist}")
                remove(element)
                is_set.remove(element)

            # If we do not sync strict, we are fine here
            #for x in is_set - should_set:
            #    print(x)
            if not strict: return

            for element in is_set - should_set:
                logger.info(f"Remove[{tag}] {element} from list {mlist}")
                remove(element)


        sync_tag('subscriber',
                 is_set=subscriber_mails,
                 should_set=member_should_set,
                 should_not_set=member_should_not_set,
                 add=lambda subscriber: mlist.subscribe(subscriber,
                                                   pre_verified=True,
                                                   pre_confirmed=True,
                                                   pre_approved=True),
                 remove=lambda subscriber: mlist.unsubscribe(subscriber),
                 strict=strict)

        if owners is not None:
            owner_mails = set([u['mail'].lower() for u in owners])
            moderator_mails = set([m.address.email.lower() for m in mlist.moderators])
            sync_tag('moderator',
                     is_set=moderator_mails,
                     should_set=owner_mails, 
                     add=lambda mail: mlist.add_moderator(mail),
                     remove=lambda mail: mlist.remove_moderator(mail))

        for mod in mlist.moderators:
            if mod.moderation_action != 'accept':
                mod.moderation_action = 'accept'
                logger.info(f"{mod}: set moderation action to {mod.moderation_action}")
                mod.save()


        site_admins = set(['dennis.klose@my-evh.de', 'christian.dietrich@my-evh.de'])
        m3_owner_mails = set([m.address.email for m in mlist.owners])
        sync_tag('owner',
                 should_set=site_admins,
                 is_set=m3_owner_mails,
                 add=lambda mail: mlist.add_owner(mail),
                 remove=lambda mail: mlist.remove_owner(mail))

    def subscribe(self, mlist, subscriber):
        ################################################################
        # Duck-Type for Map[Mail, bool]
        if type(subscriber) is tuple:
            primary, secondaries = subscriber
            self.subscribe(mlist, primary)
            for mail in secondaries:
                self.unsubscribe(mlist, mail)
            return

        ################################################################
        # Acutal Subscribe
        try:
            list_id = f"{mlist}@{settings.MAILMAN_LIST_DOMAIN}"
            mlist = self.m3.get_list(list_id)
        except HTTPError as e:
            return f"Mailingliste {mlist} nicht gefunden"

        try:
            mlist.subscribe(subscriber,
                            pre_verified=True,
                            pre_confirmed=True,
                            pre_approved=True)
            logger.info("Subscribed %s on %s", subscriber, mlist)
            return 1
        except HTTPError as e:
            logger.info('%s', e)
            return 0


    def unsubscribe(self, mlist, subscriber):
        if type(subscriber) is tuple:
            primary, secondaries = subscriber
            for mail in [primary] + list(secondaries):
                self.unsubscribe(mlist, mail)
            return

        try:
            list_id = f"{mlist}@{settings.MAILMAN_LIST_DOMAIN}"
            mlist = self.m3.get_list(list_id)
        except HTTPError as e:
            return f"Mailingliste {mlist} nicht gefunden"

        try:
            mlist.unsubscribe(subscriber)
            logger.info("Unsubscribed %s on %s", subscriber, mlist)
            return 1
        except HTTPError as e:
            logger.info('%s', e)
            return 0
        except ValueError:
            return 0
