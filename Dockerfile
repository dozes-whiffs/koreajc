FROM alpine

ENV RUN_DOCKER=1

RUN apk add nodejs python3 py3-requests py3-beautifulsoup4 && \
    mkdir -p /app

WORKDIR /app

COPY ./koreajc.py /app/koreajc.py

ENTRYPOINT ["/usr/bin/python3", "/app/koreajc.py"]

