from django import forms
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.db.models import Q
from .models import GroupProfile

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
        
