FROM python:3.9-slim

WORKDIR /search

COPY server_requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY search_server.py .

COPY features.csv data.csv
COPY embedds.csv embedds.csv

EXPOSE 8000

ENV EMBEDDINGS_CSV=embedds.csv
ENV DATA_CSV=data.csv
ENV EXTERNAL_WEBSITE_SEARCH_URL=https://www.bergdorfgoodman.com/search/

ENTRYPOINT ["gunicorn", "-w", "4", "--preload", "-b", "0.0.0.0:8000", "search_server:app"]

