# Celery task definitions for the layer index app
#
# Copyright (C) 2018 Intel Corporation
# Author: Paul Eggleton <paul.eggleton@linux.intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

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
        os.makedirs(settings.TASK_LOG_DIR)
    except FileExistsError:
        pass
    logfile = os.path.join(settings.TASK_LOG_DIR, 'task_%s.log' % str(self.request.id))
    retcode = 0
    erroutput = None
    try:
        output = utils.runcmd(update_command, os.path.dirname(os.path.dirname(__file__)), outfile=logfile, shell=True)
    except subprocess.CalledProcessError as e:
        output = e.output
        erroutput = output
        retcode = e.returncode
    except Exception as e:
        print('ERROR: %s' % str(e))
        output = str(e)
        erroutput = output
        retcode = -1
    finally:
        updateobj.log = output
        updateobj.finished = datetime.now()
        updateobj.retcode = retcode
        updateobj.save()
    return {'retcode': retcode, 'output': erroutput}
