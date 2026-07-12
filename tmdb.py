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