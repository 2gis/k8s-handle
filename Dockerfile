FROM python:3.6-alpine

LABEL description="Image with k8s-handle" \
      maintainer="<Infrastructure & Operations> io@2gis.ru" \
      source="https://github.com/2gis/k8s-handle"

ENV PATH="/opt/k8s-handle:${PATH}"

WORKDIR /tmp/

ADD . /opt/k8s-handle/

RUN apk --no-cache add ca-certificates openssl \
    && apk --no-cache add gcc libc-dev libffi-dev openssl-dev make --virtual .build-deps \
    && pip install --no-cache-dir -r /opt/k8s-handle/requirements.txt \
    && apk del .build-deps \
    && chmod +x /opt/k8s-handle/k8s-handle.py \
    && ln -s /opt/k8s-handle/k8s-handle.py /opt/k8s-handle/k8s-handle