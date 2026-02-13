FROM alpine:3.20

ENV RUN_DOCKER=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache \
    nodejs \
    python3 \
    py3-requests \
    py3-beautifulsoup4 && \
    mkdir -p /app

WORKDIR /app

COPY ./koreajc.py /app/koreajc.py

ENTRYPOINT ["/usr/bin/python3", "-u", "/app/koreajc.py"]
