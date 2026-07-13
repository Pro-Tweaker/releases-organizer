#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import requests

# Provide your key via the TMDB_API_KEY environment variable.
API_KEY = os.environ.get('TMDB_API_KEY', 'YOUR_TMDB_API_KEY')

def tmdb_search(movie_name, release_year):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_name}&year={release_year}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        return None

def tmdb_tv_search(series_name, first_air_year=None):
    url = f'https://api.themoviedb.org/3/search/tv?api_key={API_KEY}&query={series_name}'
    if first_air_year:
        url += f'&first_air_date_year={first_air_year}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        return None

def tmdb_collection_search(tmdb_id):
    url = f'https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={API_KEY}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        return data
    else:
        return None

def _tmdb_get_by_id(url):
    # Shared by the --verify-library-online lookups below: dict on 200, False on 404 (id
    # confirmed gone), None for anything else (network error, timeout, bad key) so callers can
    # tell "deleted" apart from "couldn't check".
    try:
        response = requests.get(url, timeout=10)
    except requests.RequestException:
        return None

    if response.status_code == 200:
        return response.json()
    if response.status_code == 404:
        return False
    return None

def tmdb_get_movie_by_id(movie_id):
    return _tmdb_get_by_id(f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={API_KEY}')

def tmdb_get_tv_by_id(tv_id):
    return _tmdb_get_by_id(f'https://api.themoviedb.org/3/tv/{tv_id}?api_key={API_KEY}')

def tmdb_get_collection_by_id(collection_id):
    return _tmdb_get_by_id(f'https://api.themoviedb.org/3/collection/{collection_id}?api_key={API_KEY}')