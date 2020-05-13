# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .utils import set_cookie

from .models import Poll, Item, Vote, PollCollection
from .forms import *


# Create your views here.


@login_required
def poll_collection_list(request):
    pc = PollCollection.objects.all()
    pc = [p for p in pc if p.visible_for(request.user)]
    pc = sorted(pc, key=lambda p: (not p.is_active, p.created_at))
    context = {"poll_collections": pc}
    return render(request, "poll/list.html", context)


def poll_collection_view(request, poll_collection_id):
    try:
        pc = PollCollection.objects.get(pk=poll_collection_id)
    except:
        return HttpResponse('Wrong parameters', status=400)

    if not pc.visible_for(request.user):
        return HttpResponse('NotFound', status=404)

    poll_forms = []
    for p in Poll.objects.filter(poll_collection=pc):
        if not p.is_published:
            continue
        vote = Vote.objects.filter(poll=p, user=request.user)
        poll_forms.append(PollForm(instance=p, votes=vote))

    context = {
        'poll_collection': pc,
        'forms': poll_forms,
        'next': request.path, # Come back after voting
    }

    return render(request, "poll/view.html", context)


@login_required
def vote(request, poll_id):
    try:
        poll = Poll.objects.get(pk=poll_id)
    except Poll.DoesNotExist:
        return HttpResponse('Wrong parameters', status=400)

    if not poll.poll_collection.visible_for(request.user):
        return HttpResponse('NotFound', status=404)

    if not poll.poll_collection.is_active:
        messages.add_message(request, messages.ERROR,
           "Die Umfrage ist beendet. Entscheidungen können nicht mehr verändert werden.")
        return HttpResponseRedirect(request.POST['next'])


    if request.method == 'POST':
        form = PollForm(request.POST,instance=poll)
        if form.is_valid():
            form.save(request.user)
            messages.add_message(request, messages.SUCCESS,
                                 "Deine Stimme wurde gespeichert.")

            return HttpResponseRedirect(request.POST['next'])


    return HttpResponse(status=400)





def percentage(poll, item):
    poll_vote_count = poll.get_vote_count()
    if poll_vote_count > 0:
        return float(item.get_vote_count()) / float(poll_vote_count) * 100
