FROM python:3.12.5-slim-bookworm
WORKDIR /

COPY . .

RUN apt-get update && \
    apt-get install -y libmimalloc2.0 libmimalloc-dev gcc && \
    pip install pdm && \
    pdm install --frozen-lockfile

ENV PORT=3030
ENV LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libmimalloc.so
CMD exec pdm run granian --interface asgi --port $PORT --host 0.0.0.0 pysummaly.server:app --access-log
