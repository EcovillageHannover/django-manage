# coding: utf-8

from django.http import HttpResponse
from django.shortcuts import render
from django.template import loader
from django.contrib import messages
from django.core.mail import send_mail
import ldap
import ldap.modlist
import passlib.pwd
from passlib.hash import ldap_md5_crypt
import logging



import evh.settings as config
from .models import parse_token
from .forms import *


# Get an instance of a logger
logger = logging.getLogger(__name__)

def create(request, token=None):
    context = dict(
        form=CreateAccountForm(),
        contact=config.EMAIL_FROM,
    )
    
    # Wenn wir kein Token haben, zeigen wir das Token-Eingabe Formular an.
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        context['form'] = CreateAccountForm(request.POST)
        if context['form'].is_valid():
            token = context['form'].cleaned_data['token']

    if token is None:
        return render(request, 'account/create.html', context)

    context['token'] = token.strip()

    try:
        args = parse_token(config.account_link_key, token)
        vorname, nachname, username, mail = args
    except Exception as e:
        messages.add_message(request, messages.ERROR, f"Invalides Token: {e}")
        logger.error(f"Invalid Token: {e}")
        return render(request, 'account/create.html', context)

    context['vorname'] = vorname
    context['nachname']  = nachname
    context['username'] = username
    context['mail'] = mail

    if request.POST.get('submit') == 'true':
        checkboxes = [
            request.POST.get('datensatz'),
            request.POST.get('datenschutz'),
            request.POST.get('create')
        ]
        if checkboxes == ['true', 'true', 'true']:
            try:
                __create(request, context,
                         vorname, nachname, username, mail)
            except Exception as e:
                messages.add_message(request, messages.ERROR, f"Beim Erstellen des Accounts ist etwas schief gelaufen. Kontaktieren Sie das Team Digitales: {e}")
                logger.error("account/create/error: {e}")
                return render(request, 'account/create.html', context)
        else:
            messages.add_message(request, messages.ERROR, "Deine Zustimmung ist erforderlich um einen Account anzulegen.")
            print("token")
    return render(request, 'account/create.html', context)


def __create(request, context, vorname, nachname, username, mail):
    conn = ldap.initialize(config.ldap_host)
    conn.simple_bind_s(config.ldap_user, config.ldap_password)


    #note salt generation is automatically handled
    password = passlib.pwd.genword()
    password_hash = ldap_md5_crypt.encrypt(password)


    ################################################################
    # LDAP Account
    dn = f"cn={username},{config.ldap_user_dn}"
    entry = {
        'objectClass': [b'inetOrgPerson'],
        'cn': [username.encode()],
        'sn': [nachname.encode()],
        'givenName': [vorname.encode()],
        'mail': [mail.encode()],
        'displayName': [f"{vorname} {nachname}".encode()],
        'userPassword': [password_hash.encode()],
    }

    try:
        modlist = ldap.modlist.addModlist(entry)
        conn.add_s(dn, modlist)
        logger.info(f"create/LDAP: success {dn}")
    except ldap.ALREADY_EXISTS:
        messages.add_message(request, messages.ERROR,
                             "Der Account existiert bereits. Du solltest bereits eine Mail mit Zugangsinformationen erhalten haben.")
        context['success'] = False
        return
    except Exception as e:
        messages.add_message(request, messages.ERROR,
                             f"LDAP Fehler: {e}")
        logger.error(f"create/LDAP: {e}")
        context['success'] = False
        return

    ################################################################
    # Mail versenden
    try:
        send_mail(
        '[EVH Account] Accountinformationen',
        f"""Hallo {vorname} {nachname},

dein Account wurde erfolgreich angelegt. Die Zugangsdaten zu diesem
Account, den du für alle Webdienste des ecovillage nutzen kannst, sind:

  Benutzername: {username}
  Passwort: {password}

Eine ausführliche Übersicht über all unsere Dienste findest du unter:

  https://account.my-evh.de

Die erste Anlaufstelle nach der Anmeldung, bei der du direkt mit
anderen Engagierten in Kontakt treten kannst ist unser Chat, für den
wir bereits eine kleine Anleitung erstellt haben:

  Anleitung:  https://account.my-evh.de/static/matrix-anleitung.pdf
  Chat:       https://chat.my-evh.de

-- Team Digitales""",
            config.EMAIL_FROM,
            [mail],
            fail_silently=False,
        )
    except Exception as e:
        messages.add_message(request, messages.ERROR,
                             f"Versenden der Passwort-Mail ist fehlgeschlagen: {e}")
        logger.error(f"create/SMTP: {e}")
        conn.delete_s(dn)
        logger.error(f"create/LDAP: deleted {dn}")
        context['success'] = False
        return

    messages.add_message(request, messages.SUCCESS,
                         "Account wurde erstellt. Du hast eine E-Mail mit dem Passwort erhalten.")
    context['password'] = password
    context['success'] = True
