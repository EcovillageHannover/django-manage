FROM python:3

RUN apt-get update && apt-get install -y libldap2-dev libsasl2-dev

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

VOLUME /usr/src/app

EXPOSE 8000

CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000"]
