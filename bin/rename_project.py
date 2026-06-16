"""
rename_project.py

This script automates the renaming process of a Flask template repository.
It replaces all instances of a placeholder project name (like 'application')
in filenames, directory names, and file contents with a new project name provided
by the developer, **excluding** Markdown documentation files (.md). This is useful when
starting a new project from a template, as it saves time and ensures consistency
throughout the project, while keeping documentation unchanged.

How to Use:
1. Clone or copy the Flask template repository.
2. Run the script in a terminal using the following syntax:

   python rename_project.py <root_directory> <old_name> <new_name>
"""

import os
import sys


def replace_in_file(file_path, old_text, new_text):
    # Skip .md files
    if file_path.endswith(".md"):
        print(f"Skipping documentation file: {file_path}")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        new_content = content.replace(old_text, new_text)

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(new_content)

        print(f"Replaced content in file: {file_path}")
    except UnicodeDecodeError:
        print(f"Skipping non-UTF-8 file: {file_path}")
        return


def rename_files_and_directories(root_dir, old_name, new_name):
    # Traverse through the directory bottom-up to avoid skipping renamed directories
    for root, dirs, files in os.walk(root_dir, topdown=False):
        # Rename files
        for file_name in files:
            file_path = os.path.join(root, file_name)

            # Skip .md files for renaming
            if file_name.endswith(".md"):
                print(f"Skipping renaming for documentation file: {file_path}")
                continue

            if old_name in file_name:
                new_file_name = file_name.replace(old_name, new_name)
                new_file_path = os.path.join(root, new_file_name)
                os.rename(file_path, new_file_path)
                print(f"Renamed file: {file_path} -> {new_file_path}")
            else:
                new_file_path = file_path

            # Replace placeholder text inside the file (skipping .md files)
            replace_in_file(new_file_path, old_name, new_name)

        # Rename directories
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            new_dir_name = dir_name.replace(old_name, new_name)
            new_dir_path = os.path.join(root, new_dir_name)

            # Check if destination directory exists
            if not os.path.exists(new_dir_path):
                os.rename(dir_path, new_dir_path)
                print(f"Renamed directory: {dir_path} -> {new_dir_path}")
            else:
                print(f"Skipping renaming, directory already exists: {new_dir_path}")


def main():
    if len(sys.argv) != 4:
        print("Usage: python rename_project.py <root_directory> <old_name> <new_name>")
        sys.exit(1)

    root_directory = sys.argv[1]
    old_name = sys.argv[2]
    new_name = sys.argv[3]

    print(
        f"Starting renaming process from '{old_name}' to '{new_name}' in directory: {root_directory}"
    )
    rename_files_and_directories(root_directory, old_name, new_name)
    print("Project renaming completed!")


if __name__ == "__main__":
    main()
