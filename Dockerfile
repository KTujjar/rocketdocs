FROM python:3.10

WORKDIR /code/rocketdocs

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code/rocketdocs

EXPOSE 443

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "443", "--ssl-keyfile", "./creds/privkey.pem", "--ssl-certfile", "./creds/fullchain.pem"]
