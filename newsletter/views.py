# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.core.mail import EmailMultiAlternatives
from django.contrib import messages
from django.apps import apps
from django.shortcuts import render
from django.template.loader import render_to_string
from django import forms
from django.utils.html import mark_safe


from evh.utils import format_token, parse_token
import evh.settings_local as config

from account.mailman import Mailman


# Get an instance of a logger
import logging
logger = logging.getLogger(__name__)

newsletter_config = apps.get_app_config('newsletter')

class SubscribeForm(forms.Form):
    mail = forms.EmailField(label='E-Mailaddresse', max_length=100)
    newsletters = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple,
                                            choices=newsletter_config.form_choices())


def subscribe(request):
    context = { }
    
    if request.method == 'POST':
        form = SubscribeForm(request.POST)
        if form.is_valid():
            newsletters = form.cleaned_data['newsletters']
            mask = newsletter_config.encode(newsletters)
            email = 'stettberger@dokucode.de'
            logger.info("Subscribe %s to: %s (%d)", email, newsletters, mask)

            token = format_token(config.SECRET_KEY, ['subscribe', email, hex(mask)])
            msg_plain = render_to_string('newsletter/confirmation.txt', dict(
                config=config,
                token=token.decode(),
                newsletters=newsletters
            ))

            msg = EmailMultiAlternatives(subject="[EVH] Bestätigung zur Newsletteranmeldung",
                                 body=msg_plain,
                                 from_email=config.EMAIL_FROM,
                                 to=[email],
                                 reply_to=[config.EMAIL_FROM])
            msg.send()

            messages.add_message(request, messages.SUCCESS,
                                 mark_safe('Wir haben eine Mail an %s mit einem Bestätigungslink geschickt. <strong>Klicke auf den darin enthaltenen Link!</strong> um die Anmeldung abzuschließen.'%email))

        else:
            messages.add_message(request, messages.ERROR, 'Invalide Auswahl')
            context['form'] = SubscribeForm()
    else:
        context['form'] = SubscribeForm()

    return render(request, "newsletter/subscribe.html", context)



def subscribe_confirm(request, token):
    try:
        args = parse_token(config.SECRET_KEY, token)
        TYPE, email, mask = args
        if TYPE != 'subscribe':
            raise RuntimeError("Falscher Tokentyp")

        newsletters = newsletter_config.decode(int(mask, 16))
    except Exception as e:
        messages.add_message(request, messages.ERROR, f"Invalides Token: {e} ({token})")
        logger.error(f"Invalid Token: {e} {token}")
        return render(request, 'newsletter/subscribe.html', {})

    
    mailman = Mailman()
    for nl in newsletters:
        rc = mailman.subscribe(nl, email)
        if rc == 1:
            messages.add_message(request, messages.SUCCESS,
                                 'Eintragung (%s) war erfolgreich'% nl)
        elif rc == 0:
            messages.add_message(request, messages.WARNING,
                                 'Eintragung (%s): Du warst bereits eingetragen' % nl)
        else:
            messages.add_message(request, messages.ERROR,
                                 'Eintragung (%s) fehlgeschlagen: %s' % (nl, rc))

    return render(request, "newsletter/subscribe.html", {})

