from celery import Celery
from django.core.mail import EmailMessage
from . import utils
import os
import time

try:
    import settings
except ImportError:
    # not in a full django env, so settings is inaccessible.
    # setup django to access settings.
    utils.setup_django()
    import settings

tasks = Celery('layerindex',
    broker=settings.RABBIT_BROKER,
    backend=settings.RABBIT_BACKEND)

@tasks.task
def send_email(subject, text_content, from_email=settings.DEFAULT_FROM_EMAIL, to_emails=[]):
    # We seem to need to run this within the task
    utils.setup_django()
    msg = EmailMessage(subject, text_content, from_email, to_emails)
    msg.send()
