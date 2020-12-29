# coding: utf-8

from django import forms
from .models import Poll, Item, Vote, PollCollection
from  django.utils.html import mark_safe

import logging
logger = logging.getLogger(__name__)

class HorizontalRadioSelect(forms.RadioSelect):
    template_name = 'horizontal_select.html'

class DisableRadioSelect(forms.RadioSelect):
    def __init__(self, attrs=None, choices=(), disabled_choices=()):
        super(DisableRadioSelect, self).__init__(attrs, choices=choices)
        self.disabled_choices = disabled_choices

    def create_option(self, *args, **kwargs):
        option = super(DisableRadioSelect, self).create_option(*args, **kwargs)
        logger.info("%s", option)

        if option.get('value') in self.disabled_choices:
            option['attrs']['disabled'] = True
            option['attrs']['class'] += ' disabled'

        return option

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

        elif self.instance.poll_type == Poll.PRIO:
            items = Item.objects.filter(poll=self.instance)
            for item in sorted(items, key=lambda i: i.position):

                self.fields['prio-' + str(item.id)] = forms.ChoiceField(
                    choices=[(x, str(x)) for x in range(0, 6)],
                    widget = HorizontalRadioSelect(attrs={'title': item.value})
                )
            for vote in self.votes:
                self.initial['prio-' + str(vote.item.pk)] = vote.text
        elif self.instance.poll_type == Poll.YESNONONE:
            items = Item.objects.filter(poll=self.instance)
            for item in sorted(items, key=lambda i: i.position):
                self.fields['yesnonone-' + str(item.id)] = forms.ChoiceField(
                    choices=[('ja',         'Ja'),
                             ('nein',       'Nein'),
                             ('enthaltung', 'Enthaltung')],
                    widget = HorizontalRadioSelect(attrs={'title': item.value})
                )
            for vote in self.votes:
                self.initial['yesnonone-' + str(vote.item.pk)] = vote.text
        else:
            self.choices = []
            items = Item.objects.filter(poll=self.instance)

            disabled_choices = []
            for item in sorted(items, key=lambda i: i.position):
                choice = (item.id, item.value)

                # Some Choices are already full
                if item.max_votes >= 0:
                    votes  = Vote.objects.filter(poll=self.instance, item=item)
                    users = [v.user for v in votes]
                    choice = (item.id, item.value + " (Plätze: %d/%d)" % (len(votes), item.max_votes))
                    if len(votes) >= item.max_votes and self.user not in users:
                        disabled_choices.append(item.id)
                        choice = (choice[0], mark_safe(f"<span style='color: gray;'>{choice[1]}</span>"))

                # Select Choices
                self.choices.append(choice)





            logger.info("Disabled Choices: %s", disabled_choices)

            if self.instance.poll_type == Poll.RADIO:
                self.fields['choice'] = forms.ChoiceField(
                    choices=self.choices,
                    widget=DisableRadioSelect
                )
                if len(self.votes) > 0 and self.votes[0].item:
                    self.initial['choice'] = self.votes[0].item.pk
                self.fields['choice'].widget.disabled_choices = disabled_choices
            else:
                self.fields['choices'] = forms.MultipleChoiceField(
                    choices=self.choices,
                    widget=forms.CheckboxSelectMultiple
                )
                self.initial['choices'] = [v.item.pk for v in self.votes]

    @property
    def user_voted(self):
        return any([v.user == self.user for v in self.votes])

    @property
    def show_results(self):
        pc = self.instance.poll_collection
        normal_view = pc.can_analyze(self.user) \
            and (self.user_voted or (not pc.is_active))
        edit_view = pc.can_change(self.user) or self.user.is_superuser
        return normal_view or edit_view

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
        elif any([x.startswith('prio-') or x.startswith('yesnonone-')
                  for x in self.cleaned_data]):
            for key in self.cleaned_data:
                type, item_id = key.split('-', 1)
                if type not in ('prio', 'yesnonone'): continue
                item_id = int(item_id)
                item = Item.objects.get(pk=item_id)
                vote = Vote.objects.create(user=user,
                                           poll=self.instance,
                                           item=item,
                                           text=self.cleaned_data[key])
                vote.save()
        else:
            raise RuntimeError("Unknown Voting")
        
