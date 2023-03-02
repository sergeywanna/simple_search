import collections
import concurrent
import copy
import hashlib
import io
import os
import gzip
import time
import urllib
from collections import deque
import re

import attrdict as attrdict
import yaml
from fire import Fire
import requests
from lxml import etree


def parse_config(config, params):
    with open(config) as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    # Updates config with params, even when they are nested in each other.
    for k, v in params.items():
        keys = k.split('.')
        d = config
        for key in keys[:-1]:
            d = d[key]
        d[keys[-1]] = v
    config = attrdict.AttrDict(config)
    return config


class ScrapeQueue:
    def __init__(self, base_dir, scrape_config):
        self._config = scrape_config
        self._base_dir = base_dir
        self._added = set()
        self._regexps = [re.compile(r) for r in self._config.get('priorities', [])]
        self._queues = [deque() for _ in range(len(self._regexps) + 1)]

    def _url_priority(self, url):
        ps = self._config.get('priorities', [])
        for i, regex in enumerate(self._regexps):
            if regex.match(url):
                return i
        return len(ps)

    def add(self, url):
        if url not in self._added:
            self._queues[self._url_priority(url)].append(url)
            print(f"{url}: Scheduled for download.")
            self._added.add(url)
        else:
            print("  " + url + " (skipped)")

    def pop(self):
        self._processed_count += 1
        for q in self._queues:
            if q:
                return q.popleft()
        raise Exception("No more pages to process.")

    @property
    def _processed_count(self):
        return self._state.get('processed_count', 0)

    @_processed_count.setter
    def _processed_count(self, value):
        self._state.processed_count = value

    def __bool__(self):
        return any(self._queues) and self._processed_count < self._config.max_pages

    # Save state to file when the scope is left.
    def __enter__(self):
        if self._config.state_file:
            self._state_fname = os.path.join(self._base_dir, self._config.state_file)
        else:
            self._state_fname = None
        if self._state_fname and os.path.exists(self._state_fname):
            with open(self._state_fname) as f:
                self._state = attrdict.AttrDict(yaml.load(f, Loader=yaml.FullLoader))
        else:
            self._state = attrdict.AttrDict()

        if 'added' in self._state:
            self._added = set(self._state.added)

        if 'queues' in self._state:
            self._queues = [deque(q) for q in self._state.queues]

        return self

    def _cleanup(self):
        if self._state_fname:
            with open(self._state_fname, 'w') as f:
                res = dict(self._state)
                res['queues'] = [list(q) for q in self._queues]
                res['added'] = list(self._added)
                yaml.dump(res, f)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()


