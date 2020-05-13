# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.db.models.manager import Manager
from django.contrib.auth import get_user_model

import datetime

# Create your models here.
class PollCollection(models.Model):
    date = models.DateField(default=datetime.date.today)
    name = models.CharField(max_length=255, unique=True)

    # List of Group Names
    visible         = models.CharField(max_length=255,default="",blank=True)
    visible_results = models.CharField(max_length=255,default="",blank=True)

    is_published = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "PollCollection"
        verbose_name_plural = "PollCollections"

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.name

    def __check_acl(self, rights, user):
        if rights == "":
            return True
        allowed_groups = [x.strip() for x in rights.split(",")]
        groups = [g.name for g in user.groups.all()]
        if set(allowed_groups) & set(groups):
            return True
        if user.usename in groups:
            return True
        return False
    
    def visible_for(self, user):
        if not self.is_published:
            return False
        return self.__check_acl(self.visible, user)

    def visible_results_for(self, user):
        return self.__check_acl(self.visible_results or self.visible, user)

class Poll(models.Model):
    poll_collection = models.ForeignKey(PollCollection, on_delete=models.CASCADE)

    RADIO = 'RA'
    CHECKBOX = 'CE'
    TEXT = 'TX'
    TYPE_CHOICES = (
        (RADIO, 'Radiobox'),
        (CHECKBOX, 'Checkbox'),
        (TEXT, 'Free Text')
    )

    poll_type = models.CharField(max_length=2,
                                 choices=TYPE_CHOICES,
                                 default=RADIO) 

    question = models.CharField(max_length=255, unique=True)
    description = models.TextField(default="")

    is_published = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Poll"
        verbose_name_plural = "Polls"

    def __unicode__(self):
        return self.question

    def __str__(self):
        return self.question

    def get_vote_count(self):
        return Vote.objects.filter(poll=self).count()
    vote_count = property(fget=get_vote_count)

class Item(models.Model):
    value = models.CharField(max_length=255, unique=True)
    position = models.SmallIntegerField(default=1)
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Answer"
        verbose_name_plural = "Answers"

    def __unicode__(self):
        return self.value

    def __str__(self):
        return self.value

    def get_vote_count(self):
        return Vote.objects.filter(item=self).count()
    vote_count = property(fget=get_vote_count)


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
