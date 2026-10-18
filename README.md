# OE Layer Index web interface

This is a small Django-based web application that provides a way to
manage an index of OpenEmbedded metadata layers for use on top of
OE-Core.

There are two main methods of setting up this application - within
a set of Docker containers, or standalone. The Docker-based setup
is more suited for production whereas standalone is a bit easier
for development. This document will consider only the Docker-based
setup; for standalone please see [README.devel.md](README.devel.md).


## Docker Setup

The `dockersetup.py` script will set up and configure a cluster of 5 or 6
docker containers:

- `layersapp`: the application
- `layersdb`: the database
- `layersweb`: NGINX web server (as a proxy and for serving static content)
- `layerscelery`: Celery (for running background jobs)
- `layersrabbit`: RabbitMQ (required by Celery)
- `layerscertbot`: Runs certbot to keep letsencrypt certificates up-to-date
  (optional, default disabled)

The script will edit all necessary configuration files, build and launch all
containers, and do the initial database setup. It is advised that you start
with a .sql database file to prepopulate your database. The following
instructions will walk you through the setup.

1. Install docker and docker-compose per instructions:

   https://docs.docker.com/compose/install/

   **Note:** for latest docker-compose version follow the directions above,
   rather than using a perhaps outdated one provided by your distribution.

2. Run the setup script (`dockersetup.py`). You can optionally supply your
   hostname, proxy settings, a sql database file of layer mappings to import,
   and a host to container port mapping. For more information, run:

   ```sh
   ./dockersetup.py -h
   ```

   Example command to run containers with a proxy and with a database to
   import:

   ```sh
   ./dockersetup.py -d ~/databasedump.sql -p http://<proxyserver>:<port>
   ```

   **NOTE:** If you want email sending to work (required for user registration and
   password resets), you should use the `-e`/`--email-host` option to specify your
   outgoing email server.

   During the setup you will be asked for a username, email and password to
   set up a super user for the database.

3. Once the script completes, open a web browser and navigate to the URL
   printed out by the script. By default that would be: https://localhost:8081

4. If you have chosen to not supply a prepopulated database and are instead
   starting fresh, you should now follow the instructions in the
   "Database Setup" section of the main README.

5. If you need to rerun this script for any reason a second time, you'll need
   to choose between two modes:

   1. Updating (`-u`/`--update`) - updates the code and runs any database upgrades
      if applicable, or

   2. Reinstalling (`-r`/`--reinstall`) - deletes the containers and reinstalls
      from scratch. Be warned that this will throw away all data in the
      database.

   Note that updating with `-u`/`--update` will only work if the configuration
   changes originally made by `dockersetup.py` upon installation (e.g. passwords,
   hostname, etc.) are still present in the source tree. The generated
   passwords and secret key are written to `.env.local.*` files, which git
   ignores; keep them, and do not commit them.

### Environment files

The containers read their settings (secret key, database and RabbitMQ
credentials, email server, `DEBUG`) from `.env.<context>.<service>` files, where
`<context>` is `dev`, `staging` or `prod` and `<service>` is `app`, `celery`, `db` or `rabbit`:

- `docker-compose.yml` uses the `.env.dev.*` files, which hold development-only
  values. `dockersetup.py` copies them to `.env.local.*`, fills in the secrets
  it generates, and points `docker-compose.yml` at those copies.
- `docker-compose.staging.yml` and `docker-compose.prod.yml` use the
  `.env.staging.*` and `.env.prod.*` files. Their secrets are commented out, so
  nothing starts with a known password. Set the real values, and the
  hostname in the compose file, in a local commit on the server and never
  push them. Then run, for example:

  ```sh
  docker compose -f docker-compose.prod.yml up -d --build
  ```

The `.env*` files are excluded from the Docker images.

Other settings the app and celery files can set:

- `DEBUG`: `1`, `true` or `yes` enables Django's debug mode; anything else, or
  leaving it unset, keeps it off. Never enable it on a public site.
- `ENABLE_RRS`: `1` enables the Recipe Reporting System (see [README.rrs.md](README.rrs.md)).
- `DATABASE_PORT` (default `3306`) and `STATIC_ROOT` (default
  `/usr/share/nginx/html/static/`).

### Troubleshooting

- Network issues behind a proxy when building container: On some systems
  (particularly where dnsmasq is installed), `/etc/resolv.conf` is set to
  127.0.0.x, rather than your local DNS server. Docker will look there for
  your DNS server, and when it fails to find it it will default to using a
  public one (frequently 8.8.8.8). Many corporate proxies blocks public DNS
  servers, so you will need to manually supply the DNS server to docker using
  `/etc/docker/daemon.json`:

  ```json
  {"dns": ["xx.xx.xx.xx"]}
  ```


## Database Setup

