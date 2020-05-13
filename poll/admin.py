# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin

from .models import PollCollection, Poll, Item, Vote

# Register your models here.


class PollItemInline(admin.TabularInline):
    model = Item
    extra = 0


class PollAdmin(admin.ModelAdmin):
    model = Poll
    list_display = ('poll_collection', 'question', 'poll_type', 'vote_count', 'is_published')
    inlines = [PollItemInline,]

admin.site.register(Poll, PollAdmin)

################################################################


class PollInline(admin.TabularInline):
    model = Poll
    extra = 0
    fields = (('question', 'poll_type', 'is_published'),)
    show_change_link = True


class PollCollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_published', 'is_active')
    inlines = [PollInline,]

admin.site.register(PollCollection, PollCollectionAdmin)

################################################################

class VoteAdmin(admin.ModelAdmin):
    list_display = ('poll', 'user', 'created_at')
    list_filter = ('poll', 'created_at')

admin.site.register(Vote, VoteAdmin)


