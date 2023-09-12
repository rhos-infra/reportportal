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
import requests
import urllib.request
import sys

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.utils import (create_folders_on,
                                        has_extension,
                                        replace_extension,
                                        subunit_to_xml)

from requests.packages.urllib3.exceptions import InsecureRequestWarning
from urllib.error import HTTPError

DOCUMENTATION = '''
module: zuul_job_info
version_added: '2.9'
short_description: Get Zuul job details
description:
    - This module is responsible for retrieving the JSON manifest
      associated with a designated build. It then processes the JSON data,
      scanning for artifacts with test reults in the subunit/xml format.
      After locating these artifacts, the module performs a conversion
      from subunit to XML format. The resulting XML files are subsequently
      stored in a user-defined directory.
      Job details are collected from the Zuul server using pipeline REST API.
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
    zuul_api_path_template:
        description: Zuul API path template to extract job info
        E.g.:
           "{zuul_domain}/api/tenant/{zuul_tenant}/build/{zuul_job_build_id}"
        required: True
        type: str
    output_xml_folder:
        description: Folder to save artifacts with test results
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
        if ((node.get('mimetype') != 'application/directory') and
           (".xml" in node['name'] or ".subunit" in node['name'])):
            return (parent + node['name'])
        if node.get('children'):
            for child in node.get('children'):
                get_file_name_from(child, parent+node['name']+'/')

    # get all xml or subunit file names
    file_name_list = []
    for node in manifest_json['tree']:
        result = get_file_name_from(node, '')
        if result is not None:
            file_name_list.append(result)

    test_result_files_xml = 0
    test_result_files_subunit = 0
    for file_name in file_name_list:
        file_url = base_json['log_url'] + file_name
        try:
            response = requests.get(file_url)
            response.raise_for_status()  # Raise an exception for HTTP errors

            if has_extension(file_name, ".xml"):  # save as it is in the destination_folder
                destination_path = destination_folder + file_name
                create_folders_on(destination_path)
                with open(destination_path, 'wb') as f:
                    f.write(response.content)
                test_result_files_xml += 1
            else:  # has ".subunit" extension
                file_tmp_location = "/tmp/" + file_name
                with open(file_tmp_location, 'wb') as f:
                    f.write(response.content)
                #  if needed, convert and save as xml in xml_folder
                new_filename = replace_extension(file_name, ".subunit", ".xml")
                destination_folder = destination_folder.rstrip('/') + '/'
                subunit_to_xml(file_tmp_location, destination_folder + new_filename)
                test_result_files_subunit += 1
        except requests.exceptions.RequestException as e:
            print(f"Error downloading: \n{e} \n{file_url}")

    print("Total test result files feetched: " +
          str(test_result_files_subunit + test_result_files_xml))
    print("Number of xml test result files feetched: " +
          str(test_result_files_xml))
    print("Number of subunit test result files feetched (and converted to xml): " +
          str(test_result_files_subunit))


def main():
    result = {}
    module_args = dict(zuul_domain=dict(type='str', required=True),
                       zuul_tenant=dict(type='str', required=True),
                       zuul_job_build_id=dict(type='str', required=True),
                       zuul_api_path_template=dict(type='str', required=True),
                       output_xml_folder=dict(type='str', required=True))
    module = AnsibleModule(argument_spec=module_args,
                           supports_check_mode=False)
    try:
        zuul_domain = module.params.pop('zuul_domain')
        zuul_tenant = module.params.pop('zuul_tenant')
        zuul_job_build_id = module.params.pop('zuul_job_build_id')
        zuul_api_path_template = module.params.pop('zuul_api_path_template')
        output_xml_folder = module.params.pop('output_xml_folder')

        base_url = zuul_api_path_template.format(zuul_domain=zuul_domain,
                                                 zuul_tenant=zuul_tenant,
                                                 zuul_job_build_id=zuul_job_build_id)
        get_test_results(base_url, output_xml_folder)

        module.exit_json(**result)
    except Exception as ex:
        result['msg'] = ex
        module.fail_json(**result)


if __name__ == '__main__':
    main()
