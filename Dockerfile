FROM buildpack-deps:latest
LABEL maintainer="Michael Halstead <mhalstead@linuxfoundation.org>"

EXPOSE 80
ENV PYTHONUNBUFFERED 1
## Uncomment to set proxy ENVVARS within container
#ENV http_proxy http://your.proxy.server:port
#ENV https_proxy https://your.proxy.server:port

RUN apt-get update
RUN apt-get install -y --no-install-recommends \
	python-pip \
	python-mysqldb \
	python-dev \
	python-imaging \
	rabbitmq-server \
	netcat-openbsd \
	vim \
	&& rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install gunicorn
RUN pip install setuptools
RUN mkdir /opt/workdir
COPY . /opt/layerindex
RUN pip install -r /opt/layerindex/requirements.txt
COPY settings.py /opt/layerindex/settings.py
COPY docker/updatelayers.sh /opt/updatelayers.sh
COPY docker/migrate.sh /opt/migrate.sh

## Uncomment to add a .gitconfig file within container
#COPY docker/.gitconfig /root/.gitconfig
## Uncomment to add a proxy script within container, if you choose to
## do so, you will also have to edit .gitconfig appropriately
#COPY docker/git-proxy /opt/bin/git-proxy

# Start Gunicorn
CMD ["/usr/local/bin/gunicorn", "wsgi:application", "--workers=4", "--bind=:5000", "--log-level=debug", "--chdir=/opt/layerindex"]
