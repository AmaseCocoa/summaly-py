FROM python:3.12.5-slim-bookworm

RUN apt-get update && apt-get install -y libmimalloc2.0 libmimalloc-dev

RUN pip install pdm

ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libmimalloc.so

WORKDIR /

COPY pyproject.toml .

RUN pdm install --frozen-lockfile

COPY . .

CMD ["granian", "--interface", "asgi", "pysummaly.server:app"]
