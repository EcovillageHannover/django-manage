# coding: utf-8

from django.apps import AppConfig
from django.utils.html import mark_safe



class NewsletterConfig(AppConfig):
    name = 'newsletter'
    newsletters = []

    def form_choices(self):
        for name, label, url in self.newsletters:
            if url:
                yield (name, mark_safe(f'<a href="{url}">{label}</a>'))
            else:
                yield (name, label)

    def encode(self, names):
        configured = [x[0] for x in self.newsletters]

        ret = 0
        for name in names:
            if name not in configured:
                raise InvalidArgument("Newsletter %s not found", name)
            ret |= 1 << configured.index(name)

        return ret

    def decode(self, mask):
        configured = [x[0] for x in self.newsletters]
        ret = []
        i = 0
        while i <= mask:
            if (1 << i) & mask:
                ret.append(configured[i])
            i += 1
        return ret

class EVHNewsletterConfig(NewsletterConfig):
    name = 'newsletter'

    newsletters = [
        # mailman-name, label, url
        ('genossenschaft-news', 'Allgemeiner Newsletter', None),
        ('ag-standorte-news', 'A1 - Klärung weiterer längerfristiger Standorte', None),
        ('ag-gemeinschaft-news', 'A2 - Soziales Leben im Ecovillage', None),
        ('ag-forschung-news', 'A4 - Begleitforschung', None),
        ('ag-stadtplanung-news', 'K2 - Erarbeitung Quartiersflächenplan', None),
        ('wohngruppen-news', 'K3 - Zusammenfinden von Wohngruppen und Baugemeinschaften', None),
        ('ag-energie-news', 'K4 - Energie- und Wasserkonzept Kronsberg', None),
        ('ag-mobilitaet-news', 'K5 - Mobilitätskonzept Kronsberg', None),
        ('ag-gruenes-news', 'K6 - Grünflächen/Gartenbau', None),
        ('ag-projekte-news', 'K7 - Soziale und gewerbliche Projekte Kronsberg', None),
        ('ag-freistehende-tinyhouses-news', 'K8 - Freistehende TinyHouses am Kronsberg (mobil und stationär)', None),
        ('ag-modulares-bauen-news', 'K9 - Mehrstöckige Modulhäuser am Kronsberg', None),
        ('ag-stoffkreislaeufe-news', 'K10 - Stoffkreisläufe', None),
        #('team-test-news', 'Team Test', 'https://www.ecovillage-hannover.de/mitmachen/mitmachen'),
    ]
