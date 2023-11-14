#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests

API_KEY = '95f5ff682dfaf167ba787a0aa7c82cfb'#'YOUR_TMDB_API_KEY'

def tmdb_search(movie_name, release_year):
    url = f'https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={movie_name}&year={release_year}'
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