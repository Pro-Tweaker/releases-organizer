#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests

BASE_URL = "https://api.srrdb.com/v1/"

def make_request(endpoint, release_name):
    url = f"{BASE_URL}{endpoint}{release_name}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve from ssrDB: {e}")
        return None

def srrdb_search(release_name):
    return make_request("search/r:", release_name)

def srrdb_details(release_name):
    return make_request("details/", release_name)

def srrdb_nfo(release_name):
    return make_request("nfo/", release_name)

def srrdb_imdb(release_name):
    return make_request("imdb/", release_name)

def main():
    pass

if __name__ == "__main__":
    main()