## Standalone Setup

**NOTE:** The standalone setup is most suitable for development and is not
recommended for production; for production use the Docker-based setup
covered in the main [README.md](README.md).

In order to run this application standalone, you will need:

- Python 3.10+
- Django 5.2 LTS, as pinned in `requirements.txt`
- RabbitMQ
- For production usage, a web server set up to host Django applications
  (not needed for local-only testing/development)
- A database system supported by Django (SQLite, MariaDB/MySQL, etc.).
- Third-party Django/python modules as detailed by `requirements.txt`.
  If you're using pip, you can install these by running:

  ```sh
  pip install -r requirements.txt
  ```

  (See below for a virtualenv-based setup which is easy to work with.)
- On the machine that will run the backend update script (which does not
  have to be the same machine as the web server, however it does still
  have to have Django installed, have the same or similar configuration
  in `settings.py` and have access to the database used by the web
  application):
  - A Python version supported both by Django and by the BitBake of
    the OpenEmbedded branches being parsed
  - Python dependencies as per `requirements.txt` (we still need Django
    etc. here since we interact with the database through Django's ORM.)

### Example virtualenv-based setup for the above

Python's virtualenv provides an easy way to isolate the python dependencies
of applications such as the layer index. Here's an example of setting up a
virtualenv for the layer index that's particularly useful for development.
(This assumes a Debian-based distribution, adjust accordingly for other
distros).

1. Install required host distro packages (some of these are required by
   pip to build the dependencies; it's also assumed you want MariaDB as
   the database backend):

   ```sh
   sudo apt-get update
   sudo apt-get install python3-venv libmariadb-dev build-essential python3-dev libjpeg-dev libz-dev libfreetype6-dev libssl-dev mariadb-server rabbitmq-server
   ```

2. Work around path issues (you may not need this):

   ```sh
   sudo ln -s /usr/bin/mariadb_config /usr/bin/mysql_config
   ```

3. Create a Python 3 virtualenv (path can be anywhere you like):

   ```sh
   python3 -m venv /path/to/desired/venv
   ```

4. Activate the virtualenv:

   ```sh
   . /path/to/desired/venv/bin/activate
   ```

5. Install requirements:

   ```sh
   pip install -r requirements.txt
   ```


### Setting up MariaDB/MySQL

Assuming you wish to use MariaDB/MySQL for storing the database - the
following is completely standard, but to save you having to look it up
elsewhere:

1. Start the server:

   ```sh
   sudo /etc/init.d/mysql start
   ```

2. Set the root password and secure the database server:

   ```sh
   sudo mysql_secure_installation
   ```

3. Create a database (substituting "mydatabase" with desired database
   name):

   ```sh
   mysql -u root -p
   ```

   ```sql
   CREATE DATABASE mydatabase CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```


### Configuration and running

1. Edit `settings.py` to specify a database, `EMAIL_HOST`, `SECRET_KEY` and
   other settings specific to your installation. Ensure you set
   `LAYER_FETCH_DIR` to an absolute path to a location with sufficient
   space for fetching layer repositories. Modify `RABBIT_BROKER`
   and `RABBIT_BACKEND` to reflect the settings used by your RabbitMQ
   server.

2. Run the following commands within the layerindex-web directory to
   initialise the database:

   ```sh
   ./manage.py migrate
   ./manage.py createsuperuser
   ```

3. You can test the web application locally by setting `DEBUG = True` in
   `settings.py` and running the following:

   ```sh
   ./manage.py runserver
   ```

   Then visit http://127.0.0.1:8000/layerindex/ with your browser. As
   with all Django applications there is an admin interface available
   at http://127.0.0.1:8000/admin/ also. The initial login and password
   will be those you entered in the step above when creating an admin
   account.

   **NOTE:** This local server should only be used for testing - for
   production you need to use a proper web server and have `DEBUG` set
   to `False` (or use the Docker-based setup).

   1. In order to process asynchronous tasks like sending email,
      you will need to run a Celery worker:

      ```sh
      celery -A layerindex.tasks worker --loglevel=info
      ```

4. To import layer data from the public instance at layers.openembedded.org
   you can run the following (defaults to the master branch only):

   ```sh
   layerindex/tools/import_layers.py -d https://layers.openembedded.org
   ```

   Alternatively you can add layers individually using the separate
   `layerindex/tools/import_layer.py` script or through the admin interface.


## SMTP test server

If you want to test email functionality (e.g. for password reset, layer
submission or other notifications) without sending real emails, set Django's
console email backend in `settings.py`:

```python
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

Every email is then printed to the console running the server (or the Celery
worker, for emails sent from background tasks) instead of being sent.


## Running the tests

The tests use pytest and pytest-django, which are not in `requirements.txt`:

```sh
pip install pytest pytest-django
```

To run the full suite as CI does, in the Docker image against a throwaway
MariaDB container, run this from the top of the source tree:

```sh
docker/run-tests.sh
```

This is the only way to run `tests/test_update.py`, which fetches
openembedded-core, meta-layerindex-test and BitBake from the network and runs
the update scripts (BitBake only runs on Linux).

To run the other tests directly, set `SECRET_KEY` in `settings.py` and point it
at a MariaDB/MySQL server where your database user may create databases
(pytest-django creates and removes a `test_<name>` database), then run:

```sh
pytest --ignore=tests/test_update.py tests/
```

`tests/test_dockersetup.py` tests the files `dockersetup.py` writes. It needs only
pytest and PyYAML, and is skipped inside the Docker image:

```sh
python3 -m pytest tests/test_dockersetup.py
```

On GitHub, `.github/workflows/ci.yml` runs `docker/run-tests.sh` and
`tests/test_dockersetup.py` for pushes to master and master-next and for pull
requests to master. `.github/workflows/safety.yml` scans the packages
installed in the Docker image for known vulnerabilities on each push and
weekly, if the repository has a `SAFETY_API_KEY` secret.


## Updating OpenEmbedded data

You will likely want to update the OpenEmbedded layer information on a regular
basis. To do that:

Incremental update:

```sh
layerindex/update.py
```

Reload all data (should only be needed if the database structure has
changed as part of an upgrade of the application code):

```sh
layerindex/update.py -r
```
