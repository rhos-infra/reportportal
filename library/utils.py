#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2023, RedHat
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>.

import os
import requests
import subprocess

from datetime import datetime
from exceptions import *
from lxml import etree

def get_json(url, is_verified):
    """
    Fetches JSON data from a specified URL.

    Args:
        url (str): The URL to fetch JSON data from.
        is_verified (bool): Indicates whether certificate is validated

    Raises:
        ConnectionError: ConnectionError if the HTTP response status code is not 200 (OK).

    Returns:
        dict: A dictionary containing the JSON data from the response.
    """    
    response = requests.get(url, verify=is_verified)
    if response.status_code != 200:
        raise ConnectionError(response)
    return response.json()

def convert_date_to_sec(date_string, date_format):
    """
    Converts a date string into seconds since the Unix epoch.

    This function takes a date string and its corresponding format
    and converts it into the number of seconds that have elapsed since
    the Unix epoch (January 1, 1970).

    Example usage:
        convert_date_to_sec("2023-08-06T13:20:14", "%Y-%m-%dT%H:%M:%S")

    Args:
        date_string (str): A string representing the date to be converted.
        date_format (str): The format of the date string, following Python's
                           strftime conventions.

    Returns:
        str: A string containing the number of seconds since the Unix epoch.
    """ 
    # Parse the string into a datetime object
    dt_object = datetime.strptime(date_string, date_format)

    # Calculate the seconds since the Unix epoch
    seconds = int((dt_object - datetime(1970, 1, 1)).total_seconds())

    return str(seconds)


def create_folders_on(file_path):
    """
    Ensure directory structure exists for the given file path.

    This function ensures that the directory structure leading to the specified
    file path exists. If the directories do not exist, they will be created.

    Args:
        file_path (str): The path to the file for which directory structure needs
                         to be created.
    """
    # Extract the directory path from the given file path
    directory = os.path.dirname(file_path)

    # Create the directory path if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_to_file(xml_doc, xml_path):
    """
    Save XML document in a form of ElementTree object to a file.

    The function also ensures that the directory structure leading to the file
    path exists and creates the necessary directories if they don't exist.

    Args:
        xml_doc (ElementTree): An XML doc to be saved to the file.
        xml_path (str): The path to the XML file where the suite should be saved.

    Returns:
        str: The path to the saved XML file.
    """
    # Ensure the directory structure exists for the XML file
    create_folders_on(xml_path)

    # Write the XML suite to the specified file path
    with open(xml_path, 'wb') as xml_file:
        xml_file.write(etree.tostring(xmp_doc, pretty_print=True))

    # Return the path to the saved XML file
    return xml_path

def has_extension(file_name, extension):
    """
    Check if a file name has a specific extension.

    Args:
      file_name (str): The name of the file to check for the extension.
      extension (str): The target extension to compare against.

    Returns:
      bool: True if the file name has the specified extension, False otherwise.
    """
    return file_name.endswith(extension)

def replace_extension(filename, old_extension, new_extension):
    """
    Replace the extension of a filename if it matches the old extension.

    Args:
        filename (str): The original filename with the current extension.
        old_extension (str): The extension to be replaced (if present).
        new_extension (str): The new extension to replace the old extension.

    Returns:
        str or None: The modified filename with the new extension, or None
                     if the old extension does not match the current extension
    """ 
    base_name, ext = os.path.splitext(filename)

    if ext == old_extension:
        new_filename = f"{base_name}{new_extension}"
        return new_filename

    return None

def subunit_to_xml(subunit_file_path, xml_file_path):
    """
    Converts a subunit file to XML format using subunit2junitxml tool.

    Args:
        subunit_file_path (str): subunit_file_path Path to the input subunit file.
        xml_file_path (str): Path to the output XML file.
    """    
    create_folders_on(xml_file_path)

    command = f'subunit2junitxml < {subunit_file_path} > {xml_file_path}'

    completed_process = subprocess.run(command, shell=True, text=True, capture_output=True)

    if completed_process.returncode == 0:
        print("Conversion successful\n" + completed_process.stdout)
    else:
        print("Error: Conversion failed\n" + completed_process.stderr)