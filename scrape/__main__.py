import hashlib
import os
import time
import urllib
from collections import deque
import re

import attrdict as attrdict
import yaml
from fire import Fire
import requests
from bs4 import BeautifulSoup


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
        # Strip acnhors from url.
        url = url.split('#')[0]
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._state_fname:
            with open(self._state_fname, 'w') as f:
                res = dict(self._state)
                res['queues'] = [list(q) for q in self._queues]
                res['added'] = list(self._added)
                yaml.dump(res, f)


class Parser:
    def __init__(self, base_dir, config):
        self._base_dir = base_dir
        self.config = config
        self._last_request_time = None

        # Create dump dir if it doesn't exist.
        self._dump_dir = os.path.join(self._base_dir, self.config.dump_dir)
        if not os.path.exists(self._dump_dir):
            os.makedirs(self._dump_dir)

    def _dump(self, text, url):
        hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        fname = os.path.join(self._dump_dir, hash)
        with open(fname, 'w') as f:
            f.write(text)

        # Append URL to index file.
        with open(os.path.join(self._dump_dir, 'index.txt'), 'a') as f:
            f.write(url + '\n')

    def _fetch(self, url):
        if 'scraper_api' in self.config:
            payload = {'api_key': self.config.scraper_api.key,
                       'render': False,
                       'country_code': self.config.scraper_api.get('country_code', 'us'),
                       'url': url}
            response = requests.get('http://api.scraperapi.com', params=payload)
        else:
            response = requests.get(url, headers=self.config.get('headers', {}))

        if response.status_code != 200:
            raise Exception(f"Failed to fetch {url}: {response.status_code}")
        return response.text

    def parse(self, queue, url):
        print(f"Processing {url}")
        # Check if we need to throttle next request.
        if self._last_request_time and 'throttle_per_second' in self.config:
            elapsed = time.time() - self._last_request_time
            if elapsed < 1 / self.config.throttle_per_second:
                time.sleep(1 / self.config.throttle_per_second - elapsed)

        self._last_request_time = time.time()
        text = self._fetch(url)
        if 'dump_dir' in self.config:
            self._dump(text, url)

        soup = BeautifulSoup(text, 'html.parser')
        for link in soup.find_all('a'):
            href = link.get('href')
            if href is not None:
                href = urllib.parse.urljoin(url, href)
            if href.startswith(self.config.base_url):
                queue.add(href)


def main(config, **params):
    base_dir = os.path.dirname(config)
    config = parse_config(config, params)

    with ScrapeQueue(base_dir, config.scrape) as queue:
        queue.add(config.root)

        parser = Parser(base_dir, config.parser_config)

        while queue:
            url = queue.pop()
            parser.parse(queue, url)


if __name__ == '__main__':
    Fire(main)