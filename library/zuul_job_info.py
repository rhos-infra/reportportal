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

import json
import os
import requests
import urllib.request
import xml.etree.ElementTree as ET

from ansible.module_utils.basic import AnsibleModule

from lxml import etree
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from urllib.error import HTTPError
from utils import *

DOCUMENTATION = '''
module: zuul_job_info
version_added: '2.9'
short_description: Get Zuul job details
description:
    - This module creates an XML file using the provided Zuul job details,
	  including information such as duration, start time, and job status.
	  The resulting XML file is then stored in the designated destination.
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
    output_xml_file:
        description: File path to save the generated XML file
        required: True
        type: str

requirements:
    - "datetime"
    - "json"
    - "os"
    - "requests"
    - "urllib"
    - "xml"
'''

RETURN = '''
file_path:
    description: Path of the saved XML files
    type: string
    returned: always
'''

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def create_test_suite(base_url):
    response = get_json(f'{base_url}')

    suite = etree.Element('testsuite')
    suite.set('name', 'deployment')
    suite.set('time', str(response.get('duration', 0)))
    suite.set('result', str(response.get('result', 0)))

    date_string = str(response.get('start_time', 0)) # "2023-08-06T13:20:14"
    date_format = f'%Y-%m-%dT%H:%M:%S'
    suite.set('timestamp', convert_date_to_sec(date_string,date_format))

    return suite
   
def main():
    result = {}
    module_args = dict(zuul_domain=dict(type='str', required=True),
                       zuul_tenant=dict(type='str', required=True),
                       zuul_job_build_id=dict(type='str', required=True),
                       zuul_api_path_template=dict(type='str', required=True),
                       output_xml_file=dict(type='str', required=True))
    module = AnsibleModule(argument_spec=module_args,
                           supports_check_mode=False)
    try:
        zuul_domain = module.params.pop('zuul_domain')
        zuul_tenant = module.params.pop('zuul_tenant')
        zuul_job_build_id = module.params.pop('zuul_job_build_id')
        zuul_api_path_template=module.params.pop('zuul_api_path_template')
        output_xml_file = module.params.pop('output_xml_file')

        base_url = zuul_api_path_template.format(zuul_domain=zuul_domain, \
                                               zuul_tenant=zuul_tenant, \
                                                zuul_job_build_id=zuul_job_build_id)

        suite = create_test_suite(base_url)
        result['file_path'] = save_to_file(suite, output_xml_file)

        module.exit_json(**result)
    except Exception as ex:
        result['msg'] = ex
        module.fail_json(**result)

if __name__ == '__main__':
    main()
