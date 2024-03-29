# coding: utf-8

from django_auth_ldap.backend import LDAPBackend
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group
from django.forms import modelform_factory
from django.shortcuts import render
from django.template import loader
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
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
from account import signals
from impersonate.signals import session_begin
from django.contrib.auth import get_user_model
from datetime import datetime
import sys




import evh.settings as config
from evh.utils import parse_token
from .models import Invite, LDAP, GroupProfile, make_username
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
                logger.error(f"account/create/error: {e}")
                import traceback
                logger.error("%s", traceback.format_exc())
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
    # Login user
    user = authenticate(username=username, password=password)
    login(request, user)

    ################################################################
    # Initial Groups
    invite = Invite.find_by_mail(mail)
    groups = [g for g in (invite.groups or "").split(",") if g]
    for group in groups:
        group = Group.objects.get(name=group)
        signals.group_member_add.send(sender=create,
                                      group=group,
                                      member=user)
        messages.add_message(request, messages.SUCCESS,
                             "Du wurdest der Gruppe %s hinzugefügt" % group)

    signals.user_changed.send(sender=create, user=user)

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
    signals.user_changed.send(sender=profile, user=request.user)
    user = request.user
    ldap = LDAP()
    if hasattr(user, 'userprofile'):
        mlist_primary, _ = user.userprofile.mail_for_mailinglist()
    else:
        mlist_primary = user.email

    return render(request, 'account/profile.html', {
        'user': request.user,
        'user_profile_form': UserProfileForm(instance=request.user),
        'groups': [group.name for group in user.groups.all()],
        'own_groups':  ldap.owned_groups(user.username),
        'managed_users': ldap.managed_users(user.username),
        'mlists': Mailman().get_lists(mlist_primary).values(),
    })

@login_required
def user_profile_save(request):
    user = request.user

    form = UserProfileForm(request.POST, instance=user)
    if form.is_valid():
        form.save(request)
        messages.add_message(request, messages.SUCCESS,
                             f"Deine Einstellungen wurden gespeichert")
    else:
        messages.add_message(request, messages.ERROR,
                             f"Fehler beim Speichern")
    return HttpResponseRedirect(reverse('account:profile'))


@login_required
def impersonate(request, user):
    managed_users = LDAP().managed_users(request.user.username)
    if user not in {x['username'] for x in managed_users} \
       and not request.user.is_superuser:
        return HttpResponse('Permission denied', status=403)

    new_user = LDAPBackend().populate_user(user)
    if not new_user:
        return HttpResponse('Not found', status=404)

    logger.info(f"Impersonating {new_user}")

    messages.add_message(request, messages.SUCCESS,
                                 f"Du bist ab sofort als '{new_user.username}' angemeldet.")

    prev_path = request.META.get('HTTP_REFERER')
    if prev_path:
        request.session['_impersonate_prev_path'] = \
            request.build_absolute_uri(prev_path)

    request.session['_impersonate'] = new_user.pk
    request.session.modified = True  # Let's make sure...

    # can be used to hook up auditing of the session
    session_begin.send(
        sender=None,
        impersonator=request.user,
        impersonating=new_user,
        request=request
    )

    return HttpResponseRedirect(request.POST.get('next') or prev_path or '/')


################################################################
# Group
def __resolve_group(request, group):
    groups = Group.objects.filter(name=group)
    if len(groups) != 1:
        return HttpResponse('NotFound', status=404)

    #if not request.user.is_superuser:
    if groups[0] not in LDAP().owned_groups(request.user.username) \
       and not request.user.is_superuser:
        return HttpResponse('Permission denied', status=403)

    # Ensure that the Group Profile exists
    GroupProfile.objects.get_or_create(group=groups[0])

    return groups[0]

def __resolve_user(username, email=None):
    # Resolve user
    UserModel = get_user_model()
    try:
        return UserModel.objects.get(username=username)
    except UserModel.DoesNotExist:
        if not email: return None
        try:
            return UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            pass
    return None