Once the application is running you'll need to do a bit of further
setup within it:

1. For a fresh database (without importing any database dump) you will
   need layer data. To import the full set for the master branch from the
   public instance at layers.openembedded.org you can run the following:

   ```sh
   docker-compose run --rm layersapp /opt/layerindex/layerindex/tools/import_layers.py https://layers.openembedded.org
   ```

   Alternatively, you can populate the database manually -
   you'll need to add at least the openembedded-core layer to the
   database, or some equivalent that contains `conf/bitbake.conf` for
   the base system configuration. To add this, follow these steps:

   1. With the server running, go to the admin page -
      http://localhost:8080/admin/ by default (the hostname must
      match what the web server is configured for i.e. what you
      specified when running `dockersetup.py`). Use the login/password
      for the admin account specified during setup.

   2. Click on the "Submit Layer" button in the top right and
      enter the details for the core layer. To use the real
      openembedded-core layer, use these values:

      | Field                   | Value                                            |
      |-------------------------|--------------------------------------------------|
      | Layer name              | `openembedded-core`                              |
      | Layer type              | Base                                             |
      | Summary                 | Core metadata                                    |
      | Description             | Core metadata                                    |
      | Repository URL          | `https://git.openembedded.org/openembedded-core` |
      | Repository subdirectory | `meta`                                           |

      Once you have filled in the required values, click on the
      "Submit Layer" button.

      **NOTE:** The name of the layer must be "openembedded-core",
      unless you change `CORE_LAYER_NAME` in `settings.py` to match
      whatever alternative name you use here.

   3. The layer has been added but is not yet published. (For the
      public index this provides some protection against spam and
      malformed entries.) To publish it, click on the orange number
      next to your login name at the top right, click on the
      newly added layer entry, and then click on "Publish Layer".

2. If you need to support multiple branches of OpenEmbedded/BitBake
   where some require Python 2.x and others require Python 3.x, then
   you will need to set up "Python environment" records through the
   admin interface to correspond to these so that the right Python
   version gets used to parse the branch, and then set the
   "Update environment" field on each branch record to point to the
   appropriate environment. If you're using virtualenv you will need
   separate virtual environments set up for Python 2 and 3 which you
   should point to in the Python environment record.

3. Set the site name (as displayed in the top bar and page titles) by
   going into the admin interface (http://127.0.0.1:8000/admin/
   or equivalent), clicking on "Sites" at the bottom, and editing the
   first entry, setting "Display name" to the desired name.

4. You may wish to customise some of the page templates to suit your
   installation, in particular:
   - `templates/base.html`
   - `templates/layerindex/about.html`


## Updating OpenEmbedded data

You will likely want to update the OpenEmbedded layer information on a regular
basis. To do that by fetching and parsing all layer repositories, run the
following:

Incremental update:

```sh
docker-compose run --rm layersapp /opt/layerindex/layerindex/update.py
```

Reload all data (should only be needed if the database structure has
changed as part of an upgrade of the application code):

```sh
docker-compose run --rm layersapp /opt/layerindex/layerindex/update.py -r
```

Alternatively, you can update the data from an existing layer index instance
(as per above during setup):

```sh
docker-compose run --rm layersapp /opt/layerindex/layerindex/tools/import_layers.py https://layers.openembedded.org
```


## Upgrading from an earlier version

To upgrade the Docker-based setup from a previous release, update the code
(e.g. with `git pull`) and then run:

```sh
./dockersetup.py -u
```

This will rebuild the containers and run any required database migrations.

Installations set up by `dockersetup.py` before it used environment files
(see "Environment files" above) have their secret key and passwords in the
environment sections of `docker-compose.yml`. Carry them over by hand once:

1. Copy `docker-compose.yml` somewhere safe, then restore the tracked version
   (`git checkout docker-compose.yml`) and update the code.

2. For each of `app`, `celery`, `db` and `rabbit`, copy `.env.dev.<service>` to
   `.env.local.<service>` and fill in the values from the matching service
   in the old file: `SECRET_KEY`, `DATABASE_USER`, `DATABASE_PASSWORD`,
   `MYSQL_ROOT_PASSWORD`, `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS` and any
   `EMAIL_*` settings. Set `DEBUG=0` in `.env.local.app`, and make the files
   readable only by you (`chmod 600 .env.local.*`).

3. In `docker-compose.yml`, change the `env_file` entries from `.env.dev.*` to
   `.env.local.*`, and reapply your other changes from the old file (hostname,
   ports, certificate volumes and, if you use Let's Encrypt, the
   `layerscertbot` service).

4. Run `./dockersetup.py -u` as above.


## Support for OE-Classic

The Layer index optionally provides a means to index OE-Classic on a
one-off import basis and then compare what was there to what you have
now in the indexed layers (with some graphs showing how much of it has
been migrated/superseded). If you want to enable this, do the following:

