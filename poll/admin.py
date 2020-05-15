# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from guardian.admin import GuardedModelAdmin

from .models import PollCollection, Poll, Item, Vote

# Register your models here.


class PollItemInline(admin.TabularInline):
    model = Item
    extra = 0


class PollAdmin(admin.ModelAdmin):
    def poll_collection_display(self, obj):
        pc = obj.poll_collection
        return mark_safe(
            "<a href={}>{}</a>"\
            .format(
                reverse('admin:{}_{}_change'\
                        .format(pc._meta.app_label, pc._meta.model_name),
                        args=(pc.pk,)),
                pc))

    model = Poll
    exclude = ('poll_collection',)
    list_display = ('question', 'poll_collection_display', 'poll_type', 'vote_count', 'is_published')
    list_filter = ('poll_collection',)
    inlines = [PollItemInline,]

    def view_on_site(self, obj):
        url = reverse('poll:view', kwargs={'poll_collection_id': obj.poll_collection.pk})
        return url +"?p={}".format(obj.pk)


admin.site.register(Poll, PollAdmin)

################################################################


class PollInline(admin.TabularInline):
    model = Poll
    extra = 0
    fields = (('question', 'poll_type', 'is_published'),)
    show_change_link = True


class PollCollectionAdmin(GuardedModelAdmin):
    list_display = ('name', 'is_published', 'is_active')
    inlines = [PollInline,]

    def view_on_site(self, obj):
        url = reverse('poll:view', kwargs={'poll_collection_id': obj.pk})
        return url

admin.site.register(PollCollection, PollCollectionAdmin)

################################################################

# class VoteAdmin(admin.ModelAdmin):
#     list_display = ('poll', 'user', 'created_at')
#     list_filter = ('poll', 'created_at')
# 
# admin.site.register(Vote, VoteAdmin)


