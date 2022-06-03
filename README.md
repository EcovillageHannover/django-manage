![Logo](https://www.ecovillage-hannover.de/ecovillage/media/site/98cbe6c83e-1598234117/ecovillage_hannover_0_animated.svg)

# My-EVH Services

## Local Setup

### 1. Clone this repository

```sh
git clone https://github.com/EcovillageHannover/django-manage.git
```

### 2. Install dependencies (preferably in a virtual environment of sorts)

```sh
pip install -r requirements.txt
```

**Note:** If you have trouble installing `psycopg2`, try commenting it and installing `psycopg2-binary` instead.

### 3. Create your settings_local.py

Create the file `./evh/settings_local.py` with the following content:
```py
import os

BASE_URL = "https://my-evh.local"
ALLOWED_HOSTS = ['my-evh.local', 'localhost', '127.0.0.1]

DEBUG = True
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'django',
        'USER': 'django',
        'PASSWORD': 'CHANGEME',
        'HOST': 'localhost',
        'PORT': '5432'
    }
}

MARKDOWNIFY_BLEACH=False
MARKDOWNIFY_MARKDOWN_EXTENSIONS =['evh.markdown_tables', 'tables']

EMAIL_FROM = "EVH Tech-Support Developer  <support@example.de>"
EMAIL_HOST = "mail.example.de"
EMAIL_HOST_USER = "support@example.de"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    'guardian.backends.ObjectPermissionBackend'
]
```

Replace the database password with a password of your choosing.

### 4. Setup a postgresql instance

The easiest way to do so is using docker. Assuming you [have docker setup](https://docs.docker.com/engine/install/), 
you can start a postgresql container with the following command:

```sh
docker volume create evh-db
docker run -d --name evh-db -v evh-db:/var/lib/postgresql/data \
  -e POSTGRES_DB=django -e POSTGRES_USER=django -e POSTGRES_PASSWORD=CHANGEME \
  -p 5432:5432 postgres:12-alpine
```

**Make sure the postgres password matches the one specified as database password in step 3!**

### 5. Initialize postgres

In order to run the application, you will have to initialize the database with the following command:

```sh
python ./manage.py migrate
```

### 6. Create a django superuser

You can create your django superuser as such:

```sh
python ./manage.py createsuperuser
```

### 7. Start the application

You can now start the application

```sh
python ./manage.py runserver
```

The app should be accessible at http://localhost:8000
