#!/usr/bin/env python3
import argparse
import re
import subprocess
import time
import random

# This script will make a cluster of 5 containers:

#  - layersapp: the application
#  - layersdb: the database
#  - layersweb: NGINX web server (as a proxy and for serving static content)
#  - layerscelery: Celery (for running background jobs)
#  - layersrabbit: RabbitMQ (required by Celery)

# It will build and run these containers and set up the database.
# Copyright (C) 2018 Intel Corporation
# Author: Amber Elliot <amber.n.elliot@intel.com>
#
# Licensed under the MIT license, see COPYING.MIT for details

def get_args():
	parser = argparse.ArgumentParser(
	description='Script sets up the Layer Index tool with Docker Containers.')
	parser.add_argument('-o', '--hostname', type=str, help='Hostname of your machine. Defaults to localhost if not set.', required=False, default = "localhost")
	parser.add_argument('-p', '--http-proxy', type=str, help='http proxy in the format http://<myproxy:port>', required=False)
	parser.add_argument('-s', '--https-proxy', type=str, help='https proxy in the format http://<myproxy:port>', required=False)
	parser.add_argument('-d', '--databasefile', type=str, help='Location of your database file to import. Must be a .sql file.', required=False)
	parser.add_argument('-m', '--portmapping', type=str, help='Port mapping in the format HOST:CONTAINER. Default is set to 8080:80', required=False, default = '8080:80')
	args = parser.parse_args()
	port = proxymod = ""
	try:
		if args.http_proxy:
			split = args.http_proxy.split(":")
			port = split[2]
			proxymod = split[1].replace("/", "")
	except IndexError:
		raise argparse.ArgumentTypeError("http_proxy must be in format http://<myproxy:port>")
	

	if len(args.portmapping.split(":")) != 2:
		raise argparse.ArgumentTypeError("Port mapping must in the format HOST:CONTAINER. Ex: 8080:80")
	return args.hostname, args.http_proxy, args.https_proxy, args.databasefile, port, proxymod, args.portmapping

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


# Add hostname, secret key, db info, and email host in docker-compose.yml
def edit_dockercompose(hostname, dbpassword, secretkey, portmapping):
	filedata= readfile("docker-compose.yml")
	portflag = False
	newlines = []
	lines = filedata.splitlines()
	for line in lines:
		if portflag == True :
			format = line[0:line.find("-")].replace("#", "")
			print (format)
			newlines.append(format + '- "' + portmapping + '"' + "\n")
			portflag = False
		elif "hostname:" in line:
			format = line[0:line.find("hostname")].replace("#", "")
			newlines.append(format +"hostname: " + hostname + "\n")
		elif "- SECRET_KEY" in line:
			format = line[0:line.find("- SECRET_KEY")].replace("#", "")
			newlines.append(format +"- SECRET_KEY=" + secretkey + "\n")
		elif "- DATABASE_PASSWORD" in line:
			format = line[0:line.find("- DATABASE_PASSWORD")].replace("#", "")
			newlines.append(format +"- DATABASE_PASSWORD=" + dbpassword + "\n")
		elif "- MYSQL_ROOT_PASSWORD" in line:
			format = line[0:line.find("- MYSQL_ROOT_PASSWORD")].replace("#", "")
			newlines.append(format +"- MYSQL_ROOT_PASSWORD=" + dbpassword + "\n")
		elif "ports:" in line:
			newlines.append(line + "\n")
			portflag = True
		else:
			newlines.append(line + "\n")
	writefile("docker-compose.yml", ''.join(newlines))

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

## Get user arguments and modify config files
hostname, http_proxy, https_proxy, dbfile, port, proxymod, portmapping = get_args()

if http_proxy:
	edit_gitproxy(proxymod, port)
if http_proxy or https_proxy:
	edit_dockerfile(http_proxy, https_proxy)

edit_dockercompose(hostname, dbpassword, secretkey, portmapping)

## Start up containers
return_code = subprocess.call("docker-compose up -d", shell=True)

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

## For a fresh database, create an admin account
print("Creating database superuser. Input user name, email, and password when prompted.")
return_code = subprocess.call("docker-compose run --rm layersapp /opt/layerindex/manage.py createsuperuser", shell=True)  

## Set the volume permissions using debian:stretch since we recently fetched it
return_code = subprocess.call("docker run --rm -v layerindexweb_layersmeta:/opt/workdir debian:stretch chown 500 /opt/workdir && \
		 docker run --rm -v layerindexweb_layersstatic:/usr/share/nginx/html debian:stretch chown 500 /usr/share/nginx/html", shell=True)  


## Generate static assets. Run this command again to regenerate at any time (when static assets in the code are updated)
return_code = subprocess.call("docker-compose run --rm -e STATIC_ROOT=/usr/share/nginx/html -v layerindexweb_layersstatic:/usr/share/nginx/html layersapp /opt/layerindex/manage.py collectstatic --noinput", shell = True)