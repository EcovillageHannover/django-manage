# coding: utf-8

from django_auth_ldap.backend import LDAPBackend
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import Group
from django.forms import modelform_factory
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
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from account.signals import user_changed, group_changed




import evh.settings as config
from .models import parse_token, Invite, ldap_addgroup, LDAP, GroupProfile, make_username
from .forms import *
from .mailman import Mailman


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
        logger.error(f"Invalid Token: {e} {token}")
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
    user = request.user
    return render(request, 'account/profile.html', {
        'user': request.user,
        'groups': [group.name for group in user.groups.all()],
        'own_groups':  LDAP().owned_groups(user.username),
    })

################################################################
# Group
def __resolve_group(request, group):
    groups = Group.objects.filter(name=group)
    if len(groups) != 1:
        return HttpResponse('NotFound', status=404)

    #if not request.user.is_superuser:
    if groups[0] not in LDAP().owned_groups(request.user.username):
        return HttpResponse('Permission denied', status=403)

    return groups[0]

@login_required
def group(request, group):
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group


    GroupProfileForm = modelform_factory(GroupProfile,
                                               fields=('mailinglist_intern',
                                                       'mailinglist_announce'))

    if request.method == 'POST':
        form = GroupProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.group = group
            profile.save()
        else:
            return HttpResponse('Bad Form', status=503)
    else:
        profile, _ = GroupProfile.objects.get_or_create(group=group)

    # Mailinglist
    m3 = Mailman()
    mlists = m3.get_lists()

    return render(request, 'account/group.html', {
        'group': group,
        'group_profile_form': GroupProfileForm(instance=profile),
        'members': LDAP().group_members(group),
        'mlist_discuss': mlists.get(f"{group}"),
        'mlist_news': mlists.get(f"{group}-news"),
    })


@login_required
def group_member_remove(request, group, user):
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group

    members = LDAP().group_members(group)
    for member in members:
        if member["username"] == user:
            break
    else:
        return HttpResponse('Group Member not found', status=404)

    if request.method == 'POST':
        if LDAP().group_member_change(group, user, mode="remove"):
            messages.add_message(request, messages.SUCCESS,
                                 f"Nutzer {user} entfernt.")

            user_changed.send(sender=group_member_remove, username=user)
            group_changed.send(sender=group_member_remove, group=group)
        else:
            messages.add_message(request, messages.ERROR,
                                 f"Nutzer {user} entfernen fehlgeschlagen.")
        return HttpResponseRedirect(request.POST['next'])


    return render(request, 'account/confirm.html', dict(
        title="Gruppenmitglied entfernen?",
        question=f"Soll der Nutzer <strong>{user}</strong> aus der Gruppe {group} entfernt werden?",
        yes="Ja, Mitglied entfernen",
        next=reverse('account:group', args=[group])
    ))

@login_required
def group_member_add(request, group):
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group
    group_url = reverse('account:group', args=[group])

    user = request.GET.get("user", "")
    User = LDAP().search_user(user)
    if not User:
        messages.add_message(request, messages.ERROR,
                             f"Nutzer '{user}' nicht gefunden!")
        return HttpResponseRedirect(group_url)

    username = User["username"]
    full_name = "%s %s (%s)" %(User["vorname"], User["nachname"], User["username"])

    
    members = LDAP().group_members(group)
    for member in members:
        if member["username"] == username:
            messages.add_message(request, messages.INFO,
                                 f"Nutzer {full_name} ist bereits in der Gruppe!")
            return HttpResponseRedirect(group_url)

    if request.method == 'POST':
        if LDAP().group_member_change(group, username, mode="add"):
            messages.add_message(request, messages.SUCCESS,
                                 f"Nutzer {username} hinzugefügt.")

            user_changed.send(sender=group_member_add, username=username)
            group_changed.send(sender=group_member_add, group=group)
        else:
            messages.add_message(request, messages.ERROR,
                                 f"Nutzer {username} hinzufügen fehlgeschlagen.")

        return HttpResponseRedirect(request.POST['next'])


    return render(request, 'account/confirm.html', dict(
        title="Gruppenmitglied hinzufügen?",
        question=f"Soll der Nutzer <strong>{full_name}</strong> der Gruppe {group} hinzugefügt werden?",
        yes="Ja, Mitglied hinzufügen?",
        next=group_url
    ))


from .management.commands.invite import AccountInformation, send_invite_mail

@login_required
def group_member_invite(request, group):
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group
    group_url = reverse('account:group', args=[group])

    email = request.GET.get("email", "").strip()
    vorname = request.GET.get("vorname", "").strip()
    nachname = request.GET.get("nachname", "").strip()
    if not email or not vorname or not nachname:
        messages.add_message(request, messages.ERROR,
                                 f"Vorname, Nachname UND E-Mailaddresse werden zum Einladen benötigt.")
        return HttpResponseRedirect(group_url)
    username = make_username(vorname, nachname)

    

    user = LDAP().search_user(email)
    user = user or LDAP().search_user(username)
    if user:
        username = user["username"]
        messages.add_message(request, messages.INFO,
                                 f"Nutzer hat bereits einen Account (oder es gibt eine Namensdopplung): {username}")
        return HttpResponseRedirect(group_url)

    # Send Invite Mail
    if request.method == 'POST':
        account = AccountInformation(
            vorname=vorname,
            nachname=nachname,
            username=username,
            email=email,
            group=[group.name])
        send_invite_mail(account)
        messages.add_message(request, messages.INFO,
                                 f"Einladung verschickt!")
        return HttpResponseRedirect(group_url)

    return render(request, 'account/confirm.html', dict(
        title="Nutzer zum EVH einladen?",
        question=f"Es soll <strong>{vorname} {nachname} &lt;{email}&gt;</strong> eingeladen werden. Dieser erhält durch diese Einladung eine Mail, mit der er/sie sich einen EVH-Account erstellen kann, der sofort zur Gruppe <strong>{group}</strong> hinzugefügt wird? ",
        yes="Ja, Mensch einladen!",
        next=group_url
    ))
