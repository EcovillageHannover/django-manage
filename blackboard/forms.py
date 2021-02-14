from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import UserPassesTestMixin
from .models import Item
from django.contrib.auth.mixins import LoginRequiredMixin
import logging
from  django.forms import Form, CharField, Textarea
logger = logging.getLogger("blackboard")


class ItemCreate(LoginRequiredMixin, CreateView):
    model = Item
    fields = ['name', 'category', 'is_published', 'description']

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        self.object.save()

        return HttpResponseRedirect(self.get_success_url())

class ItemUpdate(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Item
    fields = ItemCreate.fields

    def test_func(self):
        return self.get_object().owner == self.request.user

class ItemDelete(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Item
    success_url = reverse_lazy('blackboard:index')

    def test_func(self):
        return self.get_object().owner == self.request.user


class ItemEmailForm(Form):
    message = CharField(widget=Textarea(attrs={'class': 'form-control', 'placeholder': 'Deine Nachricht.'}))
