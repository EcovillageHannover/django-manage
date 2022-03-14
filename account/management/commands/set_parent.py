# coding: utf-8

from account.models import *
from django.core.management.base import BaseCommand, CommandError


import logging
logger = logging.getLogger(__name__)



class Command(BaseCommand):
    help = 'Send account invite mails'

    def add_arguments(self, parser):
        parser.add_argument("--parent", required=True)
        parser.add_argument("groups", nargs="*")

    def handle(self, *args, **options):
        if not options['parent']:
            parent = None
        else:
            parent = Group.objects.get(name=options['parent'])
        groups = [Group.objects.get(name=g)
                  for g in options['groups']]

        for group in groups:
            if group.groupprofile.parent != parent:
                logger.info("Set %s.parent = %s", group, parent)
                group.groupprofile.parent = parent
                group.groupprofile.save()
