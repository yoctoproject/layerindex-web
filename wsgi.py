import os, sys
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
sys.path.append('/var/www/html/layerindex')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
