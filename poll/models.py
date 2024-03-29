# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.db.models.manager import Manager
from django.contrib.auth import get_user_model
from django.db.models import Count

from taggit.managers import TaggableManager

import logging
logger = logging.getLogger(__name__)


import datetime

# Create your models here.
class PollCollection(models.Model):
    date = models.DateField(default=datetime.date.today)
    name = models.CharField(max_length=255, unique=True)

    description = models.TextField(default="",blank=True)

    is_published = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Umfrage"
        verbose_name_plural = "Umfragen"
        permissions = (
            ('vote_pollcollection',    'Umfrage abstimmen'),
            ('analyze_pollcollection', 'Umfrage auswerten'),
            ('export_pollcollection',  'Umfragedaten exportieren'),
        )

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    def can_view(self, user):
        return user.has_perm('view_pollcollection', self) \
            or user.has_perm('vote_pollcollection', self) or user.is_superuser

    def can_vote(self, user):
        return user.has_perm('vote_pollcollection', self) or user.is_superuser

    def can_analyze(self, user):
        return user.has_perm('analyze_pollcollection', self) or user.is_superuser

    def can_export(self, user):
        return user.has_perm('export_pollcollection', self) or user.is_superuser

    def can_change(self, user):
        return user.has_perm('change_pollcollection', self) or user.is_superuser

    @staticmethod
    def list_for_user(user):
        pcs = PollCollection.objects.all()
        pcs = [p for p in pcs if (p.is_published and p.can_view(user)) or p.can_change(user)]
        return pcs
    

    def get_unvoted(self, user):
        if not self.can_vote(user) or not self.is_active or not self.is_published:
            return []
        return self.polls.filter(is_published=True).exclude(vote__user=user)



class Poll(models.Model):
    poll_collection = models.ForeignKey(PollCollection, on_delete=models.CASCADE,
                                        related_name = 'polls')

    RADIO = 'RA'
    CHECKBOX = 'CE'
    TEXT = 'TX'
    PRIO = 'PR'
    YESNONONE = 'Y3'
    
    TYPE_CHOICES = (
        (RADIO, 'Einfachauswahl'),
        (CHECKBOX, 'Mehrfachauswahl'),
        (TEXT, 'Freitext'),
        (PRIO, 'Priorisierung'),
        (YESNONONE, 'Ja-Nein-Enthaltung'),
    )

    poll_type = models.CharField(max_length=2,
                                 choices=TYPE_CHOICES,
                                 default=RADIO)

    question = models.CharField(max_length=255, unique=False)
    description = models.TextField(default="")

    is_published = models.BooleanField(default=True)

    show_percent = models.BooleanField(default=True)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    tags = TaggableManager(blank=True)

    position = models.SmallIntegerField(default=1)

    max_votes = models.SmallIntegerField(default=-1,blank=True,null=True)

    export_key = models.CharField(max_length=255, blank=True, null=True, unique=False)

    class Meta:
        verbose_name = "Frage"
        verbose_name_plural = "Fragen"
        ordering = ["position", "id"]

    def __unicode__(self):
        return self.question

    def __str__(self):
        return self.question

    @property
    def is_text(self):
        return self.poll_type == Poll.TEXT

    @property
    def is_prio(self):
        return self.poll_type == Poll.PRIO

    @property
    def is_yes_no_none(self):
        return self.poll_type == Poll.YESNONONE
    
    @property
    def items(self):
        return Item.objects.filter(poll=self).order_by('position', 'id')

    @property
    def results(self):
        ret = []
        for item in self.items:
            count = self.vote_count
            if count == 0:
                ret += [(item, 0, 0)]
            else:
                if self.is_prio:
                    votes = Vote.objects.filter(item=item)
                    if len(votes):
                        avg =  sum(int(v.text or '0') for v in votes) / float(votes.count())
                    else:
                        avg = 0.0
                    ret += [(item, "%.1f"%avg, int(avg/5.0*100))]
                elif self.is_yes_no_none:
                    votes = Vote.objects.filter(item=item)
                    stimmen = dict(ja=0, nein=0, enthaltung=0)
                    for v in votes:
                        stimmen[v.text] += 1

                    label = "Ja: {ja}, Nein: {nein}, Enthaltung: {enthaltung}".format(
                        **stimmen)
                    ret += [(item, label, 0)]
                else:
                    percent = int(item.vote_count / float(count) * 100)
                    ret += [(item, percent, percent)]
        return ret

    @property
    def votes(self):
        return Vote.objects \
                   .filter(poll=self)

    def has_voted(self, user):
        return Vote.objects \
                   .filter(poll=self, user=user)\
                   .exists()

    def get_unvoted(self, user):
        polls = Poll.objects.all()\
                    .exclude(vote__user=me)\
                    .filter(poll_collection__is_active=True,
                            poll_collection__is_published=True)
        return [p for p in polls if p.can_vote(user)]
        
    @property
    def vote_count(self):
        return self.votes.aggregate(votes=Count('user', distinct=True))['votes']


class Item(models.Model):
    value = models.CharField(max_length=255, unique=False)
    export_key = models.CharField(max_length=255, blank=True, null=True, unique=False)
    position = models.SmallIntegerField(default=1)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    max_votes = models.SmallIntegerField(default=-1,blank=True,null=True)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Antwort"
        verbose_name_plural = "Antworten"
        ordering = ["position", "id"]

    def __unicode__(self):
        return self.value

    def __str__(self):
        return self.value

    @property
    def vote_count(self):
        return Vote.objects.filter(item=self).count()



class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    user = models.ForeignKey(get_user_model(), verbose_name='voter', on_delete=models.CASCADE)
    item = models.ForeignKey(Item, verbose_name='voted item', null=True,
                             on_delete=models.CASCADE)
    text = models.TextField(default="", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vote"
        verbose_name_plural = "Votes"
