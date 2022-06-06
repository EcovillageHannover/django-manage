# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import itertools
import time

from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .utils import set_cookie
from zlib import crc32
from collections import defaultdict
import csv
import json
import logging
logger = logging.getLogger("poll")
import io

from .models import Poll, Item, Vote, PollCollection
from .forms import *


# Create your views here.


@login_required
def poll_collection_list(request):
    pcs = PollCollection.list_for_user(request.user)
    pcs = sorted(pcs, key=lambda p: (not p.is_active, p.created_at))
    for pc in pcs:
        pc.unvoted = len(pc.get_unvoted(request.user))
    context = {
        "poll_collections": pcs,
    }

    return render(request, "poll/list.html", context)


@login_required
def poll_collection_view(request, poll_collection_id):
    try:
        pc = PollCollection.objects.get(pk=poll_collection_id)
    except:
        return HttpResponse('Wrong parameters', status=400)

    if not pc.can_view(request.user):
        return HttpResponse('NotFound', status=404)

    search_q = request.GET.get('q','')
    search_tag = request.GET.get('tag','')
    search_p = request.GET.get('p','')
    last_voted = int(request.GET.get('last_voted','-1'))

    terms = [x.strip() for x in search_q.split()]

    # Tag Autodetection
    available_tags = set()
    for p in Poll.objects.filter(poll_collection=pc):
        available_tags.update(p.tags.names())

    if set(terms) & available_tags:
        search_tag = list(set(terms) & available_tags)[0]
        terms.remove(search_tag)
        search_q = " ".join(terms)

    poll_forms = []
    number = 1
    for p in Poll.objects.filter(poll_collection=pc).order_by('is_published', 'position', 'id'):
        # Number all polls of this Poll Collcetion
        p.number = number
        number += 1

        # If the result is visible, also the unpublished polls are visible
        if not p.is_published:
            if pc.can_change(request.user) \
               or pc.can_export(request.user):
                pass
            else:
                continue

        form = PollForm(instance=p, user=request.user)

        if search_tag:
            if search_tag == 'Unbeantwortet':
                if form.user_voted:
                    continue
            elif search_tag not in p.tags.names():
                continue

        if search_p and int(search_p) != p.pk:
            continue

        if search_q:
            for term in terms:
                if term in (p.question + p.description):
                    break
            else:
                continue

        poll_forms.append(form)

    tags = list(sorted(available_tags)) + ["Unbeantwortet"]
    context = {
        'poll_collection': pc,
        'voting_users': len(Vote.objects.filter(poll__poll_collection__id=pc.id).distinct('user')),
        'poll_forms': poll_forms,
        'search_q':    search_q,
        'search_p':    search_p,
        'search_tag':  search_tag,
        'last_voted': last_voted,
        'available_tags': tags,
        'print_mode':  request.GET.get('print_mode'),
        'can_view':    pc.can_view(request.user),
        'can_vote':    pc.can_vote(request.user),
        'can_analyze': pc.can_analyze(request.user),
        'can_change':  pc.can_change(request.user),
        'can_export':  pc.can_export(request.user),
        'next': request.path, # Come back after voting
    }

    return render(request, "poll/view.html", context)


@login_required
def api_vote(request, poll_id: int):
    r_args = {'content_type': 'application/json'}

    if request.method not in ('DELETE', 'POST'):
        return HttpResponse(json.dumps({'error': 'Method not allowed!'}), status=405, **r_args)
    try:
        poll = Poll.objects.get(pk=poll_id)
    except Poll.DoesNotExist:
        return HttpResponse(json.dumps({'error': 'No such poll'}), status=404, **r_args)

    if not poll.poll_collection.is_active:
        return HttpResponse(
            json.dumps({
                'error': 'Die Umfrage ist beendet. Entscheidungen können nicht mehr verändert werden.'
            }),
            status=400,
            **r_args)

    if not poll.poll_collection.can_vote(request.user):
        return HttpResponse(json.dumps({'error': 'You are not authorized to vote on this poll'}), status=403, **r_args)

    if request.method == 'DELETE':
        return api_vote_delete(request, poll)
    elif request.method == 'POST':
        return api_vote_update(request, poll)


