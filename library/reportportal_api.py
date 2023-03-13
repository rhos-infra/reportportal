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

from dateutil import parser
import time
import os
import re
import glob
import xmltodict
import queue
import threading
from reportportal_client import ReportPortalService
from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = '''
---
module: reportportal_api
version_added: "2.4"
short_description: Uploads test results to ReportPortal v5 server
description:
   - This module makes use of the [*] 'reportportal_client' package to talk
     with Reportportal instance over REST in order to publish Xunit test
     results
     [*] https://pypi.org/project/reportportal-client/
options:
    url:
      description:
          - The URL of the Report Portal server.
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
    threads:
      description:
          - Amount of workers to upload results
      required: False
      type: int
    ignore_skipped_tests:
      description:
          - Ignore skipped tests and don't publish them to Reportportal at all
      default: False
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
    launch_start_time:
      description:
          - Override the launch start time, default will be current time.
      required: False
    launch_end_time:
      description:
          - Override the launch end time, default will be current time.
      required: False
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
    log_last_traceback_only:
      description:
          - Write only traceback as a log for the test case
      default: False
      type: bool
    full_log_attachment:
      description:
          - Save the test case log as the attachment if traceback is chosen
      default: False
      type: bool

requirements:
    - "python-dateutl"
    - "reportportal-client"
    - "junitparser"
    - "PyYAML"
    - "lxml"
    - "xmltodict"

'''

