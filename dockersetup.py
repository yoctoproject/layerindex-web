#!/usr/bin/env python3

# Layer index Docker setup script
#
# Copyright (C) 2018 Intel Corporation
# Author: Amber Elliot <amber.n.elliot@intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

# This script will make a cluster of 5 containers:
#
#  - layersapp: the application
#  - layersdb: the database
#  - layersweb: NGINX web server (as a proxy and for serving static content)
#  - layerscelery: Celery (for running background jobs)
#  - layersrabbit: RabbitMQ (required by Celery)
#
# It will build and run these containers and set up the database.

import sys
import os
import argparse
import re
import subprocess
import time
import random
import shutil
import tempfile

def get_args():
    parser = argparse.ArgumentParser(description='Script sets up the Layer Index tool with Docker Containers.')

    parser.add_argument('-o', '--hostname', type=str, help='Hostname of your machine. Defaults to localhost if not set.', required=False, default = "localhost")
    parser.add_argument('-p', '--http-proxy', type=str, help='http proxy in the format http://<myproxy:port>', required=False)
    parser.add_argument('-s', '--https-proxy', type=str, help='https proxy in the format http://<myproxy:port>', required=False)
    parser.add_argument('-d', '--databasefile', type=str, help='Location of your database file to import. Must be a .sql file.', required=False)
    parser.add_argument('-m', '--portmapping', type=str, help='Port mapping in the format HOST:CONTAINER. Default is %(default)s', required=False, default='8080:80,8081:443')
    parser.add_argument('--no-https', action="store_true", default=False, help='Disable HTTPS (HTTP only) for web server')
    parser.add_argument('--cert', type=str, help='Existing SSL certificate to use for HTTPS web serving', required=False)
    parser.add_argument('--cert-key', type=str, help='Existing SSL certificate key to use for HTTPS web serving', required=False)
    parser.add_argument('--letsencrypt', action="store_true", default=False, help='Use Let\'s Encrypt for HTTPS')

    args = parser.parse_args()

    port = proxymod = ""
    try:
        if args.http_proxy:
            split = args.http_proxy.split(":")
            port = split[2]
            proxymod = split[1].replace("/", "")
    except IndexError:
        raise argparse.ArgumentTypeError("http_proxy must be in format http://<myproxy:port>")

    for entry in args.portmapping.split(','):
        if len(entry.split(":")) != 2:
            raise argparse.ArgumentTypeError("Port mapping must in the format HOST:CONTAINER. Ex: 8080:80. Multiple mappings should be separated by commas.")

    if args.no_https:
        if args.cert or args.cert_key or args.letsencrypt:
            raise argparse.ArgumentTypeError("--no-https and --cert/--cert-key/--letsencrypt options are mutually exclusive")
    if args.letsencrypt:
        if args.cert or args.cert_key:
            raise argparse.ArgumentTypeError("--letsencrypt and --cert/--cert-key options are mutually exclusive")
    if args.cert and not os.path.exists(args.cert):
        raise argparse.ArgumentTypeError("Specified certificate file %s does not exist" % args.cert)
    if args.cert_key and not os.path.exists(args.cert_key):
        raise argparse.ArgumentTypeError("Specified certificate key file %s does not exist" % args.cert_key)
    if args.cert_key and not args.cert:
        raise argparse.ArgumentTypeError("Certificate key file specified but not certificate")
    cert_key = args.cert_key
    if args.cert and not cert_key:
        cert_key = os.path.splitext(args.cert)[0] + '.key'
        if not os.path.exists(cert_key):
            raise argparse.ArgumentTypeError("Could not find certificate key, please use --cert-key to specify it")

    return args.hostname, args.http_proxy, args.https_proxy, args.databasefile, port, proxymod, args.portmapping, args.no_https, args.cert, cert_key, args.letsencrypt