1. From the admin interface, create a Branch record with the following
   values:
   - Name: `oe-classic` (must be exactly this!)
   - Bitbake branch: `1.12`
   - Enable updates: NOT ticked
   - Comparison: ticked
   - Update environment: if you have set up Python environments (for
     python2 vs python3 across different branches) then you'll need
     to select the python2 environment that you created here

2. Clone OE-Classic somewhere locally on the machine running the
   layer index:

   ```sh
   git clone https://git.openembedded.org/openembedded
   ```

3. Clone a bitbake somewhere locally and check out the 1.12 branch:

   ```sh
   git clone https://git.openembedded.org/bitbake -b 1.12
   ```

4. Run `import_classic.py`, specifying the path to OE-Classic and
   the bitbake you checked out:

   ```sh
   layerindex/tools/import_classic.py /path/to/bitbake112 /path/to/oeclassic
   ```

5. Update the migration status of OE-Classic recipes based on other
   layers in the database:

   ```sh
   layerindex/tools/update_classic_status.py
   ```

If you refresh the main page of the website, the OE-Classic data should
now show up at the bottom of the branch drop-down menu. On a periodic
basis you can repeat the last step to update the migration status in case
new recipes are brought across (or replacements are created). Users with
sufficient permissions can also manually update the migration status on
the OE-Classic recipe detail pages within the website, which is useful
for example when there's a replacement recipe in another layer that
doesn't have the same name, so the `update_classic_status.py` script
wouldn't be able to pick it up.


## Setting up other distro comparisons

The Layer Index also provides optional functionality to enable comparison
with other distributions (currently RPM-based only) in a similar manner to
OE-Classic comparison documented above. To set this up you need to perform
the following steps:

1. From the admin interface, set up the appropriate entries:

   1. Create a Branch with the following values:
      - Bitbake branch: `<any dummy value>`
      - Enable updates: NOT enabled
      - Comparison: enabled

   2. Create a Layer. Typically this would have the same name as
      the branch although that is not a requirement. The "Comparison"
      checkbox should be ticked. If the packages are in separate
      repositories (one per package, as is typical in RPM-based
      distributions such as Fedora) then in order to make the links
      through to files work correctly you may need to use repository web
      interface URLs similar to these:

      - Repository web interface tree base URL:
        `https://github.com/organisationname/%pathelement[0]%/tree/master/%pathelement[1:]%`
      - Repository web interface file base URL:
        `https://github.com/organisationname/%pathelement[0]%/blob/master/%pathelement[1:]%`

   3. Create a LayerBranch to link the Branch and Layer that you
      created in the previous steps. You don't need to enter anything
      special here.

2. Run the import script, specifying the branch and layer names and the path
   to the base of the packages (where each subdirectory contains a package,
   notably a spec file describing the package):

   ```sh
   layerindex/tools/import_otherdistro.py import-pkgspec <branchname> <layername> <pkgpath>
   ```

3. Update the comparison status of recipes based on layers in the database:

   ```sh
   layerindex/tools/update_classic_status.py -l <layername> -b <branchname>
   ```

4. Optionally enable the Update button in the UI by setting `COMPARISON_UPDATE`
   in `settings.py` to map each other distro branch to the command that should
   be run in the background when the button is pressed. For example:

   ```python
   COMPARISON_UPDATE = [
       {
           'branch_name': 'otherlinux',
           'update_command': 'layerindex/tools/import_otherdistro.py import-pkgspec otherlinux otherlinux /path/to/pkgs -u %update%; layerindex/tools/update_classic_status.py -b otherlinux -l otherlinux -u %update%',
       },
   ]
   ```

If you refresh the main page of the website, the other distro data should
now show up at the bottom of the branch drop-down menu. On a periodic
basis you can repeat steps 2 and 3 to refresh the data as changes occur on
both sides. Users with sufficient permissions can also manually update the
migration status on the other distro recipe detail pages within the website,
which is useful for example when there's an equivalent recipe in another
layer that doesn't have the same name, so the `update_classic_status.py`
script wouldn't be able to pick it up.

If you want to show links to additional upstream pages associated with
packages in the other distro, you can add "Layer recipe extra URL" entries
for each type of link you want to be shown. For example, Fedora provides
a summary page for each package - acl's one is at
https://apps.fedoraproject.org/packages/acl, so you would create a
Layer Recipe Extra URL entry with the template URL
`https://apps.fedoraproject.org/packages/%pn%` and then links would be
shown for this under the detail page for each package in the other distro.
If you have the rrs application enabled the link will also be shown in the
"Distros" section of the maintenance detail page for the covering recipe.


## Security Considerations

Some things to be aware of from a security perspective:

