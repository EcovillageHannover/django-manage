# coding: utf-8
from django.core.management.base import BaseCommand, CommandError
from poll.models import *
from collections import defaultdict
import random
import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Lottery from Prioritized Poll'

    def add_arguments(self, parser):
        # Sources
        parser.add_argument("--poll", help="Poll ID to lottery on")

    def handle(self, *args, **options):
        poll = Poll.objects.get(pk=int(options['poll']))
        assert poll.poll_type == Poll.PRIO
        items = Item.objects.filter(poll=poll)

        pairs = {}
        for a in items:
            pa = str(a).split("/")[0]
            for b in items:
                if a == b: continue
                pb = str(b).split("/")[0]
                if pa == pb:
                    pairs[a] = b


        places = {}
        score = {}
        preferences = defaultdict(dict)
        whishes = defaultdict(lambda : 0)
        item_by_value = {}
        user_by_username = {}
        for item in items:
            item_by_value[item.value] = item
            places[item] = 10
            for vote in Vote.objects.filter(item=item):
                prio = int(vote.text)
                if prio > 0:
                    preferences[vote.user][item] = prio
                    user_by_username[vote.user.username] = vote.user
                    whishes[vote.user] += 1
                    score[vote.user] = 0
        # Normalize
        for user in preferences:
            SUM = float(sum(preferences[user].values()))
            for item in preferences[user]:
                preferences[user][item] = preferences[user][item] * 100 / SUM

        print("Wishes", sum(whishes.values()))

        r = random.Random()
        r.seed(0)

        absagen = defaultdict(list)

        def assign(item, user):
            assignments[user].append(item)
            score[user] += 1

            places[item] -= 1
            item_score = preferences[user][item]
            del preferences[user][item]
            if item in pairs and pairs[item] in preferences[user]:
                logger.info("Delete Pair: %s", pairs[item])
                del preferences[user][pairs[item]]
            if places[item] == 0:
                logging.info("Item is full: %s", item)
                del places[item]
                for u in list(preferences.keys()):
                    if item in preferences[u]:
                        absagen[item].append((u, preferences[u][item]))
                        del preferences[u][item]

                    if not preferences[u]:
                        logging.info("User lost last option: %s", u)
            for u in list(preferences.keys()):
                if len(preferences[u]) == 0:
                    del preferences[u]

            logger.info("%s -> %s (%s)", user, item, item_score)

        assignments = defaultdict(list)

        fixed_assignments = dict([
            ('Nord architecture', ['albert.hensen', 'daria.mengert', 'elisabet.adeva', 'ines.heygster', 'kristina.osmers', 'michael.boeken', 'petra.kalinowsky', 'sara.reimann', 'thorsten.peter', 'ursula.kleber']),
            ('studiomauer / cityförster', ['daria.kistner-drobiner', 'elisabet.adeva', 'ines.heygster', 'kristina.osmers', 'maximilian.heise', 'olaf.steinl', 'patricia.bull', 'rebekka.bolte', 'thorsten.peter', 'ursula.kleber']),
            ('haascookzemmrich / transsolar', ['daria.kistner-drobiner', 'elisabet.adeva', 'ines.heygster', 'marina.bauer', 'olaf.steinl', 'patricia.bull', 'petra.kalinowsky', 'rebekka.bolte', 'roswita.schlachte', 'thorsten.peter']),
            ('ISSS research / plancommun', ['albert.hensen', 'elvira.hendricks', 'florian.eick', 'kristina.osmers', 'lisa.rempp', 'marina.bauer', 'maximilian.heise', 'michael.boeken', 'patricia.bull', 'sabine-beate.liedtke'])
        ])


        for item, users in fixed_assignments.items():
            item = item_by_value[item]
            for user in users:
                user = user_by_username[user]
                assign(item, user)

        for item in places:
            if item not in fixed_assignments:
                places[item] += 2

        while places and preferences:
            # 1. Find all users with the lowest score
            min_score = min([score[u] for u in preferences])
            candidates = sorted([u for u in preferences.keys() if score[u] == min_score],
                                key=lambda u: u.username)
            weights=[max(preferences[u].values()) for u in candidates]
            user = r.choices(
                population=candidates,
                weights=weights
            )[0]
            if user not in preferences:
                score[user] += 1
                continue

            max_pref = max(prio for item,prio in preferences[user].items())
            max_items = [item for item, prio in preferences[user].items() if prio == max_pref]
            item = r.choice(sorted(max_items, key=lambda i: i.id))

            assign(item, user)

        assert not preferences
            

        item_assignments = defaultdict(list)
        for user in sorted(assignments, key=lambda a: str(a)):
            print(f"{user.get_full_name()} <{user.email}> {len(assignments[user])}/{whishes[user]}")
            for item in assignments[user]:
                item_assignments[item].append(user)
                #    print(f"  {item}")

        print("----")
        
        for item in sorted(item_assignments, key=lambda a: str(a)):
            print(f"# {item} zusagen: {len(item_assignments[item])}/ absagen: {len(absagen[item])}")
            print((item.value, [u.username for u in item_assignments[item]]))
            for user in item_assignments[item]:
                print(f"ja   {user.get_full_name()} <{user.email}>")
            for user,score in absagen[item]:
                print(f"nein {user.get_full_name()} <{user.email}> ({score})")
            print()
