# coding: utf-8

from django import forms
from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.db.models import Q
from .models import GroupProfile, UserProfile
from .mailman import Mailman

import logging
logger = logging.getLogger(__name__)

UserModel = get_user_model()


class CreateAccountForm(forms.Form):
    token = forms.CharField(label='Aktivierungscode', max_length=1000)

class PasswordResetForm(DjangoPasswordResetForm):
    def get_users(self, email):
        """Given an email, return matching user(s) who should receive a reset.

        This allows subclasses to more easily customize the default policies
        that prevent inactive users and users with unusable passwords from
        resetting their password.
        """
        email_field_name = UserModel.get_email_field_name()
        for user in UserModel._default_manager.filter(**{
                '%s__iexact' % email_field_name: email,
                'is_active': True,
            }):
            yield user, getattr(user, email_field_name)

        for user in UserModel._default_manager.filter(
                userprofile__recovery_mail__iexact=email,
                is_active=True,
                ):
            yield user, user.userprofile.recovery_mail

    def clean_email(self):
        email = self.cleaned_data["email"]
        users = list(self.get_users(email))
        if len(users) != 1:
            logger.error("User not unambiqusly found: %s %s", email, users)
            raise ValidationError(
                "Die angegebene E-Mailaddresse konnte keinem Nutzer eindeutig zugeordnet werden",
                code='email_not_found',
            )
        return users

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.html',
             use_https=False, token_generator=default_token_generator,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Generate a one-use only link for resetting password and send it to the
        user.
        """
        if not domain_override:
            current_site = get_current_site(request)
            site_name = current_site.name
            domain = current_site.domain
        else:
            site_name = domain = domain_override

        for user, user_email in self.cleaned_data["email"]:
            context = {
                'email': user_email,
                'domain': domain,
                'site_name': site_name,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': token_generator.make_token(user),
                'protocol': 'https' if use_https else 'http',
                **(extra_email_context or {}),
            }
            self.send_mail(
                subject_template_name, email_template_name, context, from_email,
                user_email, html_email_template_name=html_email_template_name,
            )
            logger.info("Sent recovery email to: %s", user_email)


class UserProfileForm(forms.Form):
    def __init__(self, *args,  instance=None, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        assert instance, "No user given"
        if hasattr(instance, 'userprofile'):
            primary, s = instance.userprofile.mail_for_mailinglist()
            emails = [primary] + list(s)
        else:
            primary = instance.email
            emails = [instance.email]

        self.fields['mailinglist_mail'] = \
            forms.ChoiceField(
                label="Mailaddresse für Mailinglisten",
                help_text="An diese Mailaddresse werden wir Mailinglisten-Nachrichten schicken.",
                choices=sorted([(x, x) for x in emails]),
                widget=forms.RadioSelect
            )

        self.initial['mailinglist_mail'] = primary

    def save(self, request):
        user = request.user
        if not hasattr(user, "userprofile"):
            userprofile = UserProfile.objects.create(user=user)
        else:
            userprofile = user.userprofile

        if userprofile.mailinglist_mail != self.cleaned_data['mailinglist_mail']:
            previous_primary = userprofile.mailinglist_mail
            primary = self.cleaned_data['mailinglist_mail']
            userprofile.mailinglist_mail = primary
            userprofile.save()

            m = Mailman()
            for mlist in m.get_lists(previous_primary):
                rc0 = m.subscribe(mlist, primary)
                rc1 = m.unsubscribe(mlist, previous_primary)
                messages.add_message(request, messages.SUCCESS,
                                     f"Abonement für {mlist} wurde aktualisiert")
                
