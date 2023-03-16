import csv
import sys

import openai
import tenacity
from fire import Fire


@tenacity.retry(wait=tenacity.wait_exponential(min=1, max=60), stop=tenacity.stop_after_attempt(5000))
def get_embed(doc):
    embed = openai.Embedding.create(input=doc, engine='text-embedding-ada-002')
    return embed['data'][0]['embedding']


def main(openai_key, docs_csv):
    openai.api_key = openai_key
    with open(docs_csv, 'r') as f:
        reader = csv.DictReader(f)
        # Create ordinary csv writer to stdout
        writer = csv.writer(sys.stdout)
        for row in reader:
            doc = f"{row['brand']} {row['short_description']}\nBrand: {row['brand']}\nPrice: {row['price']}\n{row['long_description']}"
            embed = get_embed(doc)
            writer.writerow([row['product_id'], str(embed)])




if __name__ == '__main__':
    Fire(main)
