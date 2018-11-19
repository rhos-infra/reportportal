#!/usr/bin/python
# coding: utf-8 -*-

# (c) 2018, Avishay Machluf <amachluf@redhat.com>
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

import time
import os
import glob
import xmltodict
from reportportal_client import ReportPortalService
from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = '''
---
module: reportportal_api
version_added: "2.4"
short_description: Uploads test results to Reportportal server
description:
   - This module makes use of the [*] 'reportportal_client' package to talk 
     with Reportportal instance over REST in order to publish Xunit test results
     [*] https://pypi.org/project/reportportal-client/
options:
    url:
      description:
          - The URL of the Bugzilla instance to talk with.
      required: True
      type: str
    token:
      description:
          - Reportportal API token.
      required: True
      type: str
    ssl_verify:
      description:
          - Ignore ssl verifications
      default: True
      type: bool
    project_name:
      description:
          - Reportportal project name to push results to.
      required: True
      type: str
    launch_name:
      description:
          - Reportportal launch name to push results to.
      required: True
      type: str
    launch_tags:
      description:
          - Tags to be applied to a specified launch.
      required: False
      type: list
    launch_description:
      description:
          - Description to be added to a specified launch.
      required: False
      default: ''
      type: str
    tests_paths:
      description:
          - Pattern for the path location of test xml results.
      required: True
      type: list
    tests_exclude_paths:
      description:
          - Pattern for the path location of excluded test xml results.
      required: False
      type: list

requirements:
    - "reportportal-client"
    - "junitparser"
    - "PyYAML"
    - "lxml"
    - "xmltodict"

'''

RETURN = '''
launch_id:
    description:
        The created launch ID from Reportportal.
    type: string
    returned: always
expanded_paths:
    description: The list of matching paths from paths argument.
    type: list
    returned: always
expanded_exclude_paths:
    description: The list of matching exclude paths from the exclude_path argument.
    type: list
    returned: always
'''


def get_expanded_paths(paths):
    """
    Translate patterns of paths to real path
    :param paths: Pattern for the path location of xml files
    :return: expanded_paths: The list of matching paths from paths argument
    """
    expanded_paths = []

    for path in paths:
        path = os.path.expanduser(os.path.expandvars(path))

        # Expand any glob characters. If found, add the expanded glob to
        # the list of expanded_paths, which might be empty.
        if ('*' in path or '?' in path):
            expanded_paths = expanded_paths + glob.glob(path)

        # If there are no glob characters the path is added
        # to the expanded paths whether the path exists or not
        else:
            expanded_paths.append(path)
    return expanded_paths


def publish_test_suite(service, test_suite):
    """
    Publish results of test suite xml file
    :param service: Reportportal service
    :param test_suite: Test suite to publish
    :return:
    """
    # get test cases from xml
    test_cases = test_suite.get("testcase")

    # safety incase of single test case which is not a list
    if not isinstance(test_cases, list):
        test_cases = [test_cases]

    # start test suite
    service.start_test_item(
        name=test_suite.get('@name', test_suite.get('@id', 'NULL')),
        start_time=str(int(time.time() * 1000)),
        item_type="SUITE")

    # publish all test cases
    for case in test_cases:
        publish_test_cases(service, case)

    # calculate status
    num_of_failutes = int(test_suite.get('@failures'))
    num_of_errors = int(test_suite.get('@errors'))
    status = 'FAILED' if (num_of_failutes > 0 or num_of_errors > 0) \
        else 'PASSED'

    service.finish_test_item(
        end_time=str(int(time.time() * 1000)),
        status=status)


