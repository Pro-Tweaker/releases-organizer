#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import re
import shutil

from datetime import datetime

from srrdb import *
from tmdb import *

DEBUG = False
DRY_RUN = False

VALID_EXTENSIONS = [
    'avi',
    'mp4',
    'mkv',
    'mk3d'
]

VALID_EXTENSIONS_TO_MOVE = [
    'avi',
    'mp4',
    'mkv',
    'mk3d',
]

VALID_EXTENSIONS_TO_COPY = [
    'srt',
]

class Release:
    def __init__(self, name, is_folder, files=None):
        self.name = name
        self.is_folder = is_folder
        self.files = files

def separate(folder_path):
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        contents = os.listdir(folder_path)
        release_objects = []

        for item in contents:
            item_path = os.path.join(folder_path, item)
            is_folder = os.path.isdir(item_path)
            
            if is_folder:
                # If the item is a folder, list its contents
                subfolder_contents = [file for file in os.listdir(item_path) if file.endswith(tuple(VALID_EXTENSIONS_TO_MOVE)) or file.endswith(tuple(VALID_EXTENSIONS_TO_COPY))]

                if len(subfolder_contents) != 0:
                    release_objects.append(Release(item, is_folder, subfolder_contents))
            else:
                # Check if the file has a valid extension
                file_extension = item.split('.')[-1]
                if file_extension in VALID_EXTENSIONS:
                    release_objects.append(Release(item, is_folder))
                    if DEBUG:
                        print(item)

        return release_objects
    else:
        print("The specified folder does not exist.")
        return []

def extract_movie_info(release_name):
    # Regular expression pattern to match movie names and release dates
    #pattern = r'(.+?)\.(\d{4})\.' # only dot
    pattern = r'(.+?)[.\s](\d{4})[.\s]' # dot or space

    match = re.search(pattern, release_name)
    
    if match:
        movie_name = match.group(1).replace('.', ' ')
        release_date = match.group(2)
    else:
        # If no match is found, set default values
        movie_name = "Unknown Movie"
        release_date = "YearUnknown"

    return movie_name, release_date

