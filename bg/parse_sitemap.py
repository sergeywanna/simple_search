import argparse
import requests
from xml.etree import ElementTree
import gzip
from io import BytesIO


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
}

def parse_main_sitemap(sitemap_url):
    response = requests.get(sitemap_url, headers=HEADERS)
    root = ElementTree.fromstring(response.content)
    urls = [element.text for element in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    return urls

def download_xml_file(url):
    response = requests.get(url, headers=HEADERS)
    content = response.text
    return content

def parse_individual_sitemap(xml_content):
    root = ElementTree.fromstring(xml_content)
    urls = [element.get('href') for element in root.findall('.//xhtml:link', namespaces={'xhtml': 'http://www.w3.org/1999/xhtml'})]
    return urls

def main():
    parser = argparse.ArgumentParser(description='Download and parse XML files from a sitemap.')
    parser.add_argument('--sitemap_url', type=str, required=True, help='URL of the main sitemap file.')
    parser.add_argument('--output', type=str, required=True, help='File to dump the list of all URLs.')

    args = parser.parse_args()

    main_sitemap_urls = parse_main_sitemap(args.sitemap_url)

    all_urls = []

    for sitemap_url in main_sitemap_urls:
        xml_content = download_xml_file(sitemap_url)
        urls = parse_individual_sitemap(xml_content)
        all_urls.extend(urls)

    with open(args.output, 'w') as output_file:
        for url in all_urls:
            output_file.write(f'{url}\n')


if __name__ == '__main__':
    main()