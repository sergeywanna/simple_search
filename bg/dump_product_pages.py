import argparse
import os
import queue
import random
import requests
import sys
import time
import threading
from urllib.parse import urlparse
import yaml


class Dispatcher:
    def __init__(self, objects, closure, num_retries, parallelism):
        self.objects = objects
        self.closure = closure
        self.num_retries = num_retries
        self.parallelism = parallelism
        self.task_queue = queue.Queue()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.threads = []

        # Prepare the task queue with the objects and their retry counts
        for obj in self.objects:
            self.task_queue.put((obj, 0))

    def _worker(self):
        while not self.stop_event.is_set():
            try:
                obj, retries = self.task_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                self.closure(obj)
            except Exception as e:
                print(f"Task failed: {e} (retry: {retries})")
                with self.lock:
                    if retries < self.num_retries:
                        self.task_queue.put((obj, retries + 1))
                    else:
                        print(f"Task failed after {self.num_retries} retries: {e}")
            finally:
                self.task_queue.task_done()

    def start(self):
        for _ in range(self.parallelism):
            t = threading.Thread(target=self._worker)
            t.start()
            self.threads.append(t)

    def stop(self):
        self.stop_event.set()

        for t in self.threads:
            t.join()

    def state(self):
        with self.lock:
            remaining_tasks = list(self.task_queue.queue)
        return remaining_tasks

    def join(self):
        for t in self.threads:
            t.join()

    def restore(self, state):
        with self.lock:
            self.task_queue = queue.Queue()

            for task in state:
                self.task_queue.put(task)

            self.threads = []


class Downloader:
    def __init__(self, save_directory, scrape_api_key=None):
        self.save_directory = save_directory
        self.scrape_api_key = scrape_api_key

        # Create the save directory if it does not exist
        os.makedirs(save_directory, exist_ok=True)

    def _download_url(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
        }

        if self.scrape_api_key:
            api_url = "http://api.scraperapi.com"
            params = {
                "api_key": self.scrape_api_key,
                "url": url,
            }
            response = requests.get(api_url, headers=headers, params=params, allow_redirects=False)
        else:
            response = requests.get(url, headers=headers, allow_redirects=False)

        if response.status_code != 200:
            raise Exception(f"Failed to download URL: {url} (status: {response.status_code})")

        return response.content

    def _save_file(self, content, filename):
        file_path = os.path.join(self.save_directory, filename)
        with open(file_path, "wb") as f:
            f.write(content)

    def _get_filename(self, url):
        parsed = urlparse(url)
        path_parts = parsed.path.strip("/").split("/")
        file_base = path_parts[-1].split("?")[0]
        return f"{file_base}.html"

    def run(self, url):
        print(f"Starting download of {url}")
        content = self._download_url(url)
        filename = self._get_filename(url)
        self._save_file(content, filename)
        print(f"Downloaded {url}")


def main():
    parser = argparse.ArgumentParser(description="Download URLs using Dispatcher and Downloader")
    parser.add_argument("--urls_file", required=True, help="Path to the file containing URLs to download (one URL per line)")
    parser.add_argument("--state_file", required=True, help="Path to the file containing the saved state of Dispatcher")
    parser.add_argument("--save_directory", required=True, help="Directory to save downloaded files")
    parser.add_argument("--scrape_api_key", default=None, help="ScrapeAPI key (optional)")
    parser.add_argument("--num_retries", type=int, default=3, help="Number of retries for each download task")
    parser.add_argument("--parallelism", type=int, default=5, help="Number of parallel download tasks")

    args = parser.parse_args()

    # Read URLs from the file
    with open(args.urls_file, "r") as f:
        urls = [line.strip() for line in f.readlines()]

    # Initialize Downloader and Dispatcher
    downloader = Downloader(args.save_directory, args.scrape_api_key)
    def mock_runner(url):
        # Random number of seconds between 1 and 3
        time.sleep(random.randint(1, 3))
        # with 0.2 probability, fail the task
        if random.random() < 0.2:
            print(f"Failed to download URL: {url}")
            raise Exception("Failed to download URL")
        else:
            print(f"Downloaded URL: {url}")


    dispatcher = Dispatcher(urls, downloader.run, args.num_retries, args.parallelism)
    # dispatcher = Dispatcher(urls, mock_runner, args.num_retries, args.parallelism)

    # Restore state if the state file exists
    if os.path.exists(args.state_file):
        print(f"Restoring Dispatcher state from {args.state_file}...")
        with open(args.state_file, "r") as f:
            state = yaml.safe_load(f)
        dispatcher.restore(state)

    try:
        dispatcher.start()
        dispatcher.join()
    except KeyboardInterrupt:
        print("Stopping Dispatcher...")
        dispatcher.stop()

        # Save the state to the disk as YAML
        state = dispatcher.state()
        with open(args.state_file, "w") as f:
            yaml.safe_dump(state, f)

        print("Dispatcher state saved.")
        sys.exit(0)


if __name__ == "__main__":
    main()
