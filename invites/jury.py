#!/bin/bash

exec ./manage.py  invite \
     --source:csv invites/jury.csv \
     --modify:group wettbewerb-jury \
     $*
