import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "case_ledger.settings")

app = Celery("case_ledger")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
