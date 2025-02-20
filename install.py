'''
This installer script attempts to simplify the steps involved with
using and developing FireFox/Floorp themes with Sidebery.

It has the following advantages:
* Single location config values (templating CSS files with Jinja2).
* Automatic cross-platform profile folder detection.
* Automatic installation of user chrome mods.
* Automatic installation of Sidebery styles.
'''

import os
import sys
from shutil import (
    copy,
    copytree,
    ignore_patterns,
    rmtree,
    unpack_archive,
    make_archive)
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup

# Sidebery constants
SIDEBERY_EXTENSION_ID = '3c078156-979c-498b-8990-85f7987dd929'
SIDEBERY_EXTENSION_FILENAME = f"{{{SIDEBERY_EXTENSION_ID}}}.xpi"
SIDEBERY_CUSTOM_THEME_REL_DIR = 'themes/floorpier'

# Theme source path
THEME_SOURCE_DIR = 'src'

# Build paths
BUILD_DIR = 'build'
PROFILE_BUILD_DIR = f"{BUILD_DIR}/profile"
EXTENSIONS_BUILD_DIR = f"{BUILD_DIR}/extensions"
SIDEBERY_THEME_BUILD_DIR = f"{BUILD_DIR}/sidebery"

def _get_profile_dir() -> str:
    match sys.platform:
        # TODO: Confirm default Linux profile path matches MacOS
        case 'darwin' | 'linux':
            base_dir = f"{Path.home()}/Library/Application Support/Floorp/Profiles"
        # TODO: Check and add Windows profile path
        case 'win32':
            raise NotImplementedError('Windows is not a supported platform by the installer')
        case _:
            raise NotImplementedError(
                "The current platform ('{sys.platform}') is not supported by the installer")
    # TODO: Should safety check both the base and default-release DIRs exist
    return next(Path(base_dir).rglob('*.default-release'))

def _prepare_files():
    # Create the build directory if it doesn't exist
    os.makedirs(BUILD_DIR, exist_ok=True)

    # Copy all non-template files
    copytree(THEME_SOURCE_DIR, BUILD_DIR, ignore=ignore_patterns('*.jinja'), dirs_exist_ok=True)

    # Configure Jinja2 environment with the template directory
    env = Environment(loader=FileSystemLoader(THEME_SOURCE_DIR))
    for root, _, files in os.walk(THEME_SOURCE_DIR):
        for file in files:
            # Check if the file needs templating
            if file.endswith('.jinja'):
                # Get relative path from THEME_SOURCE_DIR to current directory
                rel_path = os.path.relpath(root, THEME_SOURCE_DIR)

                # Construct output subdirectory path
                output_subdir = os.path.join(BUILD_DIR, rel_path)
                os.makedirs(output_subdir, exist_ok=True)  # Ensure subdir exists

                # Get the base name without .jinja extension
                base_name = os.path.splitext(file)[0]

                # Render the template
                template = env.get_template(os.path.join(rel_path, file))
                rendered_content = template.render()

                # Write the output file
                output_file = os.path.join(output_subdir, base_name)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(rendered_content)

# TODO: Consider auto-backing up the existing profile
def _install_user_chrome(profile_dir: str):
    user_input = input(
        f"You are about to copy the contents of '{PROFILE_BUILD_DIR}' into '{profile_dir}', continue? (y/n): ")
    if user_input.lower() == 'y':
        copytree(PROFILE_BUILD_DIR, profile_dir, dirs_exist_ok=True)

# As Sidebery doesn't support automatically (without user input) installing styles/themes,
# this method unfortunately modifies the extension directly.
def _update_sidebery(profile_dir: str):
    sidebery_src_path = os.path.join(profile_dir, f"extensions/{SIDEBERY_EXTENSION_FILENAME}")
    os.makedirs(EXTENSIONS_BUILD_DIR, exist_ok=True)

    # TODO: Validate Sidebery exists
    user_input = input('You are about to modify Sidebery with a custom style, continue? (y/n): ')
    if user_input.lower() == 'y':
        sidebery_build_dir = _unpack_sidebery(sidebery_src_path)
        _update_sidebery_themes(sidebery_build_dir)
        sidebery_repack_path = _repack_sidebery(sidebery_build_dir)
        # Copy the modified pack back into the user profile
        copy(sidebery_repack_path, sidebery_src_path)

def _unpack_sidebery(sidebery_src_path: str) -> str:
    sidebery_archive_dest_path = os.path.join(EXTENSIONS_BUILD_DIR, SIDEBERY_EXTENSION_FILENAME)
    copy(sidebery_src_path, sidebery_archive_dest_path)

    # Unpack/unzip Sidebery
    sidebery_dest_path = os.path.join(EXTENSIONS_BUILD_DIR, SIDEBERY_EXTENSION_ID)
    unpack_archive(sidebery_archive_dest_path, sidebery_dest_path, format='zip')
    return sidebery_dest_path

def _update_sidebery_themes(sidebery_build_dir: str):
    # Add our custom theme directory and CSS files to Sidebery
    sidebery_custom_theme_dir = os.path.join(sidebery_build_dir, SIDEBERY_CUSTOM_THEME_REL_DIR)
    os.makedirs(sidebery_custom_theme_dir, exist_ok=True)
    copytree(SIDEBERY_THEME_BUILD_DIR, sidebery_custom_theme_dir, dirs_exist_ok=True)

    # TODO: Remove hardcoded components with available themes
    for component in ['sidebar']:
        # Modify the corresponding HTML to include the corresponding custom stylesheet
        html_path = os.path.join(sidebery_build_dir, f"{component}/{component}.html")
        with open(html_path, 'r+', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            css_link_tag = soup.new_tag('link',
                                        rel='stylesheet',
                                        type='text/css',
                                        href=f"../{SIDEBERY_CUSTOM_THEME_REL_DIR}/{component}.css",
                                        id='theme_link')
            soup.head.append(css_link_tag)

            # Overwrite the file with our modified version
            f.seek(0)
            f.write(soup.prettify())
            f.truncate()

def _repack_sidebery(sidebery_build_dir: str) -> str:
    return make_archive(
        base_name=os.path.join(EXTENSIONS_BUILD_DIR, SIDEBERY_EXTENSION_FILENAME),
        root_dir=sidebery_build_dir,
        format='zip')

if __name__ == "__main__":
    # Make sure previous builds are removed before continuing
    rmtree(BUILD_DIR)
    _prepare_files()
    _profile_dir = _get_profile_dir()
    _install_user_chrome(_profile_dir)
    _update_sidebery(_profile_dir)
