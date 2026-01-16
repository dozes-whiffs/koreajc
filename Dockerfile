FROM python:3.10.19-slim-bookworm


ENV RUN_DOCKER=1

RUN mkdir -p /app && \
    pip install requests beautifulsoup4 py_mini_racer

WORKDIR /app

COPY ./koreajc.py /app/koreajc.py

ENTRYPOINT ["/usr/local/bin/python3", "/app/koreajc.py"]
