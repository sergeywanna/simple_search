import hashlib
import os
import time
import urllib
from collections import deque

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
        self._queue = deque()

    def add(self, url):
        hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        if hash not in self._state.hash_set:
            self._queue.append(url)
            print("  " + url)
            self._state.hash_set.add(hash)
            self._added_count += 1
        else:
            print("  " + url + " (skipped)")

    def pop(self):
        self._processed_count += 1
        return self._queue.popleft()

    @property
    def _added_count(self):
        return self._state.get('added_count', 0)

    @_added_count.setter
    def _added_count(self, value):
        self._state.added_count = value

    @property
    def _processed_count(self):
        return self._state.get('processed_count', 0)

    @_processed_count.setter
    def _processed_count(self, value):
        self._state.processed_count = value

    def __bool__(self):
        return bool(self._queue) and self._processed_count < self._config.max_pages

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

        if 'hash_set' not in self._state:
            self._state.hash_set = set()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._state_fname:
            with open(self._state_fname, 'w') as f:
                yaml.dump(dict(self._state), f)



class Parser:
    def __init__(self, config):
        self.config = config
        self._last_request_time = None

    def parse(self, queue, url):
        print(f"Processing {url}")
        # Check if we need to throttle next request.
        if self._last_request_time and 'throttle_per_second' in self.config:
            elapsed = time.time() - self._last_request_time
            if elapsed < 1 / self.config.throttle_per_second:
                time.sleep(1 / self.config.throttle_per_second - elapsed)

        self._last_request_time = time.time()
        response = requests.get(url, headers=self.config.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for link in soup.find_all('a'):
            href = link.get('href')
            if href is not None:
                href = urllib.parse.urljoin(url, href)
            if href.startswith(self.config.base_url):
                queue.add(href)


def main(config, **params):
    config_file = config
    config = parse_config(config, params)

    with ScrapeQueue(os.path.dirname(config_file), config.scrape) as queue:
        queue.add(config.root)

        parser = Parser(config.parser_config)

        while queue:
            url = queue.pop()
            parser.parse(queue, url)


if __name__ == '__main__':
    Fire(main)