def api_vote_delete(request, poll: Poll):
    r_args = {'content_type': 'application/json'}

    request_data = {} if request.method == 'DELETE' else json.loads(request.body.decode('utf-8'))
    form = PollForm(request_data, instance=poll, user=request.user)

    vote: Vote = Vote.objects \
        .filter(poll=poll, user=request.user)
    vote.delete()

    return HttpResponse(json.dumps({
        'message': f'Deine Stimme für \'{poll}\' wurde gelöscht.',
        'pollResults': poll.get_result_data(form.show_results)
    }))


def api_vote_update(request, poll: Poll):
    r_args = {'content_type': 'application/json'}

    request_data = {} if request.method == 'DELETE' else json.loads(request.body.decode('utf-8'))
    form = PollForm(request_data, instance=poll, user=request.user)

    if form.is_valid():
        form.save(request.user)
        return HttpResponse(json.dumps({
            'message': f'Deine Stimme für \'{poll}\' wurde gespeichert.',
            'pollResults': poll.get_result_data(form.show_results)
        }), **r_args)
    else:
        logging.info("%s", form.errors)
        return HttpResponse(json.dumps({'error': f'Deine Wahl für \'{poll}\' konnte nicht gespeichert werden!'}),
                            status=500,
                            **r_args)

@login_required
def export_raw(request, poll_id):
    try:
        poll = Poll.objects.get(pk=poll_id)
    except Poll.DoesNotExist:
        return HttpResponse('Wrong parameters', status=400)

    can_export = poll.poll_collection.can_export(request.user)
    can_change = poll.poll_collection.can_change(request.user)

    if not (can_change or can_export):
        return HttpResponse('NotFound', status=404)

    votes = Vote.objects.filter(poll=poll_id)
    response = HttpResponse(
        content_type="text/csv",
        status=200)
    response['Content-Disposition'] = f'attachment; filename="poll_{poll_id}.csv'
    out = csv.writer(response, quotechar='"', escapechar='\\', delimiter=";")
    header = ["PollID", "Frage", "Abstimmungszeitpunkt"]
    if can_export:
        header += ["EVH Mitgliedsnummer", "Vorname", "Familienname", "E-Mail"]
    else:
        header += ['PollUserID']

    if poll.poll_type == Poll.RADIO:
        header += ["Auswahl"]
    elif poll.poll_type == Poll.TEXT:
        header += ["Text"]
    elif poll.poll_type in (Poll.YESNONONE, Poll.PRIO, Poll.CHECKBOX):
        header += [i.export_key or i.value for i in poll.items]
    else:
        return HttpResponse('Exporting this poll type is not supported', status=503)

    out.writerow(header)
    for user, votes in itertools.groupby(sorted(votes, key=lambda V: V.user.id), lambda V: V.user):
        votes = list(votes)
        mnr = ""
        email = user.email
        if hasattr(user, 'userprofile'):
            email, _ = user.userprofile.mail_for_mailinglist()

            if user.userprofile.evh_mitgliedsnummer:
                mnr = str(user.userprofile.evh_mitgliedsnummer)

        row = [poll_id,
               poll.question,
               votes[0].updated_at.strftime("%d.%m.%Y %H:%M")]
        if can_export:
            row += [
                mnr,
                user.first_name,
                user.last_name,
                email,
            ]
        else:
            row += [
                str(abs(crc32(f'{poll.poll_collection.id}.{user.id}'.encode())))
            ]

        if poll.poll_type == Poll.RADIO:
            #logger.info("%s: %s", user, set([v.item for v in votes]))
            assert len(set([v.item for v in votes])) == 1
            #logger.info("%s", votes)
            row += [votes[0].item.export_key or votes[0].item.value]
        elif poll.poll_type == Poll.TEXT:
            row += [votes[0].text.replace(";", " ")]
        elif poll.poll_type in (Poll.CHECKBOX, ):
            items = set([v.item for v in votes])
            row += [("1" if i in items else "")  for i in poll.items]
        elif poll.poll_type in (Poll.YESNONONE, Poll.PRIO):
            d = {v.item: v.text for v in votes}
            #logging.info("%s %s %s", user, poll.items, d)
            # assert len(poll.items) == len(d)
            row += [d.get(i) for i in poll.items]
        out.writerow(row)


    return response


