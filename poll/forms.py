# coding: utf-8

from django import forms
from .models import Poll, Item, Vote, PollCollection

import logging
logger = logging.getLogger(__name__)


class PollForm(forms.ModelForm):
    class Meta:
        model = Poll
        fields = []

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.votes = Vote.objects.filter(poll=self.instance, user=user)

        self.results = None

        if self.instance.poll_type == Poll.TEXT:
            self.fields['text'] = forms.CharField(widget=forms.Textarea)
            self.initial['text'] = ""
            for vote in self.votes:
                self.initial['text'] += vote.text
        else:
            self.choices = []
            items = Item.objects.filter(poll=self.instance)
            for item in reversed(sorted(items, key=lambda i: i.position)):
                self.choices.append((item.id, item.value))

            if self.instance.poll_type == Poll.RADIO:
                self.fields['choice'] = forms.ChoiceField(
                    choices=self.choices,
                    widget=forms.RadioSelect
                )
                if len(self.votes) > 0 and self.votes[0].item:
                    self.initial['choice'] = self.votes[0].item.pk
            else:
                self.fields['choices'] = forms.MultipleChoiceField(
                    choices=self.choices,
                    widget=forms.CheckboxSelectMultiple
                )
                self.initial['choices'] = [v.item.pk for v in self.votes]

    @property
    def user_voted(self):
        return any([v.user == self.user for v in self.votes])

    def clean_choice(self):
        data = self.cleaned_data['choice']
        return Item.objects.get(pk=data)

    def clean_choices(self):
        data = self.cleaned_data['choices']
        return [Item.objects.get(pk=x) for x in data]

    def save(self, user):
        old_votes = Vote.objects.filter(user=user, poll=self.instance)
        old_votes.delete()


        if 'text' in self.cleaned_data:
            vote = Vote.objects.create(user=user,
                                       poll=self.instance,
                                       text=self.cleaned_data['text']) 
            vote.save()
        elif 'choice' in self.cleaned_data:
            vote = Vote.objects.create(user=user,
                                       poll=self.instance,
                                       item=self.cleaned_data['choice'])
            vote.save()
        elif 'choices' in self.cleaned_data:
            for item in self.cleaned_data['choices']:
                vote = Vote.objects.create(user=user,
                                           poll=self.instance,
                                           item=item)
                vote.save()
        else:
            raise RuntimeError("Unknown Voting")
        