def __user_in_group(user, group):
    """Checks if user is in group. Double check via LDAP"""
    if group.name in user.groups.values_list('name',flat=True) or \
       user.username in set([g['username'] for g in LDAP().group_members(group)]):
        return True
    return False


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

    # Mailinglist
    m3 = Mailman()
    mlists = m3.get_lists()

    members = group.user_set.all().order_by('last_name')
    all_children_groups = set(group.groupprofile.all_children)
    is_hierarchical = len(all_children_groups) > 0
    subgroups = {}
    if is_hierarchical:
        for member in members:
            subgroups[member] = all_children_groups & set(member.groups.all())

    return render(request, 'account/group.html', {
        'group': group,
        'profile': group.groupprofile,
        'is_hierarchical': is_hierarchical,
        'group_profile_form': GroupProfileForm(instance=group.groupprofile),
        'owners': [m['username'] for m in LDAP().group_owners(group)],
        'members': [(x, subgroups.get(x)) for x in members], 
        'mlist_discuss': mlists.get(f"{group}"),
        'mlist_news': mlists.get(f"{group}-news"),
    })

# @login_required
# def group_view(request, group):
#     if group != 'genossenschaft':
#         return HttpResponse('Permission denied', status=403)

#     group = __resolve_group(request, group)
#     if isinstance(group, HttpResponse):
#         return group

#     if len(set(request.user.groups.values_list('name',flat=True))\
#            & set(['dorfrat-kronsberg-koordination', 'evh-admin'])) == 0:
#         return HttpResponse('Permission denied', status=403)

#     return render(request, 'account/group_view.html', {
#         'group': group,
#         'members': LDAP().group_members(group),
#         'profile': profile,
#     })




@login_required
def group_member_add(request, group):
    # Resolve Group
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group
    group_url = reverse('account:group', args=[group])

    # Resolve User
    param = request.GET.get("user", "")
    user = __resolve_user(param, email=param)

    if not user:
        messages.add_message(request, messages.ERROR,
                             f"Nutzer '{param}' nicht gefunden!")
        return HttpResponseRedirect(group_url)
    full_name = "%s %s (%s)" %(user.first_name, user.last_name, user.username)

    # Check user is in Group (DB and LDAP)
    if __user_in_group(user, group):
        messages.add_message(request, messages.INFO,
                             f"Nutzer {full_name} ist bereits in der Gruppe!")
        return HttpResponseRedirect(group_url)

    if request.method == 'POST':
        signals.user_changed.send(sender=group_member_add, user=user)
        signals.group_member_add.send(sender=group_member_add,
                                      group=group,
                                      member=user)
        messages.add_message(request, messages.SUCCESS,
                             f"Nutzer {user.username} hinzugefügt.")

        return HttpResponseRedirect(request.POST['next'])


    return render(request, 'account/confirm.html', dict(
        title="Gruppenmitglied hinzufügen?",
        question=f"Soll der Nutzer <strong>{full_name}</strong> der Gruppe {group.name} hinzugefügt werden?",
        yes="Ja, Mitglied hinzufügen?",
        next=group_url
    ))


@login_required
def group_member_remove(request, group, username):
    group_url = reverse('account:group', args=[group])
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group

    user = __resolve_user(username)
    if not user:
        messages.add_message(request, messages.ERROR,
                             f"Nutzer '{username}' nicht gefunden!")
        return HttpResponseRedirect(group_url)


    if not __user_in_group(user, group):
        messages.add_message(request, messages.INFO,
                             f"Nutzer {user} ist nicht in der Gruppe!")
        return HttpResponseRedirect(group_url)

    if request.method == 'POST':
        signals.user_changed.send(sender=group_member_remove, user=user)
        signals.group_member_remove.send(sender=group_member_remove,
                                             group=group, member=user)
        messages.add_message(request, messages.SUCCESS,
                             f"Nutzer {user.username} entfernt.")

        return HttpResponseRedirect(request.POST['next'])

    return render(request, 'account/confirm.html', dict(
        title="Gruppenmitglied entfernen?",
        question=f"Soll der Nutzer <strong>{user}</strong> aus der Gruppe {group} entfernt werden?",
        yes="Ja, Mitglied entfernen",
        next=reverse('account:group', args=[group])
    ))


def mark_group_for_update(group):
    # Mark all Parents for sync
    for g in [group] + group.groupprofile.all_parents:
        g.groupprofile.updated_at = timezone.now()
        g.groupprofile.save()