# Edit http_proxy and https_proxy in Dockerfile
def edit_dockerfile(http_proxy, https_proxy):
    filedata= readfile("Dockerfile")
    newlines = []
    lines = filedata.splitlines()
    for line in lines:
        if "ENV http_proxy" in line and http_proxy:
            newlines.append("ENV http_proxy " + http_proxy + "\n")
        elif "ENV https_proxy" in line and https_proxy:
            newlines.append("ENV https_proxy " + https_proxy + "\n")
        else:
            newlines.append(line + "\n")

    writefile("Dockerfile", ''.join(newlines))


# If using a proxy, add proxy values to git-proxy and uncomment proxy script in .gitconfig
def edit_gitproxy(proxymod, port):
    filedata= readfile("docker/git-proxy")
    newlines = []
    lines = filedata.splitlines()
    for line in lines:
        if "PROXY=" in line:
            newlines.append("PROXY=" + proxymod + "\n")
        elif "PORT=" in line:
            newlines.append("PORT=" + port + "\n")
        else:
            newlines.append(line + "\n")
    writefile("docker/git-proxy", ''.join(newlines))
    filedata = readfile("docker/.gitconfig")
    newdata = filedata.replace("#gitproxy", "gitproxy")
    writefile("docker/.gitconfig", newdata)

def yaml_uncomment(line):
    out = ''
    for i, ch in enumerate(line):
        if ch == ' ':
            out += ch
        elif ch != '#':
            out += line[i:]
            break
    return out

def yaml_comment(line):
    out = ''
    commented = False
    for i, ch in enumerate(line):
        if ch == '#':
            commented = True
            out += line[i:]
            break
        elif ch != ' ':
            if not commented:
                out += '#'
            out += line[i:]
            break
        else:
            out += ch
    return out


# Add hostname, secret key, db info, and email host in docker-compose.yml
def edit_dockercompose(hostname, dbpassword, secretkey, rmqpassword, portmapping, letsencrypt):
    filedata= readfile("docker-compose.yml")
    in_layersweb = False
    in_layersweb_ports = False
    in_layersweb_ports_format = None
    in_layerscertbot_format = None
    newlines = []
    lines = filedata.splitlines()
    for line in lines:
        if in_layersweb_ports:
            format = line[0:line.find("-")].replace("#", "")
            if in_layersweb_ports_format:
                if format != in_layersweb_ports_format:
                    in_layersweb_ports = False
                    in_layersweb = False
                else:
                    continue
            else:
                in_layersweb_ports_format = format
                for portmap in portmapping.split(','):
                    newlines.append(format + '- "' + portmap + '"' + "\n")
                continue
        if in_layerscertbot_format:
            ucline = yaml_uncomment(line)
            format = re.match(r'^( *)', ucline).group(0)
            if len(format) <= len(in_layerscertbot_format):
                in_layerscertbot_format = False
            elif letsencrypt:
                newlines.append(ucline + '\n')
                continue
            else:
                newlines.append(yaml_comment(line) + '\n')
                continue
        if "layerscertbot:" in line:
            ucline = yaml_uncomment(line)
            in_layerscertbot_format = re.match(r'^( *)', ucline).group(0)
            if letsencrypt:
                newlines.append(ucline + '\n')
            else:
                newlines.append(yaml_comment(line) + '\n')
        elif "layersweb:" in line:
            in_layersweb = True
            newlines.append(line + "\n")
        elif "hostname:" in line:
            format = line[0:line.find("hostname")].replace("#", "")
            newlines.append(format +"hostname: " + hostname + "\n")
        elif '- "SECRET_KEY' in line:
            format = line[0:line.find('- "SECRET_KEY')].replace("#", "")
            newlines.append(format + '- "SECRET_KEY=' + secretkey + '"\n')
        elif '- "DATABASE_PASSWORD' in line:
            format = line[0:line.find('- "DATABASE_PASSWORD')].replace("#", "")
            newlines.append(format + '- "DATABASE_PASSWORD=' + dbpassword + '"\n')
        elif '- "MYSQL_ROOT_PASSWORD' in line:
            format = line[0:line.find('- "MYSQL_ROOT_PASSWORD')].replace("#", "")
            newlines.append(format + '- "MYSQL_ROOT_PASSWORD=' + dbpassword + '"\n')
        elif '- "RABBITMQ_DEFAULT_USER' in line:
            format = line[0:line.find('- "RABBITMQ_DEFAULT_USER')].replace("#", "")
            newlines.append(format + '- "RABBITMQ_DEFAULT_USER=layermq"\n')
        elif '- "RABBITMQ_DEFAULT_PASS' in line:
            format = line[0:line.find('- "RABBITMQ_DEFAULT_PASS')].replace("#", "")
            newlines.append(format + '- "RABBITMQ_DEFAULT_PASS=' + rmqpassword + '"\n')
        elif "ports:" in line:
            if in_layersweb:
                in_layersweb_ports = True
            newlines.append(line + "\n")
        elif letsencrypt and "./docker/certs:/" in line:
            newlines.append(line.split(':')[0] + ':/etc/letsencrypt\n')
        else:
            newlines.append(line + "\n")
    writefile("docker-compose.yml", ''.join(newlines))


