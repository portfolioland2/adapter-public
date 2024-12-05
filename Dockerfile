ARG BUILD_IMAGE
FROM ${BUILD_IMAGE}

WORKDIR /code
COPY ./deploy/ /code/deploy/
COPY ./src/ /code/src/
COPY cli.py /code/

COPY ./migrations /code/migrations/
COPY alembic.ini /code/
COPY start.sh /code/
COPY start.celery.sh /code/
RUN chmod +x /code/start.sh /code/start.celery.sh

EXPOSE 80
