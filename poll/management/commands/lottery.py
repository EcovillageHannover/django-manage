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

        places = {}
        score = {}
        preferences = defaultdict(dict)
        for item in items:
            places[item] = 1
            for vote in Vote.objects.filter(item=item):
                prio = int(vote.text)
                if prio > 0:
                    preferences[vote.user][item] = prio 
                    score[vote.user] = 0

        r = random.Random()
        r.seed(0)

        assignments = defaultdict(list)
        while places and preferences:
            # 1. Find all users with the lowest score
            min_score = min(score.values())
            candidates = sorted([u for u in score if score[u] == min_score],
                                key=lambda u: u.username)
            user = r.choice(candidates)

            max_pref = max(prio for item,prio in preferences[user].items())
            max_items = [item for item, prio in preferences[user].items() if prio == max_pref]
            item = r.choice(sorted(max_items, key=lambda i: i.id))
            assignments[item].append(user)
            score[user] += 1

            places[item] -= 1
            if places[item] == 0:
                del places[item]
                for u in list(preferences.keys()):
                    if item in preferences[u]:
                        del preferences[u][item]

            if not preferences[user]:
                    del preferences[user]


            logger.debug(user, "->", item)

        for item in assignments:
            print(f"{item}:")
            for user in assignments[item]:
                print(f"  {user.get_full_name()} <{user.email}>,")
            print()
        
