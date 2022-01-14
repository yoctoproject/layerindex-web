#!/usr/bin/env python3

# Layer index Docker setup script
#
# Copyright (C) 2018 Intel Corporation
# Author: Amber Elliot <amber.n.elliot@intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details
#
# SPDX-License-Identifier: MIT

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

min_version = (3, 4, 3)
if sys.version_info < min_version:
    sys.stderr.write('Sorry, python version %d.%d.%d or later is required\n' % min_version)
    sys.exit(1)

import os
import argparse
import re
import subprocess
import time
import random
import shutil
import tempfile
from shlex import quote

def get_args():
    parser = argparse.ArgumentParser(description='Script sets up the Layer Index tool with Docker Containers.')

    default_http_proxy = os.environ.get('http_proxy', os.environ.get('HTTP_PROXY', ''))
    default_https_proxy = os.environ.get('https_proxy', os.environ.get('HTTPS_PROXY', ''))
    default_socks_proxy = os.environ.get('socks_proxy', os.environ.get('SOCKS_PROXY', os.environ.get('all_proxy', os.environ.get('ALL_PROXY', ''))))
    default_no_proxy = os.environ.get('no_proxy', os.environ.get('NO_PROXY', ''))

    parser.add_argument('-u', '--update', action="store_true", default=False, help='Update existing installation instead of installing')
    parser.add_argument('-r', '--reinstall', action="store_true", default=False, help='Reinstall over existing installation (wipes database!)')
    parser.add_argument('--uninstall', action="store_true", default=False, help='Uninstall (wipes database!)')
    parser.add_argument('-o', '--hostname', type=str, help='Hostname of your machine. Defaults to localhost if not set.', required=False, default = "localhost")
    parser.add_argument('-p', '--http-proxy', type=str, help='http proxy in the format http://<myproxy:port>', default=default_http_proxy, required=False)
    parser.add_argument('-s', '--https-proxy', type=str, help='https proxy in the format http://<myproxy:port>', default=default_https_proxy, required=False)
    parser.add_argument('-S', '--socks-proxy', type=str, help='socks proxy in the format socks://myproxy:port>', default=default_socks_proxy, required=False)
    parser.add_argument('-N', '--no-proxy', type=str, help='Comma-separated list of hosts that should not be connected to via the proxy', default=default_no_proxy, required=False)
    parser.add_argument('-d', '--databasefile', type=str, help='Location of your database file to import. Must be a .sql or .sql.gz file.', required=False)
    parser.add_argument('-e', '--email-host', type=str, help='Email host for sending messages (optionally with :port if not 25)', required=False)
    parser.add_argument('--email-user', type=str, help='User name to use when connecting to email host', required=False)
    parser.add_argument('--email-password', type=str, help='Password to use when connecting to email host', required=False)
    parser.add_argument('--email-ssl', action="store_true", default=False, help='Use SSL when connecting to email host')
    parser.add_argument('--email-tls', action="store_true", default=False, help='Use TLS when connecting to email host')
    parser.add_argument('-m', '--portmapping', type=str, help='Port mapping in the format HOST:CONTAINER. Default is %(default)s', required=False, default='8080:80,8081:443')
    parser.add_argument('--project-name', type=str, help='docker-compose project name to use')
    parser.add_argument('--no-https', action="store_true", default=False, help='Disable HTTPS (HTTP only) for web server')
    parser.add_argument('--cert', type=str, help='Existing SSL certificate to use for HTTPS web serving', required=False)
    parser.add_argument('--cert-key', type=str, help='Existing SSL certificate key to use for HTTPS web serving', required=False)
    parser.add_argument('--letsencrypt', action="store_true", default=False, help='Use Let\'s Encrypt for HTTPS')
    parser.add_argument('--no-migrate', action="store_true", default=False, help='Skip running database migrations')
    parser.add_argument('--no-admin-user', action="store_true", default=False, help='Skip adding admin user')
    parser.add_argument('--no-connectivity', action="store_true", default=False, help='Skip checking external network connectivity')

    args = parser.parse_args()

    if args.update:
        if args.http_proxy != default_http_proxy or args.https_proxy != default_https_proxy or args.no_proxy != default_no_proxy or args.databasefile or args.no_https or args.cert or args.cert_key or args.letsencrypt:
            raise argparse.ArgumentTypeError("The -u/--update option will not update configuration or database content, and thus none of the other configuration options can be used in conjunction with it")
        if args.reinstall:
            raise argparse.ArgumentTypeError("The -u/--update and -r/--reinstall options are mutually exclusive")

    socks_proxy_port = socks_proxy_host = ""
    try:
        if args.socks_proxy:
            split = args.socks_proxy.split(":")
            socks_proxy_port = split[2]
            socks_proxy_host = split[1].replace("/", "")
        elif args.http_proxy:
            # Guess that this will work
            split = args.http_proxy.split(":")
            socks_proxy_port = '1080'
            socks_proxy_host = split[1].replace("/", "")
    except IndexError:
        raise argparse.ArgumentTypeError("socks_proxy must be in format socks://<myproxy:port>")

    if args.http_proxy and not args.https_proxy:
        args.https_proxy = args.http_proxy
    elif args.https_proxy and not args.http_proxy:
        args.http_proxy = args.https_proxy

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
    if args.cert and not args.cert_key:
        args.cert_key = os.path.splitext(args.cert)[0] + '.key'
        if not os.path.exists(args.cert_key):
            raise argparse.ArgumentTypeError("Could not find certificate key, please use --cert-key to specify it")

    email_host = None
    email_port = None
    if args.email_host:
        email_host_split = args.email_host.split(':')
        email_host = email_host_split[0]
        if len(email_host_split) > 1:
            email_port = email_host_split[1]

    if args.email_ssl and args.email_tls:
        raise argparse.ArgumentTypeError("--email-ssl and --email-tls options are mutually exclusive")
    if (args.email_ssl or args.email_tls or args.email_user or args.email_password) and not email_host:
        raise argparse.ArgumentTypeError("If any of the email host options are specified then you must also specify an email host with -e/--email-host")

    return args, socks_proxy_port, socks_proxy_host, email_host, email_port