@login_required
@user_passes_test(lambda u: u.is_superuser)
def group_manager_add(request, group, username):
    group_url = reverse('account:group', args=[group])
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group

    user = __resolve_user(username)
    if not user:
        messages.add_message(request, messages.ERROR,
                             f"Nutzer '{username}' nicht gefunden!")
        return HttpResponseRedirect(group_url)


    if not __user_in_group(user, group):
        messages.add_message(request, messages.INFO,
                             f"Nutzer {user} ist nicht in der Gruppe!")
        return HttpResponseRedirect(group_url)

    if request.method == 'POST':
        LDAP().group_member_change(group.name, user.username, mode="add",field='owner')
        mark_group_for_update(group)
        messages.add_message(request, messages.SUCCESS,
                             f"Nutzer {user.username} ist jetzt Manager.")

        return HttpResponseRedirect(request.POST['next'])

    return render(request, 'account/confirm.html', dict(
        title="Gruppenmanager hinzufügen",
        question=f"Willst du den Nutzer <strong>{user}</strong> zum Manager der Gruppe <strong>{group}</strong> machen?",
        yes="Ja, Zum Manager ernennen!",
        next=reverse('account:group', args=[group])
    ))

@login_required
@user_passes_test(lambda u: u.is_superuser)
def group_manager_remove(request, group, username):
    group_url = reverse('account:group', args=[group])
    group = __resolve_group(request, group)
    if isinstance(group, HttpResponse):
        return group

    user = __resolve_user(username)
    if not user:
        messages.add_message(request, messages.ERROR,
                             f"Nutzer '{username}' nicht gefunden!")
        return HttpResponseRedirect(group_url)


    if not __user_in_group(user, group):
        messages.add_message(request, messages.INFO,
                             f"Nutzer {user} ist nicht in der Gruppe!")
        return HttpResponseRedirect(group_url)

    if request.method == 'POST':
        LDAP().group_member_change(group.name, user.username, mode="remove",field='owner')
        mark_group_for_update(group)
        messages.add_message(request, messages.SUCCESS,
                             f"Nutzer {user.username} ist nicht länger Manager.")

        return HttpResponseRedirect(request.POST['next'])

    return render(request, 'account/confirm.html', dict(
        title="Gruppenmanager entfernen",
        question=f"Willst du den Nutzer <strong>{user}</strong> die Managerrechte der Gruppe <strong>{group}</strong> entziehen?",
        yes="Ja, Rechte entziehen!",
        next=reverse('account:group', args=[group])
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

    # FIXME: Make Django Database the primary source
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
        preface=f"Du wurdest von {request.user} zur Gruppe {group.name} eingeladen."
        send_invite_mail(account, preface=preface)

        # Bestätigungsmail
        msg_plain = render_to_string('registration/invite-confirm.txt',
                                     dict(vorname=vorname,
                                          nachname=nachname,
                                          email=email,
                                          inviter=request.user,
                                          group=group))

        send_mail("[EVH Account] Nutzer eingeladen: " +username, msg_plain,
                  config.EMAIL_FROM,
                  [request.user.email, config.EMAIL_FROM],
                  fail_silently=True)

        messages.add_message(request, messages.INFO,
                                 f"Einladung verschickt!")
        return HttpResponseRedirect(group_url)

    return render(request, 'account/confirm.html', dict(
        title="Nutzer zum EVH einladen?",
        question=f"Es soll <strong>{vorname} {nachname} &lt;{email}&gt;</strong> eingeladen werden. Dieser erhält durch diese Einladung eine Mail, mit der er/sie sich einen EVH-Account erstellen kann, der sofort zur Gruppe <strong>{group}</strong> hinzugefügt wird? ",
        yes="Ja, Mensch einladen!",
        next=group_url
    ))

def group_mailman(request, group):
    groups = Group.objects.filter(name=group)
    if len(groups) != 1:
        return HttpResponse('NotFound', status=404)


    return render(request, 'group/mailman.txt',
                  dict(group=groups[0],
                       ecotopia=('ecotopia' in str(groups[0]))),
                  content_type='text/plain; charset=utf8'
                  )
