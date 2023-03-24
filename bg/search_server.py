import argparse
import csv
import openai
from flask import Flask, render_template_string, request
import numpy as np
import requests
from bs4 import BeautifulSoup

# Replace with your OpenAI API key
OPENAI_API_KEY = "your-api-key"

# External website search URL
EXTERNAL_WEBSITE_SEARCH_URL = "https://www.example.com/search"

# Initialize Flask and OpenAI
app = Flask(__name__)


# Load data from CSV files
def load_data(embeddings_csv, data_csv):
    with open(embeddings_csv) as f:
        reader = csv.reader(f)
        embeddings = {row[0]: eval(row[1]) for row in reader}

    with open(data_csv) as f:
        reader = csv.DictReader(f)
        data = {row["url"]: row for row in reader}

    return embeddings, data


# Compute the cosine similarity
def search(query):
    q_emb = openai.Embedding.create(input=query, engine='text-embedding-ada-002')['data'][0]['embedding']
    scores = [(url, np.dot(q_emb, embedding)) for url, embedding in embeddings.items()]
    scores.sort(key=lambda x: x[1], reverse=True)
    return [data[url] for url, _ in scores[:30]]

# Generate the search results
def get_external_search_results(query):
    search_url = f"{EXTERNAL_WEBSITE_SEARCH_URL}?q={requests.utils.quote(query)}"
    return search_url

# Define the HTML template for search results
RESULT_TEMPLATE = """
<div class="result">
    <a href="{{ result.URL }}" target="_blank" class="result-link">
        <img src="https:{{ result.picture }}" alt="{{ result.brand }} {{ result.short }}">
        <div class="result-info">
            <h3>{{ result.brand }} {{ result.short }}</h3>
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
        results = search(query)
        results = [render_template_string(RESULT_TEMPLATE, result=result) for result in results]
        external_results = get_external_search_results(query)

    return render_template_string("""
    <style>
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
            font-size: 16px;
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
    """, results=results, external_results=external_results, RESULT_TEMPLATE=RESULT_TEMPLATE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A simple web server for searching CSV data.")
    parser.add_argument("--openai_key", required=True, help="Your OpenAI API key")
    parser.add_argument("--embeddings_csv", required=True, help="Path to the embeddings CSV file")
    parser.add_argument("--data_csv", required=True, help="Path to the data CSV file")
    parser.add_argument("--external_search_url", required=True, help="External website search URL")
    args = parser.parse_args()

    openai.api_key = args.openai_key
    EXTERNAL_WEBSITE_SEARCH_URL = args.external_search_url

    embeddings, data = load_data(args.embeddings_csv, args.data_csv)
    app.run()