# Edit http_proxy and https_proxy in Dockerfile
def edit_dockerfile(http_proxy, https_proxy, no_proxy):
    filedata= readfile("Dockerfile")
    newlines = []
    lines = filedata.splitlines()
    for line in lines:
        if "ENV http_proxy" in line:
            if http_proxy:
                newlines.append("ENV http_proxy " + http_proxy + "\n")
            else:
                newlines.append('#' + line.lstrip('#') + '\n')
        elif "ENV https_proxy" in line:
            if https_proxy:
                newlines.append("ENV https_proxy " + https_proxy + "\n")
            else:
                newlines.append('#' + line.lstrip('#') + '\n')
        elif "ENV no_proxy" in line:
            if no_proxy:
                newlines.append("ENV no_proxy " + no_proxy + "\n")
            else:
                newlines.append('#' + line.lstrip('#') + '\n')
        else:
            newlines.append(line + "\n")

    writefile("Dockerfile", ''.join(newlines))


def convert_no_proxy(no_proxy):
    '''
    Convert no_proxy to something that will work in a shell case
    statement (for the git proxy script)
    '''
    no_proxy_sh = []
    for item in no_proxy.split(','):
        ip_res = re.match('^([0-9]+).([0-9]+).([0-9]+).([0-9]+)/([0-9]+)$', item)
        if ip_res:
            mask = int(ip_res.groups()[4])
            if mask == 8:
                no_proxy_sh.append('%s.*' % ip_res.groups()[0])
            elif mask == 16:
                no_proxy_sh.append('%s.%s.*' % ip_res.groups()[:2])
            elif mask == 24:
                no_proxy_sh.append('%s.%s.%s.*' % ip_res.groups()[:3])
            elif mask == 32:
                no_proxy_sh.append('%s.%s.%s.%s' % ip_res.groups()[:4])
            # If it's not one of these, we can't support it - just skip it
        else:
            if item.startswith('.'):
                no_proxy_sh.append('*' + item)
            else:
                no_proxy_sh.append(item)
    return '|'.join(no_proxy_sh)


