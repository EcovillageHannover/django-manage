# coding: utf-8
from django.core.management.base import BaseCommand, CommandError
from poll.models import *
from collections import defaultdict
import sys
import random
import logging
logger = logging.getLogger(__name__)
import csv


class Command(BaseCommand):
    help = 'Export Poll Data'

    def add_arguments(self, parser):
        # Sources
        parser.add_argument("--pc", help="PollCollection ID to lottery on")
        parser.add_argument("--poll", help="Poll ID to export data", type=int)

    def export_poll(self, poll):
        votes = Vote.objects.filter(poll=poll)
        out = csv.writer(sys.stdout)
        out.writerow(
            ["Vorname", "Nachname", "E-Mail", "Auswahl", "Abstimmungszeitpunkt"]
        )
        for vote in votes:
            out.writerow([
                vote.user.first_name,
                vote.user.last_name,
                vote.user.email,
                vote.item.export_key or vote.item.value,
                vote.updated_at.strftime("%d.%m.%Y %H:%M")
            ])



    def handle(self, *args, **options):
        if options['poll']:
            self.export_poll(options['poll'])
            return
        
        polls = []
        polls.extend(list(PollCollection.objects.get(pk=int(options['pc'])).polls.all()))

        out = csv.writer(sys.stderr)
        out.writerow(
            ["Schlagworte", "Titel der Frage", "Frage wie sie formuliert wurde", "Auswahlantwort", "Stimmen (Antwort)", "Stimmen (Frage"]
        )
        for poll in polls:
            schlagworte = ",".join([str(x) for x in poll.tags.all()])
            frage = str(poll)

            if poll.is_text:
                votes = Vote.objects.filter(poll=poll)
                print(f"\n# {frage}\n")
                print("Schlagworte:", schlagworte,"\n")
                print("Kommentare:", len(votes), "\n")
                print("Frage:", poll.description, "\n")
                for vote in votes:
                    print("\n---\n")
                    print(vote.text)

            else:
                for item in poll.items:
                    out.writerow([schlagworte, frage, poll.description, str(item), item.vote_count, poll.vote_count])    
