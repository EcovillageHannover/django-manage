# coding: utf-8
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
import evh.settings_local as config
from django.core.mail import send_mail
from poll.models import *
from collections import defaultdict
import random
import logging
import time
logger = logging.getLogger(__name__)

User = get_user_model()

class Command(BaseCommand):
    help = 'Lottery from Prioritized Poll'

    def add_arguments(self, parser):
        # Sources
        parser.add_argument("--poll", help="Poll ID to lottery on")
        parser.add_argument("--action:send", action="store_true", help="Send Mails")

        self.mail_count = 0

    def send_mail(self, *args, **kwargs):
        if self.options['action:send']:
            self.mail_count += 1
            # send_mail(*args, **kwargs)
            time.sleep(5)


    def title(self, item):
        seminare = {
            'Aspekte' : '12.06.2020, 17:00, Städtebauliche Aspekte allgemein (Eingliederung ins Umfeld usw./Baudichte/allgemeine Gebäudeanordnung)',
            'Soziales' : '12.06.2020, 20:00, Soziales, Inklusion, Gemeinschaftsgebäude und Gemeinschaftsflächen',
            'Mobilität' : '14.06.2020, 10:00, Aspekte der Mobilität (Wegenetz, Stellflächen, Aufenthaltsqualität)',
            'Stoffkreis' : '14.06.2020, 13:00, Energie und Stoffkreisläufe (Regenwasser, Abwasser, Abfall)',
            'Freiflächen' : '14.06.2020, 16:00, Grün-/Spiel- und Freifächen',
            'Tinyhäuser' : '14.06.2020, 19:00, Tinyhäuser'
        }

        for k,v in seminare.items():
            if k in str(item):
                return v
                break
        else:
            raise RuntimeError(item)        

    def zusage(self, user, item):
        subject = f'[EVH] Zusage am Seminar: {item}'
        seminar = self.title(item)
        
        text = f"""Hallo {user.get_full_name()},

du hast dich erfolgreich für das folgende Seminar angemeldet:

   {seminar}

"""
        if 'Vor-Ort' in str(item):
            text += """Die Veranstaltung findet zur angegeben Zeit in der Zukunftswerkstatt im Ihmezentrum statt:

    Zukunftswerkstatt Ihmezentrum
    Ihmeplatz 7E
    30449 Hannover

WICHTIG: Denk bitte daran einen Mund-Nase-Schutz mitzubringen!

"""
        else:
            text += """Du kannst daher per Videochat zu gegebener Zeit bei der Veranstaltung teilnehmen.

    URL: https://bbb.my-evh.de/b/den-q9r-rfq

"""

        text += """Wenn du weitere Fragen hast, wende dich an: support@my-evh.de

Team Digitales -- Lottofee.
            """

        print(f"ja {self.mail(user)}")
        self.send_mail(subject, text,
                       from_email=config.EMAIL_FROM,
                       recipient_list=['support@my-evh.de', user.email],
                       fail_silently=False)

    def absage(self, user, item):
        seminar = self.title(item)
        subject = f'[EVH] Absage fürs Seminar: {item}'
        if 'Videochat' in str(item):
            extra=' Da sich für die Videochats deutlich mehr Teilnehmer angemeldet haben, als für die Vor-Ort Termine gibt es dort noch einzelne freie Plätze. Wenn du an diesen Teilnehmen willst, schick eine Mail an support@my-evh.de, damit wir die maximale Teilnehmeranzahl einhalten können.'
        else:
            extra=''
        text = f"""Hallo {user.get_full_name()},

auf Grund des hohen Interesses konnten wir deine abgegebenen Präferenzen für das Seminar

   {seminar}

leider nicht berücksichten. Die Auswahl der Teilnehmer an den Terminen
wurde durch das Los entschieden.{extra}

Team Digitales -- Lottofee.
"""

        print(f"nein {self.mail(user)}")
        self.send_mail(subject, text,
                       from_email=config.EMAIL_FROM,
                       recipient_list=['support@my-evh.de', user.email],
                       fail_silently=False)

    def windhund(self, poll):
        items = Item.objects.filter(poll=poll)
        for item in items:
            #if ('zurück' in str(item).lower()):
            #if not ('1. september' in str(item).lower()):
            #    continue
            for vote in Vote.objects.filter(item=item):
                #print(f"{vote.user.get_full_name()} <{vote.user.email}>,", end=' ')
                print(f"{vote.user.get_full_name()}")
                
    def handle(self, *args, **options):
        self.args = args
        self.options = options
        
        poll = Poll.objects.get(pk=int(options['poll']))
        if poll.poll_type != Poll.PRIO:
            self.windhund(poll)
            return
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
                if 'Vor-Ort' in str(item): # Vor Ort ist immer netter
                    preferences[user][item] += 0.00001

        print("Wishes", sum(whishes.values()))

        r = random.Random()
        r.seed(1)

        absagen = defaultdict(list)

        def assign(item, user):
            assignments[user].append(item)
            score[user] += 1

            places[item] -= 1
            item_score = preferences[user][item]

            if item in pairs:
                if pairs[item] in preferences[user]:
                    logging.info("Paired[%s] %s(%s) <-> %s(%s)",
                                 user,
                                 item,        preferences[user][item],
                                 pairs[item], preferences[user][pairs[item]])
                    logger.debug("Delete Pair-Preference for user %s: %s", user, pairs[item])
                    del preferences[user][pairs[item]]
                if user in absagen[pairs[item]]:
                    logger.debug("Delete Absage for user %s: %s", user, pairs[item])
                    absagen[pairs[item]].remove(user)
            del preferences[user][item]
            if places[item] == 0:
                logging.info("Item is full: %s", item)
                del places[item]
                for u in list(preferences.keys()):
                    if item in preferences[u]:
                        logger.debug("Add Absage for user %s: %s", u, item)
                        absagen[item].append(u)
                        del preferences[u][item]

                    if not preferences[u]:
                        logging.info("User lost last option: %s", u)
            for u in list(preferences.keys()):
                if len(preferences[u]) == 0:
                    del preferences[u]

            logger.info("%s -> %s (%s)", user, item, item_score)

        assignments = defaultdict(list)

        fixed_assignments = dict([
        #     ('Nord architecture', ['albert.hensen', 'daria.mengert', 'elisabet.adeva', 'ines.heygster', 'kristina.osmers', 'michael.boeken', 'petra.kalinowsky', 'sara.reimann', 'thorsten.peter', 'ursula.kleber']),
        #     ('studiomauer / cityförster', ['daria.kistner-drobiner', 'elisabet.adeva', 'ines.heygster', 'kristina.osmers', 'maximilian.heise', 'olaf.steinl', 'patricia.bull', 'rebekka.bolte', 'thorsten.peter', 'ursula.kleber']),
        #     ('haascookzemmrich / transsolar', ['daria.kistner-drobiner', 'elisabet.adeva', 'ines.heygster', 'marina.bauer', 'olaf.steinl', 'patricia.bull', 'petra.kalinowsky', 'rebekka.bolte', 'roswita.schlachte', 'thorsten.peter']),
        #     ('ISSS research / plancommun', ['albert.hensen', 'elvira.hendricks', 'florian.eick', 'kristina.osmers', 'lisa.rempp', 'marina.bauer', 'maximilian.heise', 'michael.boeken', 'patricia.bull', 'sabine-beate.liedtke'])

            ('Städebauliche Aspekte / Vor-Ort', ['albert.hensen', 'angelika.sprengel', 'christian.stief', 'daniel.marhenke', 'ines.heygster', 'jakoba.moritz', 'maximilian.heise', 'michael.boeken', 'ralf.ludewig', 'ronald.brandt', 'roswita.schlachte', 'zeynep.parlak']),
            ('Städebauliche Aspekte / Videochat', ['brigitte.haemmerle', 'elisabet.adeva', 'elke.mueller', 'insa.reichwehr', 'julia.stock', 'lidewij.tummers-mueller', 'lilian.seissler', 'lisa.rempp', 'patricia.bull', 'rebekka.bolte', 'thorsten.peter', 'vera.loew']),
            ('Soziales / Vor-Ort', ['albert.hensen', 'christian.stief', 'daniel.marhenke', 'elvira.hendricks', 'florian.kalka', 'ines.heygster', 'jakob.aderhold', 'jakoba.moritz', 'lisa.rempp', 'maximilian.heise', 'michael.boeken', 'olaf.steinl', 'petra.kalinowsky', 'roswita.schlachte']),
            ('Soziales / Videochat', ['benedikt.kaesbach', 'daria.mengert', 'elisabet.adeva', 'elke.mueller', 'holger.michaelsen', 'kaja.tippenhauer', 'lilian.seissler', 'olga-maria.liebieg', 'sabine-beate.liedtke', 'sarah.lang', 'swantje.michaelsen', 'vera.loew'])

        ])

        for item in places:
            if 'Vor-Ort' in str(item):
                places[item] = 18
            else:
                places[item] = 12

        for item, users in fixed_assignments.items():
            item = item_by_value[item]
            for user in users:
                user = user_by_username[user]
                assign(item, user)
            places[item] = 0




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
            if ('Soziales' in str(item) or 'baul' in str(item)):
                continue
            
            print(f"# {item} zusagen: {len(item_assignments[item])}/ absagen: {len(absagen[item])}")

            # print((item.value, [u.username for u in item_assignments[item]]))
            print("Bcc:", ", ".join(map(self.mail, item_assignments[item])))

            for user in item_assignments[item]:
                self.zusage(user, item)

            for user in absagen[item]:
                self.absage(user, item)
            print()
        ALL = list(absagen.items()) + list(item_assignments.items())
        print("# Anmeldungen")
        print("#  davon Vor-Ort:", sum([len(v) for k,v in ALL if 'Vor-Ort' in str(k)]))
        print("#  davon Online:", sum([len(v) for k,v in ALL if 'Videochat' in str(k)]))

        print("# Absagen:", sum([len(x) for x in absagen.values()]))
        print("# Zusagen:", sum([len(x) for x in item_assignments.values()]))

        print("# Teilnehmer")
        x = set(); [x.update(v) for k, v in ALL]
        print("#  gesamt:", len(x))
        x = set(); [x.update(v) for k, v in ALL if 'Vor-Ort' in str(k)]
        print("#  Vor-Ort:", len(x))
        x = set(); [x.update(v) for k, v in ALL if 'Videochat' in str(k)]
        print("#  Videochat:", len(x))

        print("# Versendete Mails:", self.mail_count)


    def mail(self, user):
        return f"{user.get_full_name()} <{user.email}>"