# If using a proxy, add proxy values to git-proxy and uncomment proxy script in .gitconfig
def edit_gitproxy(socks_proxy_host, socks_proxy_port, no_proxy):
    no_proxy_sh = convert_no_proxy(no_proxy)

    filedata = readfile("docker/git-proxy")
    newlines = []
    lines = filedata.splitlines()
    eatnextline = False
    for line in lines:
        if eatnextline:
            eatnextline = False
            continue
        if line.startswith('PROXY='):
            newlines.append('PROXY=' + socks_proxy_host + '\n')
        elif line.startswith('PORT='):
            newlines.append('PORT=' + socks_proxy_port + '\n')
        elif '## NO_PROXY' in line:
            newlines.append(line + '\n')
            newlines.append('    %s)\n' % no_proxy_sh)
            eatnextline = True
        else:
            newlines.append(line + "\n")
    writefile("docker/git-proxy", ''.join(newlines))

    filedata = readfile("docker/.gitconfig")
    newlines = []
    for line in filedata.splitlines():
        if 'gitproxy' in line:
            if socks_proxy_host:
                newlines.append(yaml_uncomment(line) + "\n")
            else:
                newlines.append(yaml_comment(line) + "\n")
        else:
            newlines.append(line + "\n")
    writefile("docker/.gitconfig", ''.join(newlines))

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
def edit_dockercompose(hostname, dbpassword, dbapassword, secretkey, rmqpassword, portmapping, letsencrypt, email_host, email_port, email_user, email_password, email_ssl, email_tls):

    def adjust_cert_mount_line(ln):
        linesplit = ln.split(':')
        if letsencrypt:
            linesplit[1] = '/etc/letsencrypt'
        else:
            linesplit[1] = '/opt/cert'
        # This allows us to handle if there is a ":ro" or similar on the end
        return ':'.join(linesplit)

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
                if "./docker/certs:/" in ucline:
                    ucline = adjust_cert_mount_line(ucline)
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
        elif '- "DATABASE_USER' in line:
            format = line[0:line.find('- "DATABASE_USER')].replace("#", "")
            newlines.append(format + '- "DATABASE_USER=layers"\n')
        elif '- "DATABASE_PASSWORD' in line:
            format = line[0:line.find('- "DATABASE_PASSWORD')].replace("#", "")
            newlines.append(format + '- "DATABASE_PASSWORD=' + dbpassword + '"\n')
        elif '- "MYSQL_ROOT_PASSWORD' in line:
            format = line[0:line.find('- "MYSQL_ROOT_PASSWORD')].replace("#", "")
            newlines.append(format + '- "MYSQL_ROOT_PASSWORD=' + dbapassword + '"\n')
        elif '- "RABBITMQ_DEFAULT_USER' in line:
            format = line[0:line.find('- "RABBITMQ_DEFAULT_USER')].replace("#", "")
            newlines.append(format + '- "RABBITMQ_DEFAULT_USER=layermq"\n')
        elif '- "RABBITMQ_DEFAULT_PASS' in line:
            format = line[0:line.find('- "RABBITMQ_DEFAULT_PASS')].replace("#", "")
            newlines.append(format + '- "RABBITMQ_DEFAULT_PASS=' + rmqpassword + '"\n')
        elif '- "EMAIL_HOST' in line:
            format = line[0:line.find('- "EMAIL_HOST')].replace("#", "")
            if email_host:
                newlines.append(format + '- "EMAIL_HOST=' + email_host + '"\n')
            else:
                newlines.append(format + '#- "EMAIL_HOST=<set this here>"\n')
        elif '- "EMAIL_PORT' in line:
            format = line[0:line.find('- "EMAIL_PORT')].replace("#", "")
            if email_port:
                newlines.append(format + '- "EMAIL_PORT=' + email_port + '"\n')
            else:
                newlines.append(format + '#- "EMAIL_PORT=<set this here if not the default>"\n')
        elif '- "EMAIL_USER' in line:
            format = line[0:line.find('- "EMAIL_USER')].replace("#", "")
            if email_user:
                newlines.append(format + '- "EMAIL_USER=' + email_user + '"\n')
            else:
                newlines.append(format + '#- "EMAIL_USER=<set this here if needed>"\n')
        elif '- "EMAIL_PASSWORD' in line:
            format = line[0:line.find('- "EMAIL_PASSWORD')].replace("#", "")
            if email_password:
                newlines.append(format + '- "EMAIL_PASSWORD=' + email_password + '"\n')
            else:
                newlines.append(format + '#- "EMAIL_PASSWORD=<set this here if needed>"\n')
        elif '- "EMAIL_USE_SSL' in line:
            format = line[0:line.find('- "EMAIL_USE_SSL')].replace("#", "")
            if email_ssl:
                newlines.append(format + '- "EMAIL_USE_SSL=' + str(email_ssl) + '"\n')
            else:
                newlines.append(format + '#- "EMAIL_USE_SSL=<set this here if needed>"\n')
        elif '- "EMAIL_USE_TLS' in line:
            format = line[0:line.find('- "EMAIL_USE_TLS')].replace("#", "")
            if email_tls:
                newlines.append(format + '- "EMAIL_USE_TLS=' + str(email_tls) + '"\n')
            else:
                newlines.append(format + '#- "EMAIL_USE_TLS=<set this here if needed>"\n')
        elif "ports:" in line:
            if in_layersweb:
                in_layersweb_ports = True
            newlines.append(line + "\n")
        elif "./docker/certs:/" in line:
            newlines.append(adjust_cert_mount_line(line) + '\n')
        else:
            newlines.append(line + "\n")
    writefile("docker-compose.yml", ''.join(newlines))