- By default, anyone can register themselves an account. If you wish to
  disable new user registration and manage users manually through the admin
  interface instead, then add the following line to `docker/settings.py`:

  ```python
  REGISTRATION_OPEN = False
  ```

  Then, assuming you have already run `dockersetup.py` to install the
  application, run the following command to update it:

  ```sh
  ./dockersetup.py -u
  ```

- By default, `dockersetup.py` enables connection to the web server via
  HTTPS using a self-signed certificate; connections via HTTP are
  re-directed to HTTPS. However, the self-signed certificate is only
  intended to provide a minimum level of security, but will result in
  browser warnings and is not recommended for production - instead,
  obtain and use your own certificate/key pair corresponding to the
  domain which will be used to access the application in production,
  or alternatively if the application is accessible to the internet you
  can use Let's Encrypt.

- If you provide your own certificates for HTTPS, you should probably
  also enable HSTS in your configuration. Refer to the Django Security
  guide for details on how to do that:

  https://docs.djangoproject.com/en/stable/topics/security/#ssl-https

- To reset a forgotten account password, you can either use the password
  reset function (`/accounts/password_reset/`) or alternatively from the
  backend you can run the following command:

  ```sh
  docker-compose exec layersapp /opt/layerindex/manage.py changepassword <username>
  ```

- The web-based password reset function will ask the user answers to
  security questions they selected and answered when they created the
  account. Admins can configure the selectable security questions in
  the admin interface under "Security questions"; however, be cautious
  about deleting or substantially changing a question if you already
  have user accounts that have given answers to that question, as doing
  so will invalidate the user-set answers. You can check this if you go
  to delete the security question in the admin interface - any user
  answers will show up as "Security question answers" listed to be
  deleted along with the question.

  Note: the superuser created during setup will not have answers to
  security questions set, so if you think you might need to use the
  password reset function later you will need to set these by logging
  into the application and then going to Edit Profile on the top-right
  user drop-down menu.

- Security question answers are stored using the same mechanism as
  for passwords, i.e. a secure one-way hash; thus answers cannot be
  retrieved from the database once set. Additionally, if a user wants
  to change one of their answers via the Edit Profile function, they
  will be required to re-specify all of them.

- Account lockout: this application will lock out the user in two ways:

  - By IP address (using django-axes) after too many invalid login attempts.
    (default 4, resets after an hour). The lockout can be removed
    immediately using the following command:

    ```sh
    docker-compose exec layersapp /opt/layerindex/manage.py axes_reset
    ```

    If you wish to disable this, remove or comment out "axes" in
    `INSTALLED_APPS`. For more information on configuring axes, see:

    https://django-axes.readthedocs.io/en/latest/

  - By account for too many incorrect password reset attempts. To remove
    this lockout, log into the admin interface, go to Users, click on the
    user, tick the Active checkbox and then save.

- The REST API at `/layerindex/api/` is read-only and needs no login. It
  serves the same information as the public web pages for published layers,
  including the names and email addresses of layer maintainers, and is used
  by tools such as `bitbake-layers layerindex-fetch` and Toaster.


## Backup and restore

To back up the database within the docker-based setup, you can run the
following command (no need to substitute `${MYSQL_ROOT_PASSWORD}`, it's
already present within the container environment):

```sh
docker-compose exec layersdb /bin/sh -c '/usr/bin/mariadb-dump -u root --password=${MYSQL_ROOT_PASSWORD} --max_allowed_packet=512M layersdb' | gzip > backup-`date +%Y_%m_%d_%H%M`.sql.gz
```

To restore one of these backups you would run the following command (take
care, this will overwrite the data immediately without prompting!):

```sh
zcat backupfile.sql.gz | docker-compose exec -T layersdb /bin/sh -c '/usr/bin/mariadb -u root --password=${MYSQL_ROOT_PASSWORD} layersdb'
```


## Maintenance

The code for this application is maintained by the Yocto Project.

The latest version of the code can always be found here:

https://git.yoctoproject.org/layerindex-web/

Contributions are welcome. Please send patches / pull requests to
yocto-patches@lists.yoctoproject.org with '[layerindex-web]' in the
subject.


## License

This application is based upon the Django project template, whose files
are covered by the BSD license and are copyright (c) Django Software
Foundation and individual contributors.

Bundled Bootstrap (including Glyphicons) is redistributed under
the MIT license.

Bundled jQuery is redistributed under the MIT license.

Bundled Chart.js is redistributed under the MIT license.

Bundled TableSorter is redistributed under the MIT license.

Bundled and modified django-registration-templates is redistributed
under the MIT license.

All other content is copyright (C) 2013-2019 Intel Corporation and
licensed under the MIT license (unless otherwise noted) - see
[COPYING.MIT](COPYING.MIT) for details.
