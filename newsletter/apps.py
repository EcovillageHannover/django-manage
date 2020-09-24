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
        ('team-test-news', 'Team Test', 'https://www.ecovillage-hannover.de/mitmachen/mitmachen'),
    ]
