# coding: utf-8

from django.apps import AppConfig
from django.utils.html import mark_safe



class NewsletterConfig(AppConfig):
    name = 'newsletter'
    newsletters = []

    def form_choices(self):
        for name, label, url in self.newsletters:
            if name is None: continue
            if url:
                yield (name, mark_safe(f'<a href="{url}" target="_blank">{label}</a>'))
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

    initial = ['genossenschaft-news']

    @property
    def all(self):
        return [x[0] for x in self.newsletters if x[0]]

    newsletters = [
        # mailman-name, label, url
        ('genossenschaft-news', 'Allgemeiner Newsletter der ecovillage hannover e.G.', None),
        (None, None, None), # ('dorfrat-kronsberg-news', 'Dorfrat Kronsberg', None),
        ('ag-standorte-news', 'A1 - Klärung weiterer längerfristiger Standorte',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/weitere-standorte'),
        ('ag-gemeinschaft-news', 'A2 - Soziales Leben im ecovillage',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/soziales-leben'),
        ('ag-forschung-news', 'A4 - Begleitforschung',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/begleitforschung'),
        ('ag-inklusion-news', 'A7 - Inklusion und Barrierefreiheit',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/inklusion'),
        ('ag-stadtplanung-news', 'K2 - Erarbeitung Quartiersflächenplan',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/quartiersflaechenplanung'),
        ('ag-wohngruppen-news', 'K3 - Zusammenfinden von Wohngruppen und Baugemeinschaften',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/wohngruppen'),
        ('ag-energie-news', 'K4 - Energiekonzept Kronsberg',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/energiekonzept'),
        ('ag-mobilitaet-news', 'K5 - Mobilitätskonzept Kronsberg',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/mobilitaetskonzept'),
        ('ag-gruenes-news', 'K6 - Grünflächen/Gartenbau',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/gruenes'),
        ('ag-projekte-news', 'K7 - Soziale und gewerbliche Projekte Kronsberg',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/projekte'),
        ('ag-freistehende-tinyhouses-news', 'K8 - Freistehende TinyHouses am Kronsberg (mobil und stationär)',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/tiny-haeuser'),
        ('ag-modulares-bauen-news', 'K9 - Mehrstöckige Modulhäuser am Kronsberg',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/modulhaeuser'),
        ('ag-stoffkreislaeufe-news', 'K10 - Stoffkreisläufe',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/stoffkreislaeufe'),
        ('team-digitales-news', 'AG Digitales',
         'https://www.ecovillage-hannover.de/mitmachen/themengruppen/digitales'),
    ]