RETURN = '''
launch_id:
    description: The created launch ID from Reportportal.
    type: string
    returned: always
expanded_paths:
    description: The list of matching paths from paths argument.
    type: list
    returned: always
expanded_exclude_paths:
    description:
        The list of matching exclude paths from the exclude_path argument.
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
            recursive = True if '**' in path else False
            expanded_paths = expanded_paths + glob.glob(path, recursive=recursive)

        # If there are no glob characters the path is added
        # to the expanded paths whether the path exists or not
        else:
            expanded_paths.append(path)
    return expanded_paths


def format_timestamp(timestamp):
    """Translate different formatted time objects into milliseconds timestamp

    Time objects can be strings with ISO formatted time or float/integer
    timestamps in seconds or milliseconds.

    :param timestamp: Time objects in one of the supported formats
    :return: Timestamp in milliseconds
    """

    if not timestamp:
        return None
    str_time = str(timestamp)
    if str_time.isdigit():
        if int(str_time) > 9999999999:
            return int(str_time)
        else:
            return int(str_time) * 1000
    else:
        return int(parser.parse(str_time).timestamp() * 1000)


def get_start_end_time(test_obj):
    """Calculate test case or test suite start and end time from the XML report

    There is mandatory 'time' and optional 'timestamps' parameters available
    in XML report for each testing objects such as testsuite or test case.
    Time represents the test duration and timestamp stands for the beginning
    of the test execution. If there is no timestamp available, the end time
    is the actual time of current function execution and the start time is
    calculated based on the test duration.

    :param test_obj: Test object dictionary that is taken from XML report
    :return: Start time and end time as milliseconds timestamps
    """

    if not test_obj.get('@time'):
        duration = 0
    else:
        duration = int(float(test_obj.get('@time')) * 1000)
    timestamp = format_timestamp(test_obj.get('@timestamp'))
    if not timestamp:
        end_time = int(time.time() * 1000)
        start_time = end_time - duration
    else:
        start_time = timestamp
        end_time = start_time + duration
    return str(start_time), str(end_time)


class PublisherThread(threading.Thread):

    def __init__(self, queue, publisher):
        self.queue = queue
        self.publisher = publisher
        super().__init__()

    def run(self):
        while True:
            try:
                test_case, parent_id = self.queue.get(timeout=3)
                self.publisher.publish_test_cases(test_case, parent_id)
            except queue.Empty:
                return
            finally:
                self.queue.task_done()


class ReportPortalPublisher:

    def __init__(self, service, launch_name, launch_attrs,
                 launch_description, ignore_skipped_tests,
                 log_last_traceback_only, full_log_attachment,
                 expanded_paths, threads,
                 launch_start_time=str(int(time.time() * 1000))):
        self.service = service
        self.launch_name = launch_name
        self.launch_attrs = launch_attrs
        self.launch_description = launch_description
        self.ignore_skipped_tests = ignore_skipped_tests
        self.log_last_traceback_only = log_last_traceback_only
        self.full_log_attachment = full_log_attachment
        self.expanded_paths = expanded_paths
        self.threads = threads
        self.launch_start_time = launch_start_time

    def publish_tests(self):
        """
        Publish results of test xml file
        """
        # Start Reportportal launch
        self.service.start_launch(
            name=self.launch_name,
            start_time=self.launch_start_time,
            attributes=self.launch_attrs,
            description=self.launch_description
        )

        # Iterate over XUnit test paths
        for test_path in self.expanded_paths:
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
                    self.publish_test_suite(test_suite)
            else:
                # publish single test suite
                self.publish_test_suite(data.get('testsuite'))

    def publish_test_suite(self, test_suite):
        """
        Publish results of test suite xml file
        :param test_suite: Test suite to publish
        """
        # get test cases from xml
        test_cases = test_suite.get("testcase", [])

        # safety incase of single test case which is not a list
        if not isinstance(test_cases, list):
            test_cases = [test_cases]

        start_time, end_time = get_start_end_time(test_suite)

        # start test suite
        item_id = self.service.start_test_item(
            name=test_suite.get('@name', test_suite.get('@id', 'NULL')),
            start_time=start_time,
            item_type="SUITE")

        # publish all test cases
        if test_cases:
            if self.threads > 0:
                q = queue.Queue()
                for case in test_cases:
                    q.put((case, item_id))
                for _ in range(self.threads):
                    worker = PublisherThread(q, self)
                    worker.daemon = True
                    worker.start()
                q.join()
            else:
                for case in test_cases:
                    self.publish_test_cases(case, item_id)

        # calculate status
        num_of_failutes = int(test_suite.get('@failures', 0))
        num_of_errors = int(test_suite.get('@errors', 0))
        status = 'FAILED' if (num_of_failutes > 0 or num_of_errors > 0) \
            else 'PASSED'

        self.service.finish_test_item(
            item_id,
            end_time=end_time,
            status=status)

    def get_test_case_name(self, case, limit=255):
        """
        Get the test case name from classname and name combined.
        """
        name = "{c_name}.{t_name}".format(
            c_name = case.get('@classname', ''),
            t_name = case.get('@name', case.get('@id', 'NULL'))
        )
        return name[:limit]

    def publish_test_cases(self, case, parent_id):
        """
        Publish test cases to reportportal
        :param case: Test case to publish
        :param parent_id: ID of the test suite
        """
        issue = None

        if case.get('skipped') and self.ignore_skipped_tests:
            # ignore skipped tests when flag is true
            return

        start_time, end_time = get_start_end_time(case)

        # start test case
        item_id = self.service.start_test_item(
            name = self.get_test_case_name(case, 511),
            start_time=start_time,
            item_type=case.get('@item_type', 'STEP'),
            parent_item_id=parent_id)

        # Add system_out log.
        if case.get('system-out'):
            self.service.log(
                time=start_time,
                message=case.get('system-out'),
                item_id=item_id,
                level="INFO")

        # Indicate type of test case (skipped, failures, passed)
        if case.get('skipped'):
            issue = {"issue_type": "NOT_ISSUE"}
            status = 'SKIPPED'
            skipped_case = case.get('skipped')
            msg = skipped_case.get('@message', '#text') \
                if isinstance(skipped_case, dict) else skipped_case
            self.service.log(
                time=start_time,
                message=msg,
                item_id=item_id,
                level="DEBUG")
        elif case.get('failure') or case.get('error'):
            status = 'FAILED'

            failures = case.get('failure', case.get('error'))
            failures_txt_list = []
            if not isinstance(failures, list):
                failures = [failures]
            for failure in failures:
                failures_txt_list.append(
                    (failure.get('@message') or failure.get('#text')) \
                       if isinstance(failure, dict) else failure
                )
            failures_txt_list = list(filter(None, failures_txt_list))
            failures_txt = None if not len(failures_txt_list) \
              else "\n".join(failures_txt_list)
            log_message = failures_txt
            attachment = None
            if self.log_last_traceback_only:
                matches = re.findall(
                    r'^(Traceback[\s\S]*?)(?:^\s*$|\Z)', failures_txt, re.M)
                if matches:
                    log_message = matches[-1]
                if self.full_log_attachment:
                    if log_message != failures_txt:
                        attachment = {"name": "Entire_log.txt",
                                      "data": failures_txt,
                                      "mime": "text/plain"}
            self.service.log(
                time=start_time,
                message=log_message,
                item_id=item_id,
                attachment = attachment,
                level="ERROR")
        else:
            status = 'PASSED'

        # finish test case
        self.service.finish_test_item(
            item_id,
            end_time=end_time,
            status=status,
            issue=issue)


def main():

    result = {}

    module_args = dict(
        url=dict(type='str', required=True),
        token=dict(type='str', required=True),
        ssl_verify=dict(type='bool', default=True),
        threads=dict(type='int', default=8),
        ignore_skipped_tests=dict(type='bool', default=False),
        project_name=dict(type='str', required=True),
        launch_name=dict(type='str', required=True),
        launch_tags=dict(type='list', required=False),
        launch_description=dict(type='str', default=''),
        launch_start_time=dict(type='str', default=None),
        launch_end_time=dict(type='str', default=None),
        tests_paths=dict(type='list', required=True),
        tests_exclude_paths=dict(type='list', required=False),
        log_last_traceback_only=dict(type='bool', default=False),
        full_log_attachment=dict(type='bool', default=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False)

    service = None
    launch_end_time = None

    try:
        tests_paths = module.params.pop('tests_paths')
        tests_exclude_paths = module.params.pop('tests_exclude_paths')
        ssl_verify = module.params.pop('ssl_verify')
        launch_start_time = module.params.pop('launch_start_time')
        launch_end_time = module.params.pop('launch_end_time')

        expanded_paths = get_expanded_paths(tests_paths)
        expanded_exclude_paths = [] if not tests_exclude_paths else \
            get_expanded_paths(tests_exclude_paths)

        expanded_paths = \
            list(set(expanded_paths) - set(expanded_exclude_paths))

        if not expanded_paths:
            raise IOError("There are no paths to fetch data from")

        missing_paths = []
        for a_path in expanded_paths:
            if not os.path.exists(a_path):
                missing_paths.append(a_path)
        if missing_paths:
            raise FileNotFoundError(
                "Paths not exist: {missing_paths}'".format
                (missing_paths=str(missing_paths)))

        # Get the ReportPortal service instance
        service = ReportPortalService(
            endpoint=module.params.pop('url'),
            project=module.params.pop('project_name'),
            token=module.params.pop('token'),
        )

        service.session.verify = ssl_verify
        if not ssl_verify:
            os.environ.pop('REQUESTS_CA_BUNDLE', None)

        launch_tags = module.params.pop('launch_tags')
        launch_attrs = {}
        for tag in launch_tags:
            tag_attr = tag.split(':', 1)
            if len(tag_attr) == 2:
                if len(tag_attr[0]) > 127:
                    key = tag_attr[0][:127]
                else:
                    key = tag_attr[0]
                if not tag_attr[1]:
                    val = 'N/A'
                elif len(tag_attr[1]) > 127:
                    val = tag_attr[1][:127]
                else:
                    val = tag_attr[1]
                launch_attrs[key] = val

        publisher = ReportPortalPublisher(
            service=service,
            launch_name=module.params.pop('launch_name'),
            launch_attrs=launch_attrs,
            launch_description=module.params.pop('launch_description'),
            ignore_skipped_tests=module.params.pop('ignore_skipped_tests'),
            log_last_traceback_only=\
                    module.params.pop('log_last_traceback_only'),
            full_log_attachment=module.params.pop('full_log_attachment'),
            threads=module.params.pop('threads'),
            expanded_paths=expanded_paths
        )

        if launch_start_time is not None:
            # Time in deployment report may be higher than the time set
            # as launch_start_time because of all the rounds
            fixed_start_time = str(int(launch_start_time) - 1000)
            publisher.launch_start_time = fixed_start_time

        publisher.publish_tests()

        result['expanded_paths'] = expanded_paths
        result['expanded_exclude_paths'] = expanded_exclude_paths
        result['launch_id'] = service.launch_id

        # Set launch ending time
        if launch_end_time is None:
            launch_end_time = str(int(time.time() * 1000))

        # Finish launch.
        service.finish_launch(end_time=launch_end_time)

        module.exit_json(**result)

    except Exception as ex:
        if service is not None and service.launch_id:
            if launch_end_time is None:
                launch_end_time = str(int(time.time() * 1000))
            service.finish_launch(end_time=launch_end_time, status="FAILED")
        result['msg'] = ex
        module.fail_json(**result)


if __name__ == '__main__':
    main()
