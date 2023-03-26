import argparse
import csv
import openai
import os
from flask import Flask, render_template_string, request
import numpy as np
import requests

# External website search URL
EXTERNAL_WEBSITE_SEARCH_URL = "https://www.example.com/search"

# Initialize Flask and OpenAI
app = Flask(__name__)

search_engine = None

class SearchEngine:
    def __init__(self, embeddings_csv, data_csv):
        self.embeddings, self.data = self.load_data(embeddings_csv, data_csv)
        self.urls = np.array(list(self.embeddings.keys()))
        self.embeddings = np.array(list(self.embeddings.values()))

    @staticmethod
    def load_data(embeddings_csv, data_csv):
        with open(embeddings_csv) as f:
            reader = csv.reader(f)
            embeddings = {row[0]: np.array(eval(row[1])) for row in reader}

        with open(data_csv) as f:
            reader = csv.DictReader(f)
            data = {row["url"]: row for row in reader}

        return embeddings, data

    def search(self, query):
        q_emb = openai.Embedding.create(input=query, engine='text-embedding-ada-002')['data'][0]['embedding']
        q_emb = np.array(q_emb)
        sim = np.dot(self.embeddings, q_emb)
        top = np.argsort(sim)[::-1][:30]
        return [self.data[url] for url in self.urls[top]]

# Generate the search results
def get_external_search_results(query):
    search_url = f"{EXTERNAL_WEBSITE_SEARCH_URL}?q={requests.utils.quote(query)}"
    return search_url


# Define the HTML template for search results
RESULT_TEMPLATE = """
<div class="result">
    <a href="{{ result.url }}" target="_blank" class="result-link">
        <img src="https:{{ result.picture }}" alt="{{ result.brand }} {{ result.short }}">
        <div class="result-info">
            <h3>{{ result.brand }}</h3>
            <h4>{{ result.short }}</h4>
            <p>{{ result.price }}</p>
        </div>
    </a>
</div>
"""


# Define the main route
@app.route("/", methods=["GET"])
def index():
    results = []
    external_results = ""

    query = request.args.get("query")
    if query:
        results = search_engine.search(query)
        results = [render_template_string(RESULT_TEMPLATE, result=result) for result in results]
        external_results = get_external_search_results(query)

    return render_template_string("""
    <style>
        body {
            font-family: Larsseit sans-serif;
        }
        .results-container {
            display: flex;
            flex-wrap: wrap;
            margin-left: -8px;
            margin-right: -8px;
        }
        .result {
            width: calc(50% - 48px);
            margin: 8px;
            padding: 16px;
            background-color: #f8f8f8;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 2px rgba(0, 0, 0, 0.24);
        }
        .result img {
            max-width: 100%;
            max-height: 800px;
            height: auto;
        }
        .result-link {
            text-decoration: none;
            color: inherit;
        }
        .result-info {
            margin-top: 8px;
        }
        .result-info h3 {
            margin: 0;
            font-size: 15px;
        }
        .result-info h4 {
            margin: 0;
            font-size: 12px;
        }
        .result-info p {
            margin: 0;
        }
    </style> 
    <form method="get">
        <input type="text" name="query" placeholder="Search" value="{{ query }}">
        <button type="submit">Search</button>
    </form>
    <div style="display: flex;">
        <div style="flex: 1;">
            <div class="results-container">
                {% for result in results %}
                    {{ result | safe }}
                {% endfor %}
            </div>
        </div>
        <div style="flex: 1;">
            {% if external_results %}
                <iframe src="{{ external_results }}" width="100%" height="1000" frameborder="0"></iframe>
            {% endif %}
        </div>
    </div>
    """,
                                  results=results, external_results=external_results, RESULT_TEMPLATE=RESULT_TEMPLATE)

openai.api_key = os.environ.get("OPENAI_API_KEY")
EXTERNAL_WEBSITE_SEARCH_URL = os.environ.get("EXTERNAL_WEBSITE_SEARCH_URL")
search_engine = SearchEngine(os.environ.get("EMBEDDINGS_CSV"), os.environ.get("DATA_CSV"))

if __name__ == "__main__":
    app.run()
