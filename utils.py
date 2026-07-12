import os
import shutil

def copy_file(source_path, destination_path):
    if os.path.exists(destination_path):
        print(f"Destination file {destination_path} already exists. Copy operation skipped.")
        return
    try:
        shutil.copy(source_path, destination_path)
        print(f"File copied from {source_path} to {destination_path}")
    except (shutil.Error, OSError) as e:
        print(f"Error while copying file: {e}")

def move_file(source_path, destination_path):
    if os.path.exists(destination_path):
        print(f"Destination file {destination_path} already exists. Move operation skipped.")
        return
    try:
        shutil.move(source_path, destination_path)
        print(f"File moved from {source_path} to {destination_path}")
    except (shutil.Error, OSError) as e:
        print(f"Error while moving file: {e}")