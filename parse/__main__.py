import csv
import os
import re

from bs4 import BeautifulSoup
from fire import Fire


def main(dump_dir, output):
    # List all HTML files in dump_dir
    html_files = []
    for root, dirs, files in os.walk(dump_dir):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))

    with open(output, 'w') as f:
        csv_writer = csv.DictWriter(
            f, fieldnames=['product_id', 'brand', 'short_description', 'long_description', 'price'])
        csv_writer.writeheader()
        for file in html_files:
            # skip file if it is empty
            if os.stat(file).st_size == 0:
                continue

            with open(file, 'r') as html:
                print(f'Reading {file}')
                soup = BeautifulSoup(html, 'html.parser')
                # Find h4 that has text 'Product IDs', then in the next p find span and get text
                try:
                    availability = soup.select_one('meta[property="og:availability"]')['content']
                    if availability != 'in stock':
                        continue
                    product_id = soup.find('h4', string='Product IDs').find_next('p').find('span').text.strip()
                    h1 = soup.find('h1')
                    brand = h1.find('a').text
                    short_description = h1.find('p').text
                    price = soup.find('p', attrs={'data-component': ['PriceLarge', 'PriceFinalLarge']}).text.strip()
                    desc = soup.find('div', attrs={'data-component': 'TabPanelContainer'}).find('div').find('div').find(
                        'div').find('p', recursive=False)
                    if desc is not None:
                        desc = desc.text.strip()
                        desc = re.sub(r'\s+', ' ', desc)
                    csv_writer.writerow({
                        'product_id': product_id,
                        'brand': brand,
                        'short_description': short_description,
                        'long_description': desc,
                        'price': price
                    })
                except Exception as e:
                    print(f'Error parsing {file}: {e}')


if __name__ == '__main__':
    Fire(main)
