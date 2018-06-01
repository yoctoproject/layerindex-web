from celery import Celery
from django.core.mail import EmailMessage
from . import utils
import os
import time
import subprocess
from datetime import datetime

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

@tasks.task(bind=True)
def run_update_command(self, branch_name, update_command):
    utils.setup_django()
    from layerindex.models import Update
    updateobj = Update.objects.get(task_id=self.request.id)
    updateobj.started = datetime.now()
    updateobj.save()
    output = ''
    update_command = update_command.replace('%update%', str(updateobj.id))
    update_command = update_command.replace('%branch%', branch_name)
    try:
        output = utils.runcmd(update_command, os.path.dirname(os.path.dirname(__file__)))
    except subprocess.CalledProcessError as e:
        output = e.output
    except Exception as e:
        output = str(e)
    finally:
        updateobj.log = output
        updateobj.finished = datetime.now()
        updateobj.save()
