FROM python:3.10-alpine

LABEL description="Image with k8s-handle" \
      maintainer="sre@jetbrains.com" \
      source="https://github.com/jetbrains-infra/k8s-handle"

ADD . /opt/k8s-handle/

RUN apk --no-cache add git ca-certificates bash openssl gcc libc-dev libffi-dev openssl-dev make \
    && cd /opt/k8s-handle \
    && python setup.py install \
    && apk del gcc libc-dev libffi-dev openssl-dev

ENV PATH="/opt/k8s-handle:${PATH}"

WORKDIR /tmp/