def publish_test_cases(service, case):
    """
    Publish test cases to reportportal
    :param service: Reportportal service
    :param case: Test case to publish
    :return:
    """
    issue = None
    description = "{tc_name} time: {case_time}".format(
        tc_name=case.get('@name', case.get('@id', 'NULL')),
        case_time=case.get('@time'))

    name = case.get('@name', case.get('@id', 'NULL'))

    # start test case
    service.start_test_item(
        name=name[:255],
        description=description,
        tags=case.get('@classname', '').split('.'),
        start_time=str(int(time.time() * 1000)),
        item_type="STEP")

    # Add system_out log.
    if case.get('system-out'):
        service.log(
            time=str(int(time.time() * 1000)),
            message=case.get('system-out'),
            level="INFO")

    # Indicate type of test case (skipped, failures, passed)
    if case.get('skipped'):
        issue = {"issue_type": "NOT_ISSUE"}
        status = 'SKIPPED'
        skipped_case = case.get('skipped')
        msg = skipped_case.get('@message', '#text') \
            if isinstance(skipped_case, dict) else skipped_case
        service.log(
            time=str(int(time.time() * 1000)),
            message=msg,
            level="DEBUG")
    elif case.get('failure') or case.get('error'):
        status = 'FAILED'

        failures = case.get('failure', case.get('error'))
        failures_txt = ""
        if isinstance(failures, list):
            for failure in failures:
                msg = failure.get('@message', failure.get('#text')) \
                    if isinstance(failure, dict) else failure
                failures_txt += \
                    '{msg}\n'.format(msg=msg)
        else:
            failures_txt = failures.get('@message', failures.get('#text')) \
                if isinstance(failures, dict) else failures

        service.log(
            time=str(int(time.time() * 1000)),
            message=failures_txt,
            level="ERROR")
    else:
        status = 'PASSED'

    # finish test case
    service.finish_test_item(
        end_time=str(int(time.time() * 1000)),
        status=status,
        issue=issue)


def main():

    result = {}

    module_args = dict(
        url=dict(type='str', required=True),
        token=dict(type='str', required=True),
        ssl_verify=dict(type='bool', required=False, default=True),
        project_name=dict(type='str', required=True),
        launch_name=dict(type='str', required=True),
        launch_tags=dict(type='list', required=False),
        launch_description=dict(type='str', required=False, default=''),
        tests_paths=dict(type='list', required=True),
        tests_exclude_paths=dict(type='list', required=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False)

    try:
        tests_paths = module.params.pop('tests_paths')
        tests_exclude_paths = module.params.pop('tests_exclude_paths')
        ssl_verify = module.params.pop('ssl_verify')

        expanded_paths = get_expanded_paths(tests_paths)
        expanded_exclude_paths = [] if not tests_exclude_paths else \
            get_expanded_paths(tests_exclude_paths)

        if not expanded_paths:
            return module.fail_json(path=', '.join(tests_paths),
                                    expanded_paths=', '.join(expanded_paths),
                                    msg='Error, no source paths were found')

        # Get the Reportortal service instance
        service = ReportPortalService(
            endpoint=module.params.pop('url'),
            project=module.params.pop('project_name'),
            token=module.params.pop('token'),
        )

        service.session.verify = ssl_verify
        if not ssl_verify:
            os.environ.pop('REQUESTS_CA_BUNDLE', None)

        # Start Reportportal launch
        service.start_launch(
            name=module.params.pop('launch_name'),
            start_time=str(int(time.time() * 1000)),
            tags=module.params.pop('launch_tags'),
            description=module.params.pop('launch_description')
        )

        # Iterate over XUnit test paths
        for test_path in expanded_paths:
            # open the XUnit file and parse to xml object
            with open(test_path) as fd:
                data = xmltodict.parse(fd.read())

            # get multiple test suites if present
            if data.get('testsuites'):
                # get the test suite object
                test_suites_object = data.get('testsuites')
                # get all test suites (1 or more) from the object
                test_suites = test_suites_object.get('testsuite') \
                    if isinstance(test_suites_object.get('testsuite'), list) \
                    else [test_suites_object.get('testsuite')]

                # publish all test suites
                for test_suite in test_suites:
                    publish_test_suite(service, test_suite)
            else:
                # publish single test suite
                publish_test_suite(service, data.get('testsuite'))

        result['expanded_paths'] = expanded_paths
        result['expanded_exclude_paths'] = expanded_exclude_paths
        result['launch_id'] = service.launch_id

        # Finish launch.
        service.finish_launch(end_time=str(int(time.time() * 1000)))

        module.exit_json(**result)

    except Exception as ex:
        if service is not None and service.launch_id:
            service.stop_launch(end_time=str(int(time.time() * 1000)),
                                status="FAILED")
        result['msg'] = ex.message
        module.fail_json(**result)


if __name__ == '__main__':
    main()
