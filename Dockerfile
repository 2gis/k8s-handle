FROM python:3.6-alpine

LABEL description="Image with k8s-handle" \
      maintainer="<Infrastructure & Operations> io@2gis.ru" \
      source="https://github.com/2gis/k8s-handle"

ADD . /opt/k8s-handle/

RUN apk --no-cache add git ca-certificates bash openssl gcc libc-dev libffi-dev openssl-dev make \
    && cd /opt/k8s-handle \
    && python setup.py install \
    && apk del gcc libc-dev libffi-dev openssl-dev

ENV PATH="/opt/k8s-handle:${PATH}"

WORKDIR /tmp/
