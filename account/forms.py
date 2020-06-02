from django import forms
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth import get_user_model

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
        active_users = UserModel._default_manager.filter(**{
            '%s__iexact' % email_field_name: email,
            'is_active': True,
        })
        return active_users