def read_nginx_ssl_conf(certdir):
    hostname = None
    https_port = None
    certdir = None
    certfile = None
    keyfile = None
    with open('docker/nginx-ssl-edited.conf', 'r') as f:
        for line in f:
            if 'ssl_certificate ' in line:
                certdir, certfile = os.path.split(line.split('ssl_certificate', 1)[1].strip().rstrip(';'))
            elif 'ssl_certificate_key ' in line:
                keyfile = os.path.basename(line.split('ssl_certificate_key', 1)[1].strip().rstrip(';'))
            elif 'server_name ' in line:
                sname = line.split('server_name', 1)[1].strip().rstrip(';')
                if sname != '_':
                    hostname = sname
            elif 'return 301 https://' in line:
                res = re.search(':([0-9]+)', line)
                if res:
                    https_port = res.groups()[0]
    ret = (hostname, https_port, certdir, certfile, keyfile)
    if None in ret:
        sys.stderr.write('Failed to read SSL configuration from nginx-ssl-edited.conf')
        sys.exit(1)
    return ret

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
        else:
            line = line.replace('layers.openembedded.org', hostname)
            newlines.append(line + "\n")

    # Write to a different file so we can still replace the hostname next time
    writefile("docker/nginx-ssl-edited.conf", ''.join(newlines))


def edit_settings_py(emailaddr):
    filedata = readfile('docker/settings.py')
    newlines = []
    lines = filedata.splitlines()
    in_admins = False
    for line in lines:
        if in_admins:
            if line.strip() == ')':
                in_admins = False
            continue
        elif line.lstrip().startswith('ADMINS = ('):
            if line.count('(') > line.count(')'):
                in_admins = True
            newlines.append("ADMINS = (\n")
            if emailaddr:
                newlines.append("  ('Admin', '%s'),\n" % emailaddr)
            newlines.append(")\n")
            continue
        newlines.append(line + "\n")
    writefile("docker/settings.py", ''.join(newlines))


def read_dockerfile_web():
    no_https = True
    with open('Dockerfile.web', 'r') as f:
        for line in f:
            if line.startswith('COPY ') and line.rstrip().endswith('/etc/nginx/nginx.conf'):
                if 'nginx-ssl' in line:
                    no_https = False
                break
    return no_https


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