def edit_nginx_ssl_conf(hostname, https_port, certdir, certfile, keyfile):
    filedata = readfile('docker/nginx-ssl.conf')
    newlines = []
    lines = filedata.splitlines()
    for line in lines:
        if 'ssl_certificate ' in line:
            format = line[0:line.find('ssl_certificate')]
            newlines.append(format + 'ssl_certificate ' + os.path.join(certdir, certfile) + ';\n')
        elif 'ssl_certificate_key ' in line:
            format = line[0:line.find('ssl_certificate_key')]
            newlines.append(format + 'ssl_certificate_key ' + os.path.join(certdir, keyfile) + ';\n')
            # Add a line for the dhparam file
            newlines.append(format + 'ssl_dhparam ' + os.path.join(certdir, 'dhparam.pem') + ';\n')
        elif 'https://layers.openembedded.org' in line:
            line = line.replace('https://layers.openembedded.org', 'https://%s:%s' % (hostname, https_port))
            newlines.append(line + "\n")
        elif 'http://layers.openembedded.org' in line:
            line = line.replace('http://layers.openembedded.org', 'http://%s:%s' % (hostname, http_port))
            newlines.append(line + "\n")
        else:
            line = line.replace('layers.openembedded.org', hostname)
            newlines.append(line + "\n")

    # Write to a different file so we can still replace the hostname next time
    writefile("docker/nginx-ssl-edited.conf", ''.join(newlines))


def edit_dockerfile_web(hostname, no_https):
    filedata = readfile('Dockerfile.web')
    newlines = []
    lines = filedata.splitlines()
    for line in lines:
        if line.startswith('COPY ') and line.endswith('/etc/nginx/nginx.conf'):
            if no_https:
                srcfile = 'docker/nginx.conf'
            else:
                srcfile = 'docker/nginx-ssl-edited.conf'
            line = 'COPY %s /etc/nginx/nginx.conf' % srcfile
        newlines.append(line + "\n")
    writefile("Dockerfile.web", ''.join(newlines))


def generatepasswords(passwordlength):
    return ''.join([random.SystemRandom().choice('abcdefghijklmnopqrstuvwxyz0123456789!@#%^&*-_=+') for i in range(passwordlength)])

def readfile(filename):
    f = open(filename,'r')
    filedata = f.read()
    f.close()
    return filedata

def writefile(filename, data):
    f = open(filename,'w')
    f.write(data)
    f.close()


# Generate secret key and database password
secretkey = generatepasswords(50)
dbpassword = generatepasswords(10)
rmqpassword = generatepasswords(10)

## Get user arguments and modify config files
hostname, http_proxy, https_proxy, dbfile, port, proxymod, portmapping, no_https, cert, cert_key, letsencrypt = get_args()

https_port = None
http_port = None
for portmap in portmapping.split(','):
    outport, inport = portmap.split(':', 1)
    if inport == '443':
        https_port = outport
    elif inport == '80':
        http_port = outport
