# coding: utf-8

from django_auth_ldap.backend import LDAPBackend
from django.http import HttpResponse
from django.contrib.auth import authenticate, login
from django.shortcuts import render
from django.template import loader
from django.contrib import messages
from django.core.mail import send_mail
import ldap
import ldap.modlist
import passlib.pwd
from passlib.hash import ldap_md5_crypt
import logging
from django.contrib.auth.decorators import login_required
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from account.signals import user_changed



import evh.settings as config
from .models import parse_token, Invite, ldap_addgroup
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
        args = parse_token(config.SECRET_KEY, token)
        CREATE, vorname, nachname, username, mail = args
        if CREATE != 'create':
            raise RuntimeError("Falscher Tokentyp")
    except Exception as e:
        messages.add_message(request, messages.ERROR, f"Invalides Token: {e} ({token})")
        logger.error(f"Invalid Token: {e}")
        return render(request, 'account/create.html', context)

    context['vorname'] = vorname
    context['nachname']  = nachname
    context['username'] = username
    context['mail'] = mail

    context['invite'] = Invite.find_by_mail(mail)

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
    return render(request, 'account/create.html', context)


def __create(request, context, vorname, nachname, username, mail):
    conn = ldap.initialize(config.AUTH_LDAP_SERVER_URI)
    conn.simple_bind_s(config.AUTH_LDAP_BIND_DN, config.AUTH_LDAP_BIND_PASSWORD)

    #note salt generation is automatically handled
    password = passlib.pwd.genword()
    password_hash = ldap_md5_crypt.encrypt(password)


    ################################################################
    # LDAP Account
    dn = f"cn={username},{config.AUTH_LDAP_USER_DN}"
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
    # Initial Groups
    invite = Invite.find_by_mail(mail)
    groups = [g for g in (invite.groups or "").split(",") if g]
    for group in groups:
        if ldap_addgroup(username, group):
            messages.add_message(request, messages.SUCCESS,
                                 "Du wurdest der Gruppe %s hinzugefügt" % group)


    ################################################################
    # Login user
    user = authenticate(username=username, password=password)
    login(request, user)

    user_changed.send(sender=create, username=username)

    ################################################################
    # Mail versenden
    try:
        c = dict(
            reason='create',
            vorname=vorname,
            nachname=nachname,
            username=username,
            user=user,
            password=password
        )

        msg_plain = render_to_string('registration/account_info.txt', c)

        send_mail("[EVH Account] Account angelegt",
                  msg_plain,
                  config.EMAIL_FROM,
                  [mail],
                  fail_silently=False)
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

    send_mail("[EVH Account] Nutzer angelegt: " +username, "",
                  config.EMAIL_FROM,
                  [config.EMAIL_FROM],
                  fail_silently=True)



def password_reset(request, uidb64, token):
    # urlsafe_base64_decode() decodes to bytestring
    uid = urlsafe_base64_decode(uidb64).decode()
    user = UserModel._default_manager.get(pk=uid)
    token_generator = default_token_generator
    user = LDAPBackend().populate_user(user.username)

    if not user:
        return HttpResponse("Kein bekannter Benutzer")

    context = dict(
        reason='password_reset',
        vorname=user.ldap_user.attrs['givenName'][0],
        nachname=user.ldap_user.attrs['sn'][0],
        username=user.username,
        user=user
    )
    if not token_generator.check_token(user, token):
        messages.add_message(request, messages.INFO,
                             "Passwort-Reset-Link bereits verbraucht")

        if not request.user:
            return HttpResponse("Invalid Request. (43)")
    else:
        # Establish 
        conn = ldap.initialize(config.AUTH_LDAP_SERVER_URI)
        conn.simple_bind_s(config.AUTH_LDAP_BIND_DN, config.AUTH_LDAP_BIND_PASSWORD)

        #note salt generation is automatically handled
        password = passlib.pwd.genword()
        password_hash = ldap_md5_crypt.encrypt(password).encode('utf-8')

        modlist = [(ldap.MOD_REPLACE, 'userPassword', [password_hash] )]

        logger.info(f"reset/LDAP: changed to {user.ldap_user.dn}")
        conn.modify_s(user.ldap_user.dn, modlist)


        context['password'] = password

        msg_plain = render_to_string('registration/account_info.txt', context)
        send_mail("[EVH Account] Neues Passwort",
                  msg_plain,
                  config.EMAIL_FROM,
                  [user.email],
                  fail_silently=False)
        
        user = authenticate(username=user.username, password=password)
        login(request, user)

        messages.add_message(request, messages.SUCCESS,
                             "Passwort erfolgreich zurückgesetzt.")

    return render(request, 'registration/password_reset_success.html', context)



@login_required
def profile(request):
    user_changed.send(sender=profile, username=request.user.username)
    user = LDAPBackend().populate_user(request.user.username)
    return render(request, 'account/profile.html', {
        'user': user
    })