@login_required
def export_pc_raw(request, poll_collection_id):
    try:
        pc = PollCollection.objects.get(pk=poll_collection_id)
    except PollCollection.DoesNotExist:
        return HttpResponse('Wrong parameters', status=400)

    can_export = pc.can_export(request.user)
    can_change = pc.can_change(request.user)

    if not can_export:
        return HttpResponse('NotFound', status=404)

    response = HttpResponse(
        content_type="text/csv",
        status=200)
    response['Content-Disposition'] = f'attachment; filename="pc_{poll_collection_id}.csv'

    header = ["PollCollectionID", "EVH Mitgliedsnummer", "Vorname", "Familienname", "E-Mail"]

    data = defaultdict(dict)
    polls = list(pc.polls.order_by('position').all())
    votes = Vote.objects.filter(poll__poll_collection__id=poll_collection_id)
    users = set([vote.user for vote in votes])
    for user in users:
        mnr = ""
        email = user.email
        if hasattr(user, 'userprofile'):
            email, _ = user.userprofile.mail_for_mailinglist()

            if user.userprofile.evh_mitgliedsnummer:
                mnr = str(user.userprofile.evh_mitgliedsnummer)
        row = data[user.id]
        row['EVH Mitgliedsnummer'] = mnr
        row['E-Mail'] = email
        row['Vorname'] = user.first_name
        row['Familienname'] = user.last_name

        for poll in polls:
            poll_votes = [x for x in votes if x.poll == poll and x.user == user]
            poll_key = poll.export_key or poll.question
            row['PollCollectionID'] = poll_collection_id
            if not poll_votes: continue

            if poll.poll_type == Poll.RADIO:
                assert len(set([v.item for v in poll_votes])) == 1, poll_votes
                row[poll_key] = (poll_votes[0].item.export_key or poll_votes[0].item.value)
            elif poll.poll_type == Poll.TEXT:
                row[poll_key] = poll_votes[0].text.replace("\n", "|").replace("\r", "").replace(";", " ")
            elif poll.poll_type in (Poll.CHECKBOX, ):
                for v in poll_votes:
                    key = v.item.export_key or v.item.value
                    row[f"{poll_key}/{key}"] = 1
            elif poll.poll_type in (Poll.YESNONONE, Poll.PRIO):
                for v in poll_votes:
                    key = v.item.export_key or v.item.value
                    row[f"{poll_key}/{key}"] = v.text
        for f in row.keys():
            if f not in header:
                header.append(f)

    out = csv.DictWriter(response, header, quotechar='"', escapechar='\\', delimiter=";")
    out.writeheader()
    out.writerows(data.values())

    return response

@login_required
def export_voters(request, poll_collection_id):
    try:
        pc = PollCollection.objects.get(pk=poll_collection_id)
    except:
        return HttpResponse('Wrong parameters', status=400)

    if not pc.can_export(request.user):
        return HttpResponse('NotFound', status=404)


    response = HttpResponse(
        content_type="text/html",
        status=200)
    response['Content-Disposition'] = f'attachment; filename="poll_collection_{poll_collection_id}.csv'
    out = csv.writer(response, quotechar='"', escapechar='\\', delimiter=";")

    header = ["EVH Mitgliedsnummer", "Vorname", "Familienname", "E-Mail"]
    out.writerow(header)

    votes = Vote.objects.filter(poll__poll_collection__id=poll_collection_id).distinct('user')

    for vote in votes:
        user = vote.user

        mnr = ""
        email = user.email
        if hasattr(user, 'userprofile'):
            email, _ = user.userprofile.mail_for_mailinglist()

            if user.userprofile.evh_mitgliedsnummer:
                mnr = str(user.userprofile.evh_mitgliedsnummer)

        out.writerow([
            mnr,
            user.first_name,
            user.last_name,
            email,
        ])

    return response


def percentage(poll, item):
    poll_vote_count = poll.get_vote_count()
    if poll_vote_count > 0:
        return float(item.get_vote_count()) / float(poll_vote_count) * 100