if (not https_port) and (not no_https):
    print("No HTTPS port mapping (to port 443 inside the container) was specified and --no-https was not specified")
    sys.exit(1)
if not http_port:
    print("Port mapping must include a mapping to port 80 inside the container")
    sys.exit(1)

print("""
OE Layer Index Docker setup script
----------------------------------

This script will set up a cluster of Docker containers needed to run the
OpenEmbedded layer index application.

Configuration is controlled by command-line arguments. If you need to check
which options you need to specify, press Ctrl+C now and then run the script
again with the --help argument.

Note that this script does have interactive prompts, so be prepared to
provide information as needed.
""")
try:
    input('Press Enter to begin setup (or Ctrl+C to exit)...')
except KeyboardInterrupt:
    print('')
    sys.exit(2)

if http_proxy:
    edit_gitproxy(proxymod, port)
if http_proxy or https_proxy:
    edit_dockerfile(http_proxy, https_proxy)

edit_dockercompose(hostname, dbpassword, secretkey, rmqpassword, portmapping, letsencrypt)

edit_dockerfile_web(hostname, no_https)

emailaddr = None
if not no_https:
    local_cert_dir = os.path.abspath('docker/certs')
    container_cert_dir = '/opt/cert'
    if letsencrypt:
        # Get email address
        emailaddr = input('Enter your email address (for letsencrypt): ')

        # Create dummy cert
        container_cert_dir = '/etc/letsencrypt'
        letsencrypt_cert_subdir = 'live/' + hostname
        local_letsencrypt_cert_dir = os.path.join(local_cert_dir, letsencrypt_cert_subdir)
        if not os.path.isdir(local_letsencrypt_cert_dir):
            os.makedirs(local_letsencrypt_cert_dir)
        keyfile = os.path.join(letsencrypt_cert_subdir, 'privkey.pem')
        certfile = os.path.join(letsencrypt_cert_subdir, 'fullchain.pem')
        return_code = subprocess.call("openssl req -x509 -nodes -newkey rsa:1024 -days 1 -keyout %s -out %s -subj '/CN=localhost'" % (os.path.join(local_cert_dir, keyfile), os.path.join(local_cert_dir, certfile)), shell=True)
        if return_code != 0:
            print("Dummy certificate generation failed")
            sys.exit(1)
    elif cert:
        if os.path.abspath(os.path.dirname(cert)) != local_cert_dir:
            shutil.copy(cert, local_cert_dir)
        certfile = os.path.basename(cert)
        if os.path.abspath(os.path.dirname(cert_key)) != local_cert_dir:
            shutil.copy(cert_key, local_cert_dir)
        keyfile = os.path.basename(cert_key)
    else:
        print('')
        print('Generating self-signed SSL certificate. Please specify your hostname (%s) when prompted for the Common Name.' % hostname)
        certfile = 'setup-selfsigned.crt'
        keyfile = 'setup-selfsigned.key'
        return_code = subprocess.call('openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout %s -out %s' % (os.path.join(local_cert_dir, keyfile), os.path.join(local_cert_dir, certfile)), shell=True)
        if return_code != 0:
            print("Self-signed certificate generation failed")
            sys.exit(1)
    return_code = subprocess.call('openssl dhparam -out %s 2048' % os.path.join(local_cert_dir, 'dhparam.pem'), shell=True)
    if return_code != 0:
        print("DH group generation failed")
        sys.exit(1)

    edit_nginx_ssl_conf(hostname, https_port, container_cert_dir, certfile, keyfile)

    if letsencrypt:
        return_code = subprocess.call("docker-compose up -d --build layersweb", shell=True)
        if return_code != 0:
            print("docker-compose up layersweb failed")
            sys.exit(1)
        tempdir = tempfile.mkdtemp()
        try:
            # Wait for web server to start
            while True:
                time.sleep(2)
                return_code = subprocess.call("wget -q --no-check-certificate http://%s:%s/" % (hostname, http_port), shell=True, cwd=tempdir)
                if return_code == 0 or return_code > 4:
                    break
                else:
                    print("Web server may not be ready; will try again.")

            # Delete temp cert now that the server is up
            shutil.rmtree(os.path.join(local_cert_dir, 'live'))

            # Create a test file and fetch it to ensure web server is working (for http)
            return_code = subprocess.call("docker-compose exec layersweb /bin/sh -c 'mkdir -p /var/www/certbot/.well-known/acme-challenge/ ; echo something > /var/www/certbot/.well-known/acme-challenge/test.txt'", shell=True)
            if return_code != 0:
                print("Creating test file failed")
                sys.exit(1)
            return_code = subprocess.call("wget -nv http://%s:%s/.well-known/acme-challenge/test.txt" % (hostname, http_port), shell=True, cwd=tempdir)
            if return_code != 0:
                print("Reading test file from web server failed")
                sys.exit(1)
            return_code = subprocess.call("docker-compose exec layersweb /bin/sh -c 'rm -rf /var/www/certbot/.well-known'", shell=True)
            if return_code != 0:
                print("Removing test file failed")
                sys.exit(1)
        finally:
            shutil.rmtree(tempdir)

        # Now run certbot to register SSL certificate
        staging_arg = '--staging'
        if emailaddr:
            email_arg = '--email %s' % emailaddr
        else:
            email_arg = '--register-unsafely-without-email'
        return_code = subprocess.call('docker-compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    %s \
    %s \
    -d %s \
    --rsa-key-size 4096 \
    --agree-tos \
    --force-renewal" layerscertbot' % (staging_arg, email_arg, hostname), shell=True)
        if return_code != 0:
            print("Running certbot failed")
            sys.exit(1)

        # Stop web server (so it can effectively be restarted with the new certificate)
        return_code = subprocess.call("docker-compose stop layersweb", shell=True)
        if return_code != 0:
            print("docker-compose stop failed")
            sys.exit(1)


