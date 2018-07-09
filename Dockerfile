FROM buildpack-deps:latest
LABEL maintainer="Michael Halstead <mhalstead@linuxfoundation.org>"

EXPOSE 80
ENV PYTHONUNBUFFERED=1 \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    LC_CTYPE=en_US.UTF-8
## Uncomment to set proxy ENVVARS within container
#ENV http_proxy http://your.proxy.server:port
#ENV https_proxy https://your.proxy.server:port

COPY requirements.txt /
RUN apt-get update
RUN apt-get install -y --no-install-recommends \
	python-pip \
	python-mysqldb \
	python-dev \
	python-imaging \
	python3-pip \
	python3-mysqldb \
	python3-dev \
	python3-pil \
	locales \
	rabbitmq-server \
	netcat-openbsd \
	vim \
	&& rm -rf /var/lib/apt/lists/*
RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen \
	&& locale-gen en_US.UTF-8 \
	&& update-locale
RUN pip install --upgrade pip
RUN pip3 install gunicorn
RUN pip install setuptools
RUN pip3 install setuptools
RUN pip install -r /requirements.txt
RUN pip3 install -r /requirements.txt
RUN mkdir /opt/workdir
COPY . /opt/layerindex
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