def srrdb(release_name):
    search_result = srrdb_search(release_name)
    if search_result:
        results_count = search_result.get('resultsCount', 0)
        if results_count == 0:
            print("No results found.")
        elif results_count > 1:
            print(f"Multiple results found for {release_name}. Please choose which result to use:")

            for index, result in enumerate(search_result['results'], start=1):
                print(f"{index}. {result['title']}")

            while True:
                try:
                    user_choice = int(input("Enter the number of the result to use: "))
                    if 1 <= user_choice <= results_count:
                        selected_result = search_result['results'][user_choice - 1]
                        print(f"You selected: {selected_result['title']}")
                        break
                    else:
                        print("Invalid choice. Please enter a valid number.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

        imdb_result = srrdb_imdb(release_name)
        if imdb_result:
            return imdb_result
        else:
            return None

def extract_tmdb_info(release_name, tmdb_data):
    if tmdb_data is None:
        return None, None, None

    if 'total_results' in tmdb_data and tmdb_data['total_results'] > 0:
        if tmdb_data['total_results'] == 1:
            # If there's only one result, return it
            first_movie = tmdb_data['results'][0]
        else:
            print(f"Multiple results found for {release_name}. Please choose which result to use:")

            for i, movie in enumerate(tmdb_data['results']):
                print(f"{i + 1}. {movie['title']} ({movie['release_date']}) - https://www.themoviedb.org/movie/{movie['id']}")

            while True:
                try:
                    choice = int(input("Enter the number of the entry you want: "))
                    if 1 <= choice <= tmdb_data['total_results']:
                        first_movie = tmdb_data['results'][choice - 1]
                        break
                    else:
                        print("Invalid choice. Please enter a valid number.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

        movie_id = first_movie['id']
        title = first_movie['title']
        release_date = first_movie['release_date']
        return movie_id, title, release_date
    else:
        return None, None, None

def rename_release_with_ssrdb(release_name, imdb_data):
    # Extract movie name and release date from the IMDb data
    if 'releases' in imdb_data and imdb_data['releases']:
        movie_name = imdb_data['releases'][0]['title']
        imdb_id = imdb_data['releases'][0]['imdb']
    else:
        return release_name  # If IMDb data is not available, keep the original name

    # Extract the year (date) from the release name if available
    date_match = re.search(r'\d{4}', release_name)
    release_date = date_match.group() if date_match else "YearUnknown"

    # Generate the new release name format
    new_release_name = f"{movie_name} ({release_date}) [imdbid-tt{imdb_id}]"

    return new_release_name

def rename_release_with_tmdb(movie_id, movie_name, release_date):
    try:
        # Parse the release_date string using a specified format
        release_date = datetime.strptime(release_date, "%Y-%m-%d")

        # Extract the year as a string
        year = str(release_date.year)

        return f"{movie_name} ({year}) [tmdbid-{movie_id}]"
    except ValueError:
        return None

def sanitize_for_windows(input_string):
    # Define a regex pattern to match characters not allowed in Windows filenames
    invalid_chars_regex = r'[\/:*?"<>|]'

    # Replace invalid characters with nothing
    sanitized_string = re.sub(invalid_chars_regex, '', input_string)

    # Remove trailing periods and spaces (Windows does not allow these at the end of folder names)
    sanitized_string = sanitized_string.rstrip(' .')

    # Ensure the string is not empty after sanitization
    if not sanitized_string:
        sanitized_string = '_'

    return sanitized_string

def arguments():
    parser = argparse.ArgumentParser(
                    prog='Movie Release Renamer',
                    description='',
                    epilog='')

    parser.add_argument('folder', nargs='?', default='.')
    parser.add_argument('output', nargs='?', default='output')
    parser.add_argument('-s', '--source', choices=['tmdb', 'srrdb'], default='tmdb')
    parser.add_argument('-de', '--delete-empty', help='Delete empty folders after move', action='store_true', default=False)
    parser.add_argument('-ds', '--srr', help='Download SRR file from ssrDB', action='store_true', default=False)
    parser.add_argument('-dn', '--nfo', help='Download NFO file from ssrDB', action='store_true', default=False)
    parser.add_argument('-d', '--debug', help='Enable debug output', action='store_true', default=False)
    parser.add_argument('-dy', '--dry-run', help='Do not make the moves', action='store_true', default=False)

    return parser.parse_args()

def main():
    args = arguments()

    folder = args.folder
    output = args.output
    source = args.source
    delete_empty = args.delete_empty

    DEBUG = args.debug
    DRY_RUN = args.dry_run

    results = separate(folder)

    for release in results:

        if(release.is_folder):
            release_name = release.name

            if DEBUG:
                print(f"Name: {release.name}")
                print(f"Is Folder: {release.is_folder}")
                if release.is_folder:
                    print(f"Contents: {', '.join(release.files)}")
                print()
        else:
            release_name, _ = os.path.splitext(release.name)

        movie_name, release_date = extract_movie_info(release_name)
        
        if DEBUG:
            print(f"Release Name: {release_name}")
            print(f"Movie Name: {movie_name}")
            print(f"Release Date: {release_date}")

        # Check if file or folder is tv season or episodes
        #tv_pattern = r'\.S\d{2}\.' # dot only
        tv_pattern = r'[.\s]S\d{2}[.\s]' # dot or space
        tv_matches = re.findall(tv_pattern, release.name)
        if tv_matches:
            if DEBUG:
                print("The file or folder contains the pattern:", tv_matches)
                print()
            continue
        
        if source == "srrdb":
            result = srrdb(release_name)
            renamed_release = rename_release_with_ssrdb(release_name, result)
        elif source == "tmdb":
            tmdb_data = tmdb_search(movie_name, release_date)
            tmdb_id, tmdb_title, tmdb_release_date = extract_tmdb_info(release_name, tmdb_data)

            if tmdb_id:
                if DEBUG:
                    print("TMDb Movie Info:")
                    print(f"ID: {tmdb_id}")
                    print(f"Title: {tmdb_title}")
                    print(f"Release Date: {tmdb_release_date}")
                renamed_release = rename_release_with_tmdb(tmdb_id, tmdb_title, tmdb_release_date)
                
            else:
                continue

        print(f"Renamed Release: {renamed_release}")

        if DRY_RUN:
            print(f"Dry run enabled, not moving the files")
        else:
            path = os.path.join(output, renamed_release)
            path = sanitize_for_windows(path)

            if not os.path.exists(path):
                os.makedirs(path)

            if release.is_folder:
                # Iterate through files in the source folder
                for file in release.files:
                    if any(file.endswith(ext) for ext in VALID_EXTENSIONS_TO_COPY):
                        shutil.copy(os.path.join(folder, release.name, file), path)
                    elif any(file.endswith(ext) for ext in VALID_EXTENSIONS_TO_MOVE):
                        shutil.move(os.path.join(folder, release.name, file), path)

                # Check if the source folder is empty and delete it
                if delete_empty:
                    if not os.listdir(os.path.join(folder, release.name)):
                        os.rmdir(os.path.join(folder, release.name))
            else:
                shutil.move(os.path.join(folder, release.name), path)

        print("")

if __name__ == "__main__":
    main()