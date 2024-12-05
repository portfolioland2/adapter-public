FROM python:3.10-slim
ENV PYTHONUNBUFFERED 1
ARG CI_JOB_TOKEN
ENV POETRY_HTTP_BASIC_GITLAB_USERNAME gitlab-ci-token
ENV POETRY_HTTP_BASIC_GITLAB_PASSWORD $CI_JOB_TOKEN

RUN apt-get update && apt-get install -yqq curl gcc vim
RUN apt-get install --fix-broken

RUN pip3 install --upgrade keyrings.alt
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

ENV PYTHONPATH=/

RUN mkdir /code
WORKDIR /code

COPY poetry.lock pyproject.toml /code/
RUN poetry install
