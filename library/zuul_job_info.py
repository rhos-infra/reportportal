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

import gzip
import json
import junitxml
import os
import requests
import urllib.request
import subprocess
import subunit
import sys
import xml.etree.ElementTree as ET

from ansible.module_utils.basic import AnsibleModule
from lxml import etree
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from urllib.error import HTTPError

DOCUMENTATION = '''
module: zuul_job_info
version_added: '2.9'
short_description: Get Zuul job details
description:
    - This module generates XUnit file based on the Zuul job
      information (duration, start time) and extracts tempest
      test results to the specified destinaion. 
      Job details are collected from the Zuul server
      using pipeline REST API.
options:
    zuul_domain:
        description: URL of the Zuul server
        required: True
        type: str 
    zuul_tenant:
        description: Zuul tenant
        required: True
        type: str    
    zuul_job_build_id:
        description: ID of the job build
        required: True
        type: str
    zuul_fetch_test_results:
        description: determines whether test result xmls are fetched for zuul_job_build_id
                     or expected to be located in xml_folder.  
        required: True
        type: bool
    xml_folder:
        description: Folder with XML files (deploment.xml and test result xmls)
        required: True
        type: str

requirements:
    - "gzip"
    - "json"
    - "junitxml"
    - "lxml"
    - "os"
    - "requests"
    - "urllib"
    - "subprocess"
    - "subunit"
    - "xml"

    
'''

RETURN = '''
file_path:
    description: Path of the saved XML files
    type: string
    returned: always
'''

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class ConnectionError(Exception):
    def __init__(self, response):
        msg = f'HTTP{response.status_code}: {response.text}'
        super().__init__(msg)


def get_json(url):
    response = requests.get(url, verify=False)
    if response.status_code != 200:
        raise ConnectionError(response)
    return response.json()

def create_test_suite(base_url):
    response = get_json(f'{base_url}')

    suite = etree.Element('testsuite')
    suite.set('name', 'deployment')
    suite.set('time', str(response.get('duration', 0)))
    suite.set('timestamp', str(response.get('start_time', 0)))
    suite.set('result', str(response.get('result', 0)))

    return suite


def has_extension(file_name, extension):
    return file_name.endswith(extension)

def replace_extension(filename, old_extension, new_extension):
    base_name, ext = os.path.splitext(filename)

    if ext == old_extension:
        new_filename = f"{base_name}{new_extension}"
        return new_filename

    return None  # Return None if the extension doesn't match

def get_test_results(zuul_api_url, destination_folder):
    try:
        base_url = urllib.request.urlopen(zuul_api_url).read()
        base_json = json.loads(base_url)
        manifest_url = [x['url'] for x in base_json['artifacts'] if x.get('metadata', {}).get('type') == 'zuul_manifest'][0]
        manifest = urllib.request.urlopen(manifest_url)
        if manifest.info().get('Content-Encoding') == 'gzip':
            manifest_json = json.loads(gzip.decompress(manifest.read()))
        else:
            manifest_json = json.loads(manifest.read())
    except HTTPError as e:
        if e.code == 404:
            print(
                "Could not find build UUID in Zuul API. This can happen with "
                "buildsets still running, or aborted ones. Try again after the "
                "buildset is reported back to Zuul.", file=sys.stderr)
        else:
            print(e, file=sys.stderr)
        sys.exit(2)

    def get_file_name_from(node, parent):
        if (node.get('mimetype') != 'application/directory') and \
           (".xml" in node['name']  or ".subunit" in node['name']) :
            return(parent+node['name'])
        if node.get('children'):
            for child in node.get('children'):
                    get_file_name_from(child, parent+node['name']+'/')

    # get all xml or subunit file names
    file_name_list = []
    for node in manifest_json['tree']:
        result = get_file_name_from(node, '')
        if result is not None:
            file_name_list.append(result)
    print(file_name_list)
    
    test_result_files_xml = 0
    test_result_files_subunit = 0
    for file_name in file_name_list:
        file_url = base_json['log_url'] + file_name
        try:
            response = requests.get(file_url)     
            response.raise_for_status()  # Raise an exception for HTTP errors

            if has_extension(file_name, ".xml"): #save as it is in the destination_folder
                destination_path = destination_folder + new_filename
                create_folders_on(destination_path)
                with open(destination_path, 'wb') as f:
                    f.write(response.content)
                test_result_files_xml += 1 
            else: # has ".subunit" extension
                file_tmp_location = "/tmp/" + file_name
                with open(file_tmp_location, 'wb') as f:
                    f.write(response.content)                
                #  if needed, convert and save as xml in xml_folder
                new_filename = replace_extension(file_name,".subunit", ".xml")
                subunit_to_xml(file_tmp_location, destination_folder + new_filename)
                test_result_files_subunit += 1
        except requests.exceptions.RequestException as e:
            print(f"Error downloading: \n{e} \n{file_url}")
   
    print("Total test result files feetched: " + \
        str(test_result_files_subunit + test_result_files_xml))    
    print("Number of xml test result files feetched: " + \
        str(test_result_files_xml))
    print("Number of subunit test result files feetched (and converted to xml): " + \
        str(test_result_files_subunit))
    
def create_folders_on(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory) 

def subunit_to_xml(subunit_file_path, xml_file_path):
    create_folders_on(xml_file_path)

    command = f'subunit2junitxml < {subunit_file_path} > {xml_file_path}'

    completed_process = subprocess.run(command, shell=True, text=True, capture_output=True)

    if completed_process.returncode == 0:
        print("Conversion successful\n" + completed_process.stdout)
    else:
        print("Error: Conversion failed\n" + completed_process.stderr)

    
def save_to_file(suite, xml_path):
    create_folders_on(xml_path)
    
    with open(xml_path, 'wb') as xml_file:
        xml_file.write(etree.tostring(suite, pretty_print=True))
    return xml_path

def main():
    result = {}
    module_args = dict(zuul_domain=dict(type='str', required=True),
                       zuul_tenant=dict(type='str', required=True),
                       zuul_job_build_id=dict(type='str', required=True),
                       zuul_fetch_test_results=dict(type='bool', required=True),
                       xml_path=dict(type='str', required=True))
    module = AnsibleModule(argument_spec=module_args,
                           supports_check_mode=False)
    try:
        zuul_url = module.params.pop('zuul_domain')
        zuul_tenant = module.params.pop('zuul_tenant')
        build_id = module.params.pop('zuul_job_build_id')
        fetch_test_results = module.params.pop('zuul_fetch_test_results')
        xml_folder = module.params.pop('xml_folder')

        base_url = f'{zuul_url}/api/tenant/{zuul_tenant}/build/{build_id}'

        suite = create_test_suite(base_url)
        result['file_path'] = save_to_file(suite, xml_folder + "deployment.xml")
        
        if fetch_test_results:
            get_test_results(base_url,xml_folder)
        
        module.exit_json(**result)
    except Exception as ex:
        result['msg'] = ex
        module.fail_json(**result)

if __name__ == '__main__':
    main()
