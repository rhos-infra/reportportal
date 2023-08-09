#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2021, Alex Katz <akatz@redhat.com>
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


import requests
import sys

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.utils import *
from lxml import etree
from requests.packages.urllib3.exceptions import InsecureRequestWarning

DOCUMENTATION = '''
module: jenkins_job_stages
version_added: '2.9'
short_description: Collect Jenkins job stages details
description:
    - This module generates XUnit file based on the Jenkins job
      information. Job details are collected from the Jenkins server
      using pipeline REST API (more details on github [1])
      [1] https://github.com/jenkinsci/pipeline-stage-view-plugin/
options:
    jenkins_domain:
        description: URL of the Jenkins server
        required: True
        type: str
    jenkins_job_name:
        description: Name of the job
        required: True
        type: str
    jenkins_job_build_id:
        description: ID of the job build
        required: True
        type: str
    ssl_verify:
        description: set certification verifications on/off
        default: True
        type: bool
    xml_path:
        description: Path to save the XML file
        required: True
        type: str

requirements:
    - "lxml"
    - "requests"
'''

RETURN = '''
file_path:
    description: Path of the saved XML file
    type: string
    returned: always
'''

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

ssl_verify = True

def clear_log(string):
    allowed_chars = [9, 10, 13]
    allowed_chars += list(range(32,128))
    new_str = ''.join([c for c in string if ord(c) in allowed_chars])
    return new_str

def get_stage_logs(base_url, steps, status):
    logs = []
    for step_id in steps:
        response = get_json(f'{base_url}/execution/node/{step_id}/wfapi/log', ssl_verify)
        log_entry = clear_log(response.get('text', '')).strip()
        if log_entry:
            logs.append(log_entry)
    log = '\n'.join(logs).strip()

    if not log:
        log = 'No logs found'
    log_obj = etree.Element(status)
    log_obj.text = log

    return log_obj

def create_test_suite(base_url):
    response = get_json(f'{base_url}/wfapi/describe')

    suite = etree.Element('testsuite')
    suite.set('name', 'deployment')
    suite.set('time', str(response.get('durationMillis', 0) // 1000))
    suite.set('timestamp', str(response.get('startTimeMillis', 0) // 1000))

    stages = list(stage['id'] for stage in response['stages'])

    return suite, stages

def create_test_case(base_url, stage_id):
    response = get_json(f'{base_url}/execution/node/{stage_id}/wfapi/describe')
    if response.get('status') == 'IN_PROGRESS':
        return None, 'progress'
    elif response.get('status') in ['SUCCESS', 'UNSTABLE']:
        status = 'system-out'
    elif response.get('status') == 'NOT_EXECUTED':
        status = 'skipped'
    else:
        status = 'failure'

    case = etree.Element('testcase')
    case.set('name', response['name'])
    case.set('time', str(response.get('durationMillis', 0) // 1000))
    case.set('timestamp', str(response.get('startTimeMillis', 0) // 1000))
    case.set('item_type', 'BEFORE_TEST')

    steps = list(step['id'] for step in response['stageFlowNodes'])
    case.append(get_stage_logs(base_url, steps, status))

    return case, status

def main():
    result = {}
    module_args = dict(jenkins_domain=dict(type='str', required=True),
                       jenkins_job_name=dict(type='str', required=True),
                       jenkins_job_build_id=dict(type='str', required=True),
                       ssl_verify=dict(type='bool', default=True),
                       xml_path=dict(type='str', required=True))
    module = AnsibleModule(argument_spec=module_args,
                           supports_check_mode=False)
    try:
        global ssl_verify
        jenkins_url = module.params.pop('jenkins_domain')
        job_name = module.params.pop('jenkins_job_name')
        build_id = module.params.pop('jenkins_job_build_id')
        xml_path = module.params.pop('xml_path')
        ssl_verify = module.params.pop('ssl_verify')


        base_url = f'{jenkins_url}/job/{job_name}/{build_id}'

        suite, stage_ids = create_test_suite(base_url)

        test_count = 0
        failure_count = 0
        for stage_id in stage_ids:
            stage, status = create_test_case(base_url, stage_id)
            if status == 'progress':
                continue
            suite.append(stage)
            test_count += 1
            if status == 'failure':
                failure_count += 1
        suite.set('failures', str(failure_count))
        suite.set('errors', '0')
        suite.set('tests', str(test_count))

        result['file_path'] = save_to_file(suite, xml_path)
        module.exit_json(**result)
    except Exception as ex:
        result['msg'] = ex
        module.fail_json(**result)

if __name__ == '__main__':
    main()
