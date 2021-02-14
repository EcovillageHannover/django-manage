# -*- coding: utf-8 -*-
from django.db import models
from django.db.models.manager import Manager
from django.contrib.auth import get_user_model
from django.urls import reverse


import logging
logger = logging.getLogger(__name__)

class Category(models.Model):
    title = models.CharField(max_length=255, unique=True)

    class Meta:
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"

    def __str__(self):
        return self.title


# Create your models here.
class Item(models.Model):
    owner = models.ForeignKey(get_user_model(),  on_delete=models.CASCADE)
    category = models.ForeignKey(Category,  on_delete=models.CASCADE,
                                 verbose_name = "Kategorie",
                                 help_text="In welcher Kategorie soll die Anzeige geschaltet sein?")

    name = models.CharField(max_length=255,
                            unique=False,
                            verbose_name="Anzeigentitel",
                            )
    description = models.TextField(default="",
                                   blank=True,
                                   verbose_name="Anzeigentext",
                                   help_text="Formatierung mit Markdown",
                                   )

    is_published = models.BooleanField(default=True,
                                       verbose_name = "Anzeige aktiv?",
                                       help_text="Wenn eine Anzeige deaktiviert ist, kannst nur du sie sehen."
                                       )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name = "Anzeige"
        verbose_name_plural = "Anzeigen"


    def __str__(self):
        return str(self.category) + " | "+ self.name

    def get_absolute_url(self):
        return reverse('blackboard:view', args=[self.pk])



