# coding: utf-8
from django.core.management.base import BaseCommand, CommandError
from poll.models import *
from collections import defaultdict
import random
import logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Statistic about Poll Data'

    def add_arguments(self, parser):
        # Sources
        parser.add_argument("--pc", help="PollCollection ID to lottery on")

    def handle(self, *args, **options):
        polls = []
        polls.extend(list(PollCollection.objects.get(pk=int(options['pc'])).polls.all()))

        teilnehmer = set()
        print("Fragen:", len(polls))
        abstimmungen = 0
        for poll in polls:
            votes = Vote.objects.filter(poll=poll)
            users = set([v.user for v in votes])
            abstimmungen += len(users)
            teilnehmer |= users
        print("Teilnehmer:", len(teilnehmer))
        print("Abstimmungen:", abstimmungen)
