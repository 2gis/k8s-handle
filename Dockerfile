FROM python:3.6-alpine

LABEL description="Image with k8s-handle" \
      maintainer="<Infrastructure & Operations> io@2gis.ru" \
      source="https://github.com/2gis/k8s-handle"

ADD . /opt/k8s-handle/

RUN apk --no-cache add git ca-certificates bash openssl gcc libc-dev libffi-dev openssl-dev make \
    && pip install -r /opt/k8s-handle/requirements.txt \
    && apk del gcc libc-dev libffi-dev openssl-dev \
    && chmod +x /opt/k8s-handle/k8s-handle.py \
    && ln -s /opt/k8s-handle/k8s-handle.py /opt/k8s-handle/k8s-handle

ENV PATH="/opt/k8s-handle:${PATH}"

WORKDIR /tmp/
