FROM python:3.10.19-slim-bookworm


RUN mkdir -p /app && \
    pip install requests beautifulsoup4

WORKDIR /app

COPY ./koreajc.py /app/koreajc.py

ENTRYPOINT ["/usr/bin/python3", "/app/koreajc.py"]

