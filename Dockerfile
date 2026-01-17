FROM python:3.10.19-slim-bookworm

ENV RUN_DOCKER=1

RUN mkdir -p /app && \
    apt update && \
    apt install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/{apt,dpkg,cache,log}/ && \
    pip install requests beautifulsoup4 quickjs

WORKDIR /app

COPY ./koreajc.py /app/koreajc.py

ENTRYPOINT ["/usr/local/bin/python3", "/app/koreajc.py"]
