FROM node:20-bookworm-slim AS node

FROM python:3.10.19-slim-bookworm

ENV RUN_DOCKER=1

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib /usr/local/lib
COPY --from=node /lib /lib
COPY --from=node /usr/lib /usr/lib

RUN mkdir -p /app && \
    pip install --no-cache-dir requests beautifulsoup4

WORKDIR /app

COPY ./koreajc.py /app/koreajc.py

ENTRYPOINT ["/usr/local/bin/python3", "/app/koreajc.py"]