def setup_https(hostname, http_port, https_port, letsencrypt, cert, cert_key, emailaddr):
    local_cert_dir = os.path.abspath('docker/certs')
    container_cert_dir = '/opt/cert'
    if letsencrypt:
        # Create dummy cert
        container_cert_dir = '/etc/letsencrypt'
        letsencrypt_cert_subdir = 'live/' + hostname
        local_letsencrypt_cert_dir = os.path.join(local_cert_dir, letsencrypt_cert_subdir)
        if not os.path.isdir(local_letsencrypt_cert_dir):
            os.makedirs(local_letsencrypt_cert_dir)
        keyfile = os.path.join(letsencrypt_cert_subdir, 'privkey.pem')
        certfile = os.path.join(letsencrypt_cert_subdir, 'fullchain.pem')
        return_code = subprocess.call(['openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048', '-days', '1', '-keyout', os.path.join(local_cert_dir, keyfile), '-out', os.path.join(local_cert_dir, certfile), '-subj', '/CN=localhost'], shell=False)
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
        return_code = subprocess.call(['openssl', 'req', '-x509', '-nodes', '-days', '365', '-newkey', 'rsa:2048', '-keyout', os.path.join(local_cert_dir, keyfile), '-out', os.path.join(local_cert_dir, certfile)], shell=False)
        if return_code != 0:
            print("Self-signed certificate generation failed")
            sys.exit(1)
    return_code = subprocess.call(['openssl', 'dhparam', '-out', os.path.join(local_cert_dir, 'dhparam.pem'), '2048'], shell=False)
    if return_code != 0:
        print("DH group generation failed")
        sys.exit(1)

    edit_nginx_ssl_conf(hostname, https_port, container_cert_dir, certfile, keyfile)

    if letsencrypt:
        return_code = subprocess.call(['docker-compose', 'up', '-d', '--build', 'layersweb'], shell=False)
        if return_code != 0:
            print("docker-compose up layersweb failed")
            sys.exit(1)
        tempdir = tempfile.mkdtemp()
        try:
            # Wait for web server to start
            while True:
                time.sleep(2)
                return_code = subprocess.call(['wget', '-q', '--no-check-certificate', "http://{}:{}/".format(hostname, http_port)], shell=False, cwd=tempdir)
                if return_code == 0 or return_code > 4:
                    break
                else:
                    print("Web server may not be ready; will try again.")

            # Delete temp cert now that the server is up
            shutil.rmtree(os.path.join(local_cert_dir, 'live'))

            # Create a test file and fetch it to ensure web server is working (for http)
            return_code = subprocess.call("docker-compose exec -T layersweb /bin/sh -c 'mkdir -p /var/www/certbot/.well-known/acme-challenge/ ; echo something > /var/www/certbot/.well-known/acme-challenge/test.txt'", shell=True)
            if return_code != 0:
                print("Creating test file failed")
                sys.exit(1)
            return_code = subprocess.call(['wget', '-nv', "http://{}:{}/.well-known/acme-challenge/test.txt".format(hostname, http_port)], shell=False, cwd=tempdir)
            if return_code != 0:
                print("Reading test file from web server failed")
                sys.exit(1)
            return_code = subprocess.call(['docker-compose', 'exec', '-T', 'layersweb', '/bin/sh', '-c', 'rm -rf /var/www/certbot/.well-known'], shell=False)
            if return_code != 0:
                print("Removing test file failed")
                sys.exit(1)
        finally:
            shutil.rmtree(tempdir)

        # Now run certbot to register SSL certificate
        staging_arg = '--staging'
        if emailaddr:
            email_arg = '--email %s' % quote(emailaddr)
        else:
            email_arg = '--register-unsafely-without-email'
        return_code = subprocess.call('docker-compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    %s \
    %s \
    -d %s \
    --rsa-key-size 4096 \
    --agree-tos \
    --force-renewal" layerscertbot' % (staging_arg, email_arg, quote(hostname)), shell=True)
        if return_code != 0:
            print("Running certbot failed")
            sys.exit(1)

        # Stop web server (so it can effectively be restarted with the new certificate)
        return_code = subprocess.call(['docker-compose', 'stop', 'layersweb'], shell=False)
        if return_code != 0:
            print("docker-compose stop failed")
            sys.exit(1)


def edit_options_file(project_name):
    with open('.dockersetup-options', 'w') as f:
        f.write('project_name=%s\n' % project_name)


