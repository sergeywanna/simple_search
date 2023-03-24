import csv
import sys

import openai
import tenacity
import tqdm
from fire import Fire


@tenacity.retry(wait=tenacity.wait_exponential(min=1, max=60), stop=tenacity.stop_after_attempt(5000))
def get_embed(doc):
    embed = openai.Embedding.create(input=doc, engine='text-embedding-ada-002')
    return embed['data'][0]['embedding']


def main(openai_key, docs_csv, template, output_file, debug=0):
    openai.api_key = openai_key

    # Read existing output file and create a set of processed URLs
    processed_urls = set()
    try:
        with open(output_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                processed_urls.add(row[0])
    except FileNotFoundError:
        pass  # If the output file does not exist, proceed with an empty set of processed URLs

    with open(docs_csv, 'r') as f:
        reader = csv.DictReader(f)

        # Open the output file in append mode
        with open(output_file, 'a', newline='') as outfile:
            writer = csv.writer(outfile)

            i = 0
            for row in tqdm.tqdm(reader):
                url = row['url']
                if url not in processed_urls:
                    doc = template.format(**row)
                    if debug != 0 and i % debug == 0:
                        print(doc, file=sys.stderr)
                    embed = get_embed(doc)
                    writer.writerow([url, str(embed)])
                    i += 1


if __name__ == '__main__':
    Fire(main)