## Start up containers
return_code = subprocess.call("docker-compose up -d", shell=True)
if return_code != 0:
    print("docker-compose up failed")
    sys.exit(1)

# Apply any pending layerindex migrations / initialize the database. Database might not be ready yet; have to wait then poll.
time.sleep(8)
while True:
    time.sleep(2)
    return_code = subprocess.call("docker-compose run --rm layersapp /opt/migrate.sh", shell=True)
    if return_code == 0:
        break
    else:
        print("Database server may not be ready; will try again.")

# Import the user's supplied data
if dbfile:
    return_code = subprocess.call("docker exec -i layersdb mysql -uroot -p" + dbpassword + " layersdb " + " < " + dbfile, shell=True)
    if return_code != 0:
        print("Database import failed")
        sys.exit(1)

## For a fresh database, create an admin account
print("Creating database superuser. Input user name, email, and password when prompted.")
return_code = subprocess.call("docker-compose run --rm layersapp /opt/layerindex/manage.py createsuperuser", shell=True)
if return_code != 0:
    print("Creating superuser failed")
    sys.exit(1)

## Set the volume permissions using debian:stretch since we recently fetched it
return_code = subprocess.call("docker run --rm -v layerindexweb_layersmeta:/opt/workdir debian:stretch chown 500 /opt/workdir && \
         docker run --rm -v layerindexweb_layersstatic:/usr/share/nginx/html debian:stretch chown 500 /usr/share/nginx/html", shell=True)
if return_code != 0:
    print("Setting volume permissions failed")
    sys.exit(1)

## Generate static assets. Run this command again to regenerate at any time (when static assets in the code are updated)
return_code = subprocess.call("docker-compose run --rm -e STATIC_ROOT=/usr/share/nginx/html -v layerindexweb_layersstatic:/usr/share/nginx/html layersapp /opt/layerindex/manage.py collectstatic --noinput", shell = True)
if return_code != 0:
    print("Collecting static files failed")
    sys.exit(1)

print("")
if https_port and not no_https:
    protocol = 'https'
    port = https_port
else:
    protocol = 'http'
    port = http_port
print("The application should now be accessible at %s://%s:%s" % (protocol, hostname, port))
