FROM python:3.12.5-slim-bullseye

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/microsoft/mimalloc.git && \
    cd mimalloc && \
    mkdir -p out/release && \
    cd out/release && \
    cmake ../.. && \
    make && \
    make install && \
    cd ../../.. && \
    rm -rf mimalloc

ENV LD_PRELOAD=/usr/local/lib/libmimalloc.so

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["granian", "--interface", "asgi", "docker.backend:app"]
