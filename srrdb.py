#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import requests

BASE_URL = "https://api.srrdb.com/v1/"
DOWNLOAD_URL = "https://www.srrdb.com/download/"

def make_request(endpoint, release_name):
    url = f"{BASE_URL}{endpoint}{release_name}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve from srrDB: {e}")
        return None

def srrdb_search(release_name):
    return make_request("search/r:", release_name)

def srrdb_details(release_name):
    return make_request("details/", release_name)

def srrdb_nfo(release_name):
    return make_request("nfo/", release_name)

def srrdb_imdb(release_name):
    return make_request("imdb/", release_name)

def download_file(url, destination_path):
    if os.path.exists(destination_path):
        print(f"Destination file {destination_path} already exists. Download skipped.")
        return False
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to download from srrDB: {e}")
        return False

    # srrDB answers missing files with an HTML page instead of an HTTP error
    content_type = response.headers.get('Content-Type', '')
    if 'text/html' in content_type or not response.content:
        print(f"File not available on srrDB: {url}")
        return False

    with open(destination_path, 'wb') as file:
        file.write(response.content)
    print(f"File downloaded from {url} to {destination_path}")
    return True

def srrdb_download_srr(release_name, destination_folder):
    url = f"{DOWNLOAD_URL}srr/{release_name}"
    return download_file(url, os.path.join(destination_folder, f"{release_name}.srr"))

def srrdb_download_nfo(release_name, destination_folder):
    nfo_result = srrdb_nfo(release_name)
    if not nfo_result or not nfo_result.get('nfolink'):
        print(f"No NFO found on srrDB for {release_name}")
        return False

    downloaded = False
    for link in nfo_result['nfolink']:
        filename = link.rsplit('/', 1)[-1]
        if download_file(link, os.path.join(destination_folder, filename)):
            downloaded = True
    return downloaded

def main():
    pass

if __name__ == "__main__":
    main()