# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import itertools
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import EmailMessage
import csv
import io
from collections import defaultdict


import evh.settings as config
from .models import *
from .forms import *

import logging
logger = logging.getLogger("blackboard")


@login_required
def index(request):
    items = defaultdict(list)
    for item in Item.objects.filter():
        top_level = item.category.title.split(">",1)[:-1]
        top_level = [x.strip() for x in top_level]
        items[" » ".join(top_level)].append(item)
    context = {'items': list(sorted(items.items())),
               'foobar': 23}
    return render(request, "blackboard/list.html", context)

@login_required
def view(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if not item.is_published and request.user != item.owner:
        return Http404()
    return render(request, 'blackboard/view.html', dict(
        item=item,
        email_form=ItemEmailForm(),
    ))

def _addr(user):
    if hasattr(user, 'userprofile'):
        primary, secondaries = user.userprofile.mail_for_mailinglist()
        return primary.lower()
    else:
        return user.email

@login_required
def mail(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if not item.is_published:
        return Http404()
    if request.method == 'POST':
        form = ItemEmailForm(request.POST)
        if form.is_valid():
            body = render_to_string('blackboard/contact_mail.txt', dict(
                sender=request.user,
                receiver=item.owner,
                msg=form.cleaned_data['message'],
                item=item,
                config=config,
            ))

            email = EmailMessage(
                f'[EVH Anzeigen] {request.user} antwortet auf {item.name}',
                body,
                config.EMAIL_FROM,
                [_addr(item.owner)],
                reply_to=[_addr(request.user)],
            )
            email.send()
            messages.add_message(request, messages.SUCCESS,
                             "Nachricht wurde erfolgreich verschickt.")
            return HttpResponseRedirect(reverse('blackboard:view', args=[item.pk]))

    else:
        return Http404()
