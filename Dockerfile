# See README for how to use this.

FROM python:3.12

# If something doesn't work, try reaching out the the maintainers.
LABEL maintainer="Michael Halstead <mhalstead@linuxfoundation.org>"
LABEL maintainer="Piotr Buliński <piotr@qbee.io>"

# Setup a non-root user to run the application
RUN useradd -m -r layerindex -s /bin/bash && \
   install -d -o layerindex -g layerindex -m 755 /app \
   install -d -o layerindex -g layerindex -m 755 /opt/layerindex-web

# Set the working directory inside the container
WORKDIR /app

# Set environment variables 
# Prevents Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1

# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Set the Django settings module
ENV DJANGO_SETTINGS_MODULE=settings

# Upgrade pip
RUN pip install --upgrade pip 

# Copy the Django project  and install dependencies
COPY requirements.txt  /app/
COPY requirements-dev.txt  /app/
 
# run this command to install all dependencies 
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

# Switch to non-root user
USER layerindex

# Copy the Django project to the container
COPY . /app/

# Expose the Django port
EXPOSE 8000

# Run Django’s development server
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]