def check_connectivity():
    return_code = subprocess.call(['docker-compose', 'run', '--rm', 'layersapp', '/opt/connectivity_check.sh'], shell=False)
    if return_code != 0:
        print("Connectivity check failed - if you are behind a proxy, please check that you have correctly specified the proxy settings on the command line (see --help for details)")
        sys.exit(1)


def generatepasswords(passwordlength):
    return ''.join([random.SystemRandom().choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@%^&*-_+') for i in range(passwordlength)])

def readfile(filename):
    with open(filename, 'r') as f:
        return f.read()

def writefile(filename, data):
    with open(filename, 'w') as f:
        f.write(data)


## Get user arguments
try:
    args, socks_proxy_port, socks_proxy_host, email_host, email_port = get_args()
except argparse.ArgumentTypeError as e:
    print('error: %s' % e)
    sys.exit(1)

if args.update:
    with open('docker-compose.yml', 'r') as f:
        for line in f:
            if 'MYSQL_ROOT_PASSWORD=' in line:
                dbapassword = line.split('=')[1].rstrip().rstrip('"')
                break
    # Use last project name
    try:
        with open('.dockersetup-options', 'r') as f:
            for line in f:
                if line.startswith('project_name='):
                    args.project_name = line.split('=', 1)[1].rstrip()
    except FileNotFoundError:
        pass
else:
    # Generate secret key and database password
    secretkey = generatepasswords(50)
    dbapassword = generatepasswords(10)
    dbpassword = generatepasswords(10)
    rmqpassword = generatepasswords(10)

if args.project_name:
    os.environ['COMPOSE_PROJECT_NAME'] = args.project_name
else:
    # Get the project name from the environment (so we can save it for a future upgrade)
    args.project_name = os.environ.get('COMPOSE_PROJECT_NAME', '')

https_port = None
http_port = None
if not args.update:
    for portmap in args.portmapping.split(','):
        outport, inport = portmap.split(':', 1)
        if inport == '443':
            https_port = outport
        elif inport == '80':
            http_port = outport
    if (not https_port) and (not args.no_https):
        print("No HTTPS port mapping (to port 443 inside the container) was specified and --no-https was not specified")
        sys.exit(1)
    if not http_port:
        print("Port mapping must include a mapping to port 80 inside the container")
        sys.exit(1)

## Check if it's installed
installed = False
return_code = subprocess.call("docker ps -a | grep -q layersapp", shell=True)
if return_code == 0:
    installed = True

if args.uninstall:
    if not installed:
        print("Cannot uninstall - application does not appear to be installed")
        sys.exit(1)
elif args.update:
    if not installed:
        print("Application container not found - update mode can only be used on an existing installation")
        sys.exit(1)
    if dbapassword == 'testingpw':
        print("Update mode can only be used when previous configuration is still present in docker-compose.yml and other files")
        sys.exit(1)
elif installed and not args.reinstall:
    print('Application already installed. Please use -u/--update to update or -r/--reinstall to reinstall')
    sys.exit(1)

if not args.uninstall:
    print("""
OE Layer Index Docker setup script
----------------------------------

This script will set up a cluster of Docker containers needed to run the
OpenEmbedded Layer Index application.

Configuration is controlled by command-line arguments. If you need to check
which options you need to specify, press Ctrl+C now and then run the script
again with the --help argument.

Note that this script does have interactive prompts, so be prepared to
provide information as needed.
""")

if not (args.update or args.uninstall) and not email_host:
    print("""  WARNING: no email host has been specified - functions that require email
  (such as and new account registraion, password reset and error reports will
  not work without it. If you wish to correct this, press Ctrl+C now and then
  re-run specifying the email host with the --email-host option.
""")

if args.reinstall:
    print("""  WARNING: continuing will wipe out any existing data in the database and set
  up the application from scratch! Press Ctrl+C now if this is not what you
  want.
""")

if args.uninstall:
    print("""
  WARNING: continuing will wipe out any existing data in the database and
  uninstall the application. Press Ctrl+C now if this is not what you want.
""")

try:
    if args.uninstall:
        promptstr = 'Press Enter to begin uninstallation (or Ctrl+C to exit)...'
    elif args.update:
        promptstr = 'Press Enter to begin update (or Ctrl+C to exit)...'
    else:
        promptstr = 'Press Enter to begin setup (or Ctrl+C to exit)...'
    input(promptstr)
except KeyboardInterrupt:
    print('')
    sys.exit(2)

if not (args.update or args.uninstall):
    # Get email address
    print('')
    if args.letsencrypt:
        print('You will now be asked for an email address. This will be used for the superuser account, to send error reports to and for Let\'s Encrypt.')
    else:
        print('You will now be asked for an email address. This will be used for the superuser account and to send error reports to.')
    emailaddr = None
    while True:
        emailaddr = input('Enter your email address: ')
        if '@' in emailaddr:
            break
        else:
            print('Entered email address is not valid')

if args.reinstall or args.uninstall:
    return_code = subprocess.call(['docker-compose', 'down', '-v'], shell=False)

if args.uninstall:
    # We're done
    print('Uninstallation completed')
    sys.exit(0)

if args.update:
    args.no_https = read_dockerfile_web()
    if not args.no_https:
        container_cert_dir = '/opt/cert'
        args.hostname, https_port, certdir, certfile, keyfile = read_nginx_ssl_conf(container_cert_dir)
        edit_nginx_ssl_conf(args.hostname, https_port, certdir, certfile, keyfile)
else:
    # Always edit these in case we switch from proxy to no proxy
    edit_gitproxy(socks_proxy_host, socks_proxy_port, args.no_proxy)
    edit_dockerfile(args.http_proxy, args.https_proxy, args.no_proxy)

    edit_dockercompose(args.hostname, dbpassword, dbapassword, secretkey, rmqpassword, args.portmapping, args.letsencrypt, email_host, email_port, args.email_user, args.email_password, args.email_ssl, args.email_tls)

    edit_dockerfile_web(args.hostname, args.no_https)

    edit_settings_py(emailaddr)

    edit_options_file(args.project_name)

    if not args.no_https:
        setup_https(args.hostname, http_port, https_port, args.letsencrypt, args.cert, args.cert_key, emailaddr)

## Start up containers
return_code = subprocess.call(['docker-compose', 'up', '-d', '--build'], shell=False)
if return_code != 0:
    print("docker-compose up failed")
    sys.exit(1)

if not (args.update or args.no_connectivity):
    ## Run connectivity check
    check_connectivity()

# Get real project name (if only there were a reasonable way to do this... ugh)
real_project_name = ''
output = subprocess.check_output(['docker-compose', 'ps', '-q'], shell=False)
if output:
    output = output.decode('utf-8')
    for contid in output.splitlines():
        output = subprocess.check_output(['docker', 'inspect', '-f', '{{ .Mounts }}', contid], shell=False)
        if output:
            output = output.decode('utf-8')
            for volume in re.findall('volume ([^ ]+)', output):
                if '_' in volume:
                    real_project_name = volume.rsplit('_', 1)[0]
                    break
            if real_project_name:
                break
if not real_project_name:
    print('Failed to detect docker-compose project name')
    sys.exit(1)

# Database might not be ready yet; have to wait then poll.
time.sleep(8)
while True:
    time.sleep(2)
    # Pass credentials through environment for slightly better security
    # (avoids password being visible through ps or /proc/<pid>/cmdline)
    env = os.environ.copy()
    env['MYSQL_PWD'] = dbapassword
    # Dummy command, we just want to establish that the db can be connected to
    return_code = subprocess.call("echo | docker-compose exec -T -e MYSQL_PWD layersdb mysql -uroot layersdb", shell=True, env=env)
    if return_code == 0:
        break
    else:
        print("Database server may not be ready; will try again.")

if not args.update:
    # Import the user's supplied data
    if args.databasefile:
        return_code = subprocess.call("gunzip -t %s > /dev/null 2>&1" % quote(args.databasefile), shell=True)
        if return_code == 0:
            catcmd = 'zcat'
        else:
            catcmd = 'cat'
        env = os.environ.copy()
        env['MYSQL_PWD'] = dbapassword
        return_code = subprocess.call("%s %s | docker-compose exec -T -e MYSQL_PWD layersdb mysql -uroot layersdb" % (catcmd, quote(args.databasefile)), shell=True, env=env)
        if return_code != 0:
            print("Database import failed")
            sys.exit(1)

if not args.no_migrate:
    # Apply any pending layerindex migrations / initialize the database.
    env = os.environ.copy()
    env['DATABASE_USER'] = 'root'
    env['DATABASE_PASSWORD'] = dbapassword
    return_code = subprocess.call(['docker-compose', 'run', '--rm', '-e', 'DATABASE_USER', '-e', 'DATABASE_PASSWORD', 'layersapp', '/opt/migrate.sh'], shell=False, env=env)
    if return_code != 0:
        print("Applying migrations failed")
        sys.exit(1)

if not args.update:
    # Create normal database user for app to use
    with tempfile.NamedTemporaryFile('w', dir=os.getcwd(), delete=False) as tf:
        sqlscriptfile = tf.name
        tf.write("DROP USER IF EXISTS layers;")
        tf.write("CREATE USER layers IDENTIFIED BY '%s';\n" % dbpassword)
        tf.write("GRANT SELECT, UPDATE, INSERT, DELETE ON layersdb.* TO layers;\n")
        tf.write("FLUSH PRIVILEGES;\n")
    try:
        # Pass credentials through environment for slightly better security
        # (avoids password being visible through ps or /proc/<pid>/cmdline)
        env = os.environ.copy()
        env['MYSQL_PWD'] = dbapassword
        return_code = subprocess.call("docker-compose exec -T -e MYSQL_PWD layersdb mysql -uroot layersdb < " + quote(sqlscriptfile), shell=True, env=env)
        if return_code != 0:
            print("Creating database user failed")
            sys.exit(1)
    finally:
        os.remove(sqlscriptfile)

    ## Set the volume permissions using debian:stretch since we recently fetched it
    volumes = ['layersmeta', 'layersstatic', 'logvolume']
    with open('docker-compose.yml', 'r') as f:
        for line in f:
            if line.lstrip().startswith('- srcvolume:'):
                volumes.append('srcvolume')
                break
    for volume in volumes:
        volname = '%s_%s' % (real_project_name, volume)
        return_code = subprocess.call(['docker', 'run', '--rm', '-v', '%s:/opt/mount' % volname, 'debian:stretch', 'chown', '500', '/opt/mount'], shell=False)
        if return_code != 0:
            print("Setting volume permissions for volume %s failed" % volume)
            sys.exit(1)

## Generate static assets. Run this command again to regenerate at any time (when static assets in the code are updated)
return_code = subprocess.call("docker-compose run --rm -e STATIC_ROOT=/usr/share/nginx/html -v %s_layersstatic:/usr/share/nginx/html layersapp /opt/layerindex/manage.py collectstatic --noinput" % quote(real_project_name), shell = True)
if return_code != 0:
    print("Collecting static files failed")
    sys.exit(1)

if https_port and not args.no_https:
    protocol = 'https'
    port = https_port
    defport = '443'
else:
    protocol = 'http'
    port = http_port
    defport = '80'
if port == defport:
    host = args.hostname
else:
    host = '%s:%s' % (args.hostname, port)

if not args.update:
    if not args.databasefile:
        ## Set site name
        return_code = subprocess.call(['docker-compose', 'run', '--rm', 'layersapp', '/opt/layerindex/layerindex/tools/site_name.py', host, 'OpenEmbedded Layer Index'], shell=False)

    if not args.no_admin_user:
        ## For a fresh database, create an admin account
        print("Creating database superuser. Input user name and password when prompted.")
        return_code = subprocess.call(['docker-compose', 'run', '--rm', 'layersapp', '/opt/layerindex/manage.py', 'createsuperuser', '--email', emailaddr], shell=False)
        if return_code != 0:
            print("Creating superuser failed")
            sys.exit(1)


if args.update:
    print("Update complete")
else:
    if args.project_name:
        print("")
        print("NOTE: you may need to use -p %s (or set COMPOSE_PROJECT_NAME=\"%s\" ) if running docker-compose directly in future" % (args.project_name, args.project_name))
    print("")
    print("The application should now be accessible at %s://%s" % (protocol, host))
    print("")
