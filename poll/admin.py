# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import (get_group_perms, get_groups_with_perms, get_perms_for_model, get_user_perms,
                                get_users_with_perms, get_objects_for_user, assign_perm, remove_perm)

import logging
logger = logging.getLogger(__name__)

from .models import PollCollection, Poll, Item, Vote

class ExtendedGuardedModelAdmin(GuardedModelAdmin):
    def get_model_objs(self, request, action=None, klass=None):
        opts = self.opts
        actions = [action] if action else ['view', 'change', 'delete']

        target_klass = klass if klass else opts.model

        if hasattr(self, 'permission_authority'):
            klass, pointers = self.permission_authority
        elif klass:
            pass
        else:
            klass = opts.model

        model_name = klass._meta.model_name

        objects = get_objects_for_user(
            user=request.user,
            perms=['{}_{}'.format(perm, model_name) for perm in actions],
            klass=klass,
            any_perm=True)

        if hasattr(self, 'permission_authority'):
            for klass, ptr in pointers:
                objects = klass.objects.filter(
                    **{f'{ptr}__in': objects}
                )

        return objects

    def has_module_permission(self, request):
        if super(GuardedModelAdmin, self).has_module_permission(request):
            return True
        return self.get_model_objs(request).exists()

    def get_queryset(self, request):
        if request.user.is_superuser:
            return super(GuardedModelAdmin, self).get_queryset(request)

        data = self.get_model_objs(request)
        return data

    def has_perm(self, request, obj, action):
        opts = self.opts
        codename = '{action}_{model_name}'.format(action=action, model_name=opts.model_name)
        if obj:
            if hasattr(self, 'permission_authority'):
                return True
            return request.user.has_perm('{label}.{codename}'.format(label=opts.app_label, codename=codename), obj)
        else:
            return self.get_model_objs(request, action).exists()

    def has_view_permission(self, request, obj=None):
        return self.has_perm(request, obj, 'view')

    def has_change_permission(self, request, obj=None):
        return self.has_perm(request, obj, 'change')

    def has_delete_permission(self, request, obj=None):
        return self.has_perm(request, obj, 'delete')

    def save_model(self, request, obj, form, change):
        result = super(GuardedModelAdmin, self).save_model(request, obj, form, change)
        if not request.user.is_superuser and not change:
            opts = self.opts
            actions = ['view', 'add', 'change', 'delete']
            [assign_perm('{}.{}_{}'.format(opts.app_label, action, opts.model_name), request.user, obj)
             for action in actions]
        return result

    @staticmethod
    def remove_obj_perms(obj):
        perms_dict = get_users_with_perms(obj, attach_perms=True)
        perms_dict.update(get_groups_with_perms(obj, attach_perms=True))
        for user_or_group in perms_dict:
            [remove_perm(perm, user_or_group, obj) for perm in perms_dict[user_or_group]]

    def delete_model(self, request, obj):
        self.remove_obj_perms(obj)
        return super(GuardedModelAdmin, self).delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        [self.remove_obj_perms(obj) for obj in queryset]
        return super(GuardedModelAdmin, self).delete_queryset(request, queryset)


################################################################
# Register your models here.
class PollItemInline(admin.TabularInline):
    model = Item
    extra = 0

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj):
        return True

    def has_delete_permission(self, request, obj):
        return True

    fields = (('value', 'export_key', 'position', 'max_votes'),)
    readonly_fields = ('vote_count',)



class PollAdmin(ExtendedGuardedModelAdmin):
    permission_authority = (PollCollection, [(Poll, 'poll_collection')])

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
    fields = (('question', 'poll_type', 'is_published', 'position'),)
    show_change_link = True

    def has_add_permission(self, request, obj):
        return True

    def has_change_permission(self, request, obj):
        return True

    def has_delete_permission(self, request, obj):
        return True



class PollCollectionAdmin(ExtendedGuardedModelAdmin):
    user_can_access_owned_objects_only = True
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