class Parser:
    def __init__(self, base_dir, config, queue):
        self._base_dir = base_dir
        self.config = config
        self._last_request_time = None
        self._queue = queue

        # Create dump dir if it doesn't exist.
        self._dump_dir = os.path.join(self._base_dir, self.config.dump_dir)
        if not os.path.exists(self._dump_dir):
            os.makedirs(self._dump_dir)

        self.parsers = collections.OrderedDict()
        for parser in self.config.parsers:
            if parser.method == 'parse_sitemap':
                config = copy.deepcopy(parser.config)
                method = lambda url, cfg=config: self._parse_sitemap(cfg, url)
            elif parser.method == 'parse_products_gz':
                config = copy.deepcopy(parser.config)
                method = lambda url, cfg=config: self._parse_products_gz(cfg, url)
            elif parser.method == 'dump':
                method = lambda url: self._dump(url)
            else:
                raise Exception("Unknown parser method: " + parser.method)
            self.parsers[re.compile(parser.pattern)] = method

    def _parse_sitemap(self, config, url):
        content = self._fetch(url)
        root = etree.fromstring(content)
        ns_map = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                  "re": "http://exslt.org/regular-expressions"}
        result = []
        for match in root.xpath(config.xpath, namespaces=ns_map):
            result.append(str(match))
        return result

    def _parse_products_gz(self, config, url):
        result = []
        content = self._fetch(url)
        with gzip.open(io.BytesIO(content), 'rt') as f:
            root = etree.fromstring(f.read())
            ns_map = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                      'image': 'http://www.google.com/schemas/sitemap-image/1.1'}
            for product in root.xpath(config.xpath, namespaces=ns_map):
                for url in product.xpath(config.url_xpath, namespaces=ns_map):
                    result.append(str(url))
                if 'image_xpath' in config:
                    for image in product.xpath(config.image_xpath, namespaces=ns_map):
                        result.append(str(image))
        return result

    @staticmethod
    def _url2fname(url):
        hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        ext = url.split('.')[-1]
        if len(ext) > 4:
            ext = ''
        else:
            ext = '.' + 'html' if ext == 'aspx' else ext
        return hash + ext

    def _dump(self, url):
        fname = self._url2fname(url)
        with open(os.path.join(self._dump_dir, fname), 'wb') as f:
            # TODO: Check that there was no redirect and the URL is the same.
            f.write(self._fetch(url))

        # Append URL to index file.
        with open(os.path.join(self._dump_dir, 'index.txt'), 'a') as f:
            f.write(url + '\n')

    def _fetch(self, url):
        if urllib.parse.urlparse(url).scheme == 'file':
            with open(urllib.parse.urlparse(url).path, 'rb') as f:
                return f.read()
        elif 'scraper_api' in self.config:
            payload = {'api_key': self.config.scraper_api.key,
                       'render': False,
                       'country_code': self.config.scraper_api.get('country_code', 'us'),
                       'url': url}
            response = requests.get('http://api.scraperapi.com', params=payload)
        else:
            response = requests.get(url, headers=self.config.get('headers', {}))

        if response.status_code != 200:
            raise Exception(f"Failed to fetch {url}: {response.status_code}")
        return response.content

    def parse_url(self, url):
        print(f"Processing {url}")
        # Check if we need to throttle next request.
        if self._last_request_time and 'throttle_per_second' in self.config:
            elapsed = time.time() - self._last_request_time
            if elapsed < 1 / self.config.throttle_per_second:
                time.sleep(1 / self.config.throttle_per_second - elapsed)

        for regex, method in self.parsers.items():
            if regex.search(url):
                self._last_request_time = time.time()
                res = method(url)
                if res is None:
                    res = []
                return res

        print(f"Could not find parser for {url}")

    def run(self):
        if 'concurrency' not in self.config or self.config.concurrency == 1:
            # Single-threaded mode.
            while self._queue:
                url = self._queue.pop()
                for new_url in self.parse_url(url):
                    self._queue.add(new_url)
        else:
            # Multi-threaded mode.
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
                futures = set()
                count = 0
                def done_closure(future):
                    nonlocal count
                    for new_url in future.result():
                        self._queue.add(new_url)
                    futures.remove(future)
                    count += 1

                try:
                    while True:
                        if not self._queue:
                            concurrent.futures.wait(futures)
                            if not self._queue:
                                break

                        url = self._queue.pop()
                        future = executor.submit(self.parse_url, url)
                        futures.add(future)
                        future.add_done_callback(done_closure)

                    print(f'Total of {count} URLs processed.')
                except KeyboardInterrupt:
                    print("Keyboard interrupt, waiting for scraper threads to finish...")
                    executor.shutdown(wait=True)
                    print("Done")
                    raise


def main(config, **params):
    base_dir = os.path.dirname(config)
    config = parse_config(config, params)

    with ScrapeQueue(base_dir, config.scrape) as queue:
        for seed in config.seeds:
            queue.add(seed)

        parser = Parser(base_dir, config.parser_config, queue)
        try:
            parser.run()
        except KeyboardInterrupt:
            queue.__exit__(None, None, None)
            raise


if __name__ == '__main__':
    Fire(main)
