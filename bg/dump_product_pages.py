import argparse
import os
import time
import requests
import yaml
from urllib.parse import urlparse
import concurrent.futures
import threading

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36'
}

class RateLimiter:
    def __init__(self, rate_limit):
        self.rate_limit = rate_limit
        self.lock = threading.Lock()
        self.last_request = 0

    def wait(self):
        with self.lock:
            current_time = time.time()
            elapsed_time = current_time - self.last_request
            sleep_time = max(1 / self.rate_limit - elapsed_time, 0)
            time.sleep(sleep_time)
            self.last_request = time.time()

def download_file(url, directory, rate_limiter, scraper_api_key=None):
    filename = os.path.split(urlparse(url).path)[-1]
    file_path = os.path.join(directory, filename)

    if scraper_api_key:
        url = f'http://api.scraperapi.com?api_key={scraper_api_key}&url={url}'

    rate_limiter.wait()
    response = requests.get(url, headers=HEADERS, allow_redirects=False)

    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(response.content)
        print(f'Successfully downloaded {url}')
        return True
    else:
        print(f'Failed to download {url}: {response.status_code} {response.reason}')
        return False

def process_url(url, directory, rate_limiter, scraper_api_key):
    if not download_file(url, directory, rate_limiter, scraper_api_key):
        return url
    return None

def process_url_wrapper(url, directory, rate_limiter, scraper_api_key, stop_event):
    try:
        if not stop_event.is_set():
            return process_url(url, directory, rate_limiter, scraper_api_key)
    except Exception as e:
        print(f'Exception while processing {url}: {e}')
        return None

def main():
    parser = argparse.ArgumentParser(description='Download files from a list of URLs.')
    parser.add_argument('--input_file', type=str, required=True, help='Input file with URLs.')
    parser.add_argument('--output_dir', type=str, required=True, help='Output directory for downloaded files.')
    parser.add_argument('--parallelism', type=int, default=1, help='Number of parallel downloads.')
    parser.add_argument('--scraper_api_key', type=str, help='ScraperAPI key for proxying requests.')
    parser.add_argument('--rate_limit', type=float, default=1, help='Number of requests per second.')
    parser.add_argument('--max-retries', type=int, default=3, help='Maximum number of retries per URL (default: 3)')
    parser.add_argument('--task-timeout', type=int, default=300, help='Timeout for tasks in seconds (default: 300)')

    args = parser.parse_args()

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    state_file = 'download_state.yaml'

    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            state = yaml.safe_load(f)
        remaining_urls = state['remaining_urls']
    else:
        with open(args.input_file, 'r') as f:
            urls = [line.strip() for line in f.readlines()]
        remaining_urls = urls

    rate_limiter = RateLimiter(args.rate_limit)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallelism) as executor:
        stop_event = threading.Event()
        url_attempts = {url: 0 for url in urls}
        max_retries = args.max_retries
        task_timeout = args.task_timeout
        try:
            while remaining_urls:
                future_to_url = {
                    executor.submit(process_url_wrapper, url, args.output_dir, rate_limiter, args.scraper_api_key,
                                    stop_event): url for url in remaining_urls}
                completed_urls = []

                for future in concurrent.futures.as_completed(future_to_url, timeout=task_timeout):
                    url = future_to_url[future]
                    result = future.result()
                    if result is not None:
                        completed_urls.append(result)
                    else:
                        url_attempts[url] += 1

                remaining_urls = [url for url in remaining_urls if
                                  url not in completed_urls and url_attempts[url] <= max_retries]
        except KeyboardInterrupt:
            print('\nTerminating remaining tasks...')
            stop_event.set()

        with open(state_file, 'w') as f:
            yaml.dump({'remaining_urls': remaining_urls}, f)

        print('State saved. You can resume later.')


if __name__ == '__main__':
    main()
