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
    xml_path:
        description: Path to save the XML file. The path also contains tempest test results in xml format
        required: True
        type: str

requirements:
    - "gzip"
    - "json"
    - "lxml"
    - "requests"
    - "urllib"
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

# def create_tempest_test_case(base_url):
#     response = get_json(f'{base_url}')
#     if response.get('status') == 'IN_PROGRESS':
#         return None, 'progress'
#     elif response.get('status') in ['SUCCESS', 'UNSTABLE']:
#         status = 'system-out'
#     elif response.get('status') == 'NOT_EXECUTED':
#         status = 'skipped'
#     else:
#         status = 'failure'

#     # TODO: get tempest duration and start time from  job-output.json 
#     durationMillis = 1
#     startTimeMillis = 0
#     case = etree.Element('testcase')
#     case.set('name', "tempest")
#     case.set('time', str(durationMillis) )
#     case.set('timestamp', str(startTimeMillis))
#     case.set('item_type', 'TEST')

#     return case


def get_tempest_subunit(zuul_api_url, destination_path):
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

    def p(node, parent):
        if node.get('mimetype') != 'application/directory':
            return(parent+node['name'])
        if node.get('children'):
            for child in node.get('children'):
                    p(child, parent+node['name']+'/')

    # find testrepository.subunit path
    res = base_json['log_url']
    for i in manifest_json['tree']:
        name = p(i, '')
        if "tempest" in name:
            res = res + name
            break
    try:
        response = requests.get(res)     
        response.raise_for_status()  # Raise an exception for HTTP errors
        with open(destination_path, 'wb') as file:
            file.write(response.content) 
    except requests.exceptions.RequestException as e:
        print(f"Error downloading: {e}")
        
    

def subunit_to_xml(subunit_path, xml_path):
    # Read the subunit input
    with open(subunit_path, 'rb') as subunit_file:
        subunit_stream = subunit.v2.StreamResultToBytes()
        subunit.stream_to_byte_stream(subunit_file, subunit_stream)
    
    # Parse the subunit stream and convert to XML
    xml_root = ET.Element('testsuite')
    
    for event in subunit_stream.iter_events():
        if isinstance(event, subunit.v2.TestEvent):
            testcase = ET.SubElement(xml_root, 'testcase', classname=event.test_id, name=event.test_id)
            
            if event.outcome == 'success':
                pass  # You might add additional attributes or elements for success cases
            elif event.outcome == 'fail':
                failure = ET.SubElement(testcase, 'failure', type=event.details)
                failure.text = event.details + '\n' + event.traceback
            else:
                error = ET.SubElement(testcase, 'error', type=event.details)
                error.text = event.details + '\n' + event.traceback
    
    tree = ET.ElementTree(xml_root)
    tree.write(xml_path, encoding='utf-8', xml_declaration=True)
    
def save_to_file(suite, xml_path):
    with open(xml_path, 'wb') as xml_file:
        xml_file.write(etree.tostring(suite, pretty_print=True))
    return xml_path

def main():
    result = {}
    module_args = dict(zuul_domain=dict(type='str', required=True),
                       zuul_job_build_id=dict(type='str', required=True),
                       xml_path=dict(type='str', required=True))
    module = AnsibleModule(argument_spec=module_args,
                           supports_check_mode=False)
    try:
        zuul_url = module.params.pop('zuul_domain')
        zuul_tenant = module.params.pop('zuul_tenant')
        build_id = module.params.pop('zuul_job_build_id')
        xml_path = module.params.pop('xml_path')

        base_url = f'{zuul_url}/api/tenant/{zuul_tenant}/build/{build_id}'

        suite = create_test_suite(base_url)
        local_subunit_path = "/tmp/testrepository.subunit"
        get_tempest_subunit(base_url,local_subunit_path)
        subunit_to_xml(local_subunit_path, xml_path)
        case = create_tempest_test_case(base_url)

        result['file_path'] = save_to_file(suite, xml_path)
        
        module.exit_json(**result)
    except Exception as ex:
        result['msg'] = ex
        module.fail_json(**result)

if __name__ == '__main__':
    main()
