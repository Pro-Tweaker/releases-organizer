#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import requests

# Provide your key via the TMDB_API_KEY environment variable.
API_KEY = os.environ.get('TMDB_API_KEY', 'YOUR_TMDB_API_KEY')

# TMDB's `year` / `first_air_date_year` search params are a soft hint (they also match
# alternate/regional release dates), so a search can return a result whose actual year is
# nowhere near what was asked for. Allow a small drift for legitimate festival/regional
# release date gaps, but no more.
YEAR_MATCH_TOLERANCE = 1

def _filter_by_year(data, expected_year, date_field):
    # Re-check locally against the date field already present on every search result - no
    # extra API calls - before the caller counts total_results/results.
    if data is None or not expected_year:
        return data
    try:
        expected = int(expected_year)
    except (TypeError, ValueError):
        return data

    def year_ok(item):
        date = item.get(date_field)
        if not date or len(date) < 4:
            return False
        try:
            return abs(int(date[:4]) - expected) <= YEAR_MATCH_TOLERANCE
        except ValueError:
            return False

    filtered = [r for r in data.get('results', []) if year_ok(r)]
    data = dict(data)
    data['results'] = filtered
    data['total_results'] = len(filtered)
    return data

def tmdb_search(movie_name, release_year):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_name}&year={release_year}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        return _filter_by_year(data, release_year, 'release_date')
    else:
        return None

def tmdb_tv_search(series_name, first_air_year=None):
    url = f'https://api.themoviedb.org/3/search/tv?api_key={API_KEY}&query={series_name}'
    if first_air_year:
        url += f'&first_air_date_year={first_air_year}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        return _filter_by_year(data, first_air_year, 'first_air_date')
    else:
        return None

def tmdb_collection_search(tmdb_id, language=None):
    url = f'https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={API_KEY}'
    if language:
        url += f'&language={language}'
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

def tmdb_get_collection_by_id(collection_id, language=None):
    url = f'https://api.themoviedb.org/3/collection/{collection_id}?api_key={API_KEY}'
    if language:
        url += f'&language={language}'
    return _tmdb_get_by_id(url)