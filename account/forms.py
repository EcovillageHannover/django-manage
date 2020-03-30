from django import forms

class CreateAccountForm(forms.Form):
    token = forms.CharField(label='Aktivierungscode', max_length=1000)
