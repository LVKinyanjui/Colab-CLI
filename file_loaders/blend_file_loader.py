#!/usr/bin/env python3

import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor

root = sys.argv[1] if len(sys.argv) > 1 else "https://download.blender.org/demo/"
seen = set()
files = set()

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)

def crawl(url):
    if url in seen:
        return
    seen.add(url)

    try:
        parser = Links()
        parser.feed(urlopen(url).read().decode(errors="ignore"))

        for href in parser.links:
            full = urljoin(url, href)

            if not full.startswith(root):
                continue

            if urlparse(full).path.lower().endswith(".blend"):
                files.add(full)
            elif href.endswith("/"):
                crawl(full)
    except Exception:
        pass

crawl(root)

Path("blend_urls.txt").write_text("\n".join(sorted(files)) + "\n")

def download(url):
    path = Path(urlparse(url).path).name

    if path and Path(path).exists():
        print(f"skip  {path}")
        return

    try:
        with urlopen(url) as r, open(path, "wb") as f:
            f.write(r.read())
        print(f"done  {path}")
    except Exception as e:
        print(f"fail  {url}: {e}")

with ThreadPoolExecutor(max_workers=8) as pool:
    list(pool.map(download, sorted(files)))

