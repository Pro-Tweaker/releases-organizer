#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time

import requests

# Provide your key via the TMDB_API_KEY environment variable.
API_KEY = os.environ.get('TMDB_API_KEY', 'YOUR_TMDB_API_KEY')

REQUEST_TIMEOUT = 10    # seconds
MAX_RETRIES = 5         # retry attempts after the first try
RETRY_BACKOFF_BASE = 1  # seconds, doubles each attempt
RETRY_BACKOFF_MAX = 30  # cap on computed/Retry-After backoff

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

def _default_retry_logger(message):
    print(f"  [tmdb] {message}", file=sys.stderr)

_retry_logger = _default_retry_logger

def set_retry_logger(logger):
    # Lets a caller (e.g. organizer.py's --verify-library-online progress bar) reroute retry
    # warnings so they don't collide with its own stdout output. Pass None to restore the default.
    global _retry_logger
    _retry_logger = logger or _default_retry_logger

def _retry_delay(response, attempt):
    if response is not None and response.status_code == 429:
        retry_after = response.headers.get('Retry-After')
        if retry_after is not None:
            try:
                return min(float(retry_after), RETRY_BACKOFF_MAX)
            except ValueError:
                pass
    return min(RETRY_BACKOFF_BASE * (2 ** attempt), RETRY_BACKOFF_MAX)

def _request_with_retry(url):
    # Retries transient failures (network errors/timeouts, 429 rate-limiting, 5xx) with
    # backoff, honoring TMDB's Retry-After header on 429, so a single blip doesn't fail out
    # of a long --verify-library-online run. Returns the final requests.Response, or None if
    # every attempt raised a network error. A hard failure (404, or a non-retryable 4xx like
    # a bad API key) returns immediately - the caller distinguishes those from "couldn't check".
    response = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            response = None
            reason = f'network error: {e}'
        else:
            if response.status_code != 429 and response.status_code < 500:
                return response
            reason = f'HTTP {response.status_code}'

        if attempt == MAX_RETRIES:
            break
        delay = _retry_delay(response, attempt)
        _retry_logger(f"{reason}, retrying in {delay:.0f}s (attempt {attempt + 1}/{MAX_RETRIES})...")
        time.sleep(delay)
    return response

def _tmdb_get_json(url):
    response = _request_with_retry(url)
    if response is not None and response.status_code == 200:
        return response.json()
    return None

def tmdb_search(movie_name, release_year):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_name}&year={release_year}'
    data = _tmdb_get_json(url)
    return _filter_by_year(data, release_year, 'release_date')

def tmdb_tv_search(series_name, first_air_year=None):
    url = f'https://api.themoviedb.org/3/search/tv?api_key={API_KEY}&query={series_name}'
    if first_air_year:
        url += f'&first_air_date_year={first_air_year}'
    data = _tmdb_get_json(url)
    return _filter_by_year(data, first_air_year, 'first_air_date')

def tmdb_collection_search(tmdb_id, language=None):
    url = f'https://api.themoviedb.org/3/movie/{tmdb_id}?api_key={API_KEY}'
    if language:
        url += f'&language={language}'
    return _tmdb_get_json(url)

def _tmdb_get_by_id(url):
    # Shared by the --verify-library-online lookups below: dict on 200, False on 404 (id
    # confirmed gone), None for anything else (network error, timeout, bad key, or retries
    # exhausted) so callers can tell "deleted" apart from "couldn't check".
    response = _request_with_retry(url)
    if response is None:
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