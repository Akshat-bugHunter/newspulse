#!/usr/bin/env bash

set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed_news
python manage.py fetch_news