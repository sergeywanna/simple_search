FROM python:3.9-alpine

WORKDIR /search

COPY server_requirements.txt requirements.txt
# Install build dependencies
RUN apk add --no-cache --virtual .build-deps \
    build-base \
    linux-headers \
    libffi-dev \
    python3-dev \
    py3-pip \
    freetype-dev \
    libpng-dev \
    openblas-dev

# Install runtime dependencies
RUN apk add --no-cache \
    libstdc++ \
    openblas

WORKDIR /search

# Install Python packages
COPY server_requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Clean up build dependencies
RUN apk del .build-deps

# RUN pip install --no-cache-dir -r requirements.txt

COPY search_server.py .
COPY features.csv data.csv
COPY urls.txt .
COPY embedds.npy .

EXPOSE 8000

ENV URLS_TXT=urls.txt
ENV EMBEDDINGS_NPY=embedds.npy
ENV DATA_CSV=data.csv
ENV EXTERNAL_WEBSITE_SEARCH_URL=https://www.bergdorfgoodman.com/search/

ENTRYPOINT ["gunicorn", "-w", "4", "--preload", "-b", "0.0.0.0:8000", "search_server:app"]

