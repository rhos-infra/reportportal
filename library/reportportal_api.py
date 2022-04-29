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

from ansible.module_utils.basic import AnsibleModule
from collections import OrderedDict
from dateutil import parser
from reportportal_client import ReportPortalService
import datetime
import glob
import os
import pytz
import queue
import re
import threading
import time
import xmltodict


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
    reportportal_timezone:
      description:
          - The timezone of the ReportPortal that needs to be updated
            Timezone differences will be fixed automatically in case the tests
            were executed in a future time compare to local time of the
            ReportPortal instance
      type: str

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
        if '*' in path or '?' in path:
            recursive = True if '**' in path else False
            expanded_paths = \
                expanded_paths + glob.glob(path, recursive=recursive)

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


class TestSuiteManager:

    _tsms = OrderedDict()
    deployment_file_name = 'deployment.xml'

    def __init__(self, result_files, skip_dep_times=True):
        TestSuiteManager._tsms[self] = self
        self.skip_deployment_times = skip_dep_times
        self._testsuites = OrderedDict()
        self._newest_end_time = None
        self._oldest_start_time = None
        for result_file in result_files:
            self.add_testsuites_from_file(result_file)

        self.adjust_times()

    @classmethod
    def get_last_tsm(cls):
        return list(cls._tsms.items())[-1][-1]

    def add_testsuites_from_file(self, file):
        with open(file) as fd:
            data = xmltodict.parse(fd.read())

        # get multiple test suites if present
        if data.get('testsuites'):
            # get the test suite object
            testsuites_obj = data.get('testsuites')
            # get all test suites (1 or more) from the object
            testsuites = testsuites_obj.get('testsuite') \
                if isinstance(testsuites_obj.get('testsuite'), list) \
                else [testsuites_obj.get('testsuite')]
        else:
            # publish single test suite
            testsuites = [data.get('testsuite')]

        for idx, testsuite in enumerate(testsuites):
            self.add_test_suite(testsuite, idx, file)

    @property
    def testsuites(self):
        return list(self._testsuites)

    def add_test_suite(self, testsuite, idx, file):
        tsw = TestSuiteWrapper(testsuite, idx, file)
        self._testsuites[tsw] = tsw

    @property
    def oldest_start_time(self):

        oldest = None
        for testsuite in self.testsuites:
            if self.skip_deployment_times and \
                    os.path.basename(testsuite.file) == \
                    self.__class__.deployment_file_name:
                continue
            if oldest is None or testsuite.start_time < oldest:
                oldest = testsuite.start_time

        self.oldest_start_time = oldest
        return oldest

    @oldest_start_time.setter
    def oldest_start_time(self, oldest_start_time):
        self._oldest_start_time = oldest_start_time

    @property
    def newest_end_time(self):

        newest = None
        for testsuite in self.testsuites:
            if self.skip_deployment_times and \
                    os.path.basename(testsuite.file) == \
                    self.__class__.deployment_file_name:
                continue
            if newest is None or testsuite.end_time > newest:
                newest = testsuite.end_time

        self.newest_end_time = newest
        return newest

    @newest_end_time.setter
    def newest_end_time(self, newest_end_time):
        self._newest_end_time = newest_end_time

    def adjust_times(self):

        for testsuite in self.testsuites:
            if os.path.basename(testsuite.file) == \
                    self.__class__.deployment_file_name:
                testsuite.end_time = self.newest_end_time

                dep_start_time = self.newest_end_time - testsuite.duration

                if self.oldest_start_time > dep_start_time:
                    self.oldest_start_time = dep_start_time

                testsuite.start_time = dep_start_time

    def correct_times(self, rp_cur_time):
        for testsuite in self.testsuites:
            testsuite.correct_times(rp_cur_time)


class TestSuiteWrapper:

    def __init__(self, testsuite, idx, file):
        self._testsuite = testsuite
        self._idx = idx
        self._file = file
        self._start_time = None
        self._end_time = None
        self._timestamp = None

    @property
    def idx(self):
        return self._idx

    @property
    def file(self):
        return self._file

    @property
    def time(self):
        return self._testsuite.get('@time')

    @property
    def duration(self):
        return self.time

    @property
    def name(self):
        return self._testsuite.get('@name', self.testsuite.get('@id', 'NULL'))

    @property
    def errors(self):
        return int(self._testsuite.get('@errors', 0))

    @property
    def failures(self):
        return int(self._testsuite.get('@failures', 0))

    @property
    def skipped(self):
        return int(self._testsuite.get('@skipped', 0))

    @property
    def tests(self):
        return int(self._testsuite.get('@tests'))

    @property
    def passed(self):
        return self.tests - self.skipped - self.errors - self.failures

    @property
    def timestamp(self):
        if self._timestamp is not None:
            return self._timestamp

        timestamp = self._testsuite.get('@timestamp')
        if timestamp is None:
            return

        # Numeric timestamp
        if str(timestamp).isnumeric():
            if len(timestamp) >= 13:
                timestamp = int(timestamp)
            else:
                timestamp = int(timestamp) * 1000

        # ISO format timestamp
        else:
            parsed_time = parser.parse(timestamp)
            timestamp = int(parsed_time.timestamp()) * 1000

        self._timestamp = timestamp
        return timestamp

    @timestamp.setter
    def timestamp(self, timestamp):
        self._timestamp = timestamp

    def get_file_modified_time(self):
        status = os.stat(self.file)
        return int(status.st_mtime * 1000)

    @property
    def start_time(self):
        if self._start_time is not None:
            return self._start_time

        if self.timestamp:
            self._start_time = self.timestamp
        else:
            self._start_time = self.get_file_modified_time() - \
                        int(float(self.duration) * 1000)

        return self._start_time

    @start_time.setter
    def start_time(self, start_time):
        self._start_time = int(start_time)

    @property
    def end_time(self):
        if self._end_time is not None:
            return self._end_time

        self._end_time = self.start_time + int(float(self.duration) * 1000)

        return self._end_time

    @end_time.setter
    def end_time(self, end_time):
        self._end_time = int(end_time)

    def correct_times(self, rp_cur_time):
        if self.end_time > rp_cur_time:
            delta_ms = self.end_time - rp_cur_time

            self.start_time -= delta_ms
            self.end_time -= delta_ms

            if self.timestamp:
                self._timestamp -= delta_ms

    @property
    def testsuite(self):
        return self._testsuite


class ReportPortalPublisher:

    def __init__(self, service, launch_name, launch_attrs,
                 launch_description, ignore_skipped_tests,
                 log_last_traceback_only, full_log_attachment,
                 expanded_paths, threads,
                 launch_start_time=None):
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
        self.tsm = TestSuiteManager.get_last_tsm()

    def publish_tests(self):
        """
        Publish results of test xml file
        """
        oldest_launch_start_time = \
            self.launch_start_time or str(self.tsm.oldest_start_time)

        # Start Reportportal launch
        self.service.start_launch(
            name=self.launch_name,
            start_time=oldest_launch_start_time,
            attributes=self.launch_attrs,
            description=self.launch_description
        )

        for test_suite in self.tsm.testsuites:
            self.publish_test_suite(test_suite)

    def publish_test_suite(self, test_suite):
        """
        Publish results of test suite xml file
        :param test_suite: Test suite to publish
        """
        # get test cases from xml
        test_cases = test_suite.testsuite.get("testcase")

        # safety in case of single test case which is not a list
        if not isinstance(test_cases, list):
            test_cases = [test_cases]

        # start test suite
        item_id = self.service.start_test_item(
            name=test_suite.name,
            start_time=test_suite.start_time,
            item_type="SUITE")

        # publish all test cases
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
        if test_suite.failures > 0 or test_suite.errors > 0:
            status = 'FAILED'
        else:
            status = 'PASSED'

        self.service.finish_test_item(
            item_id,
            end_time=test_suite.end_time,
            status=status)

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
            name=case.get('@name', case.get('@id', 'NULL'))[:255],
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
            failures_txt = ""
            if isinstance(failures, list):
                for failure in failures:
                    msg = failure.get('@message', failure.get('#text')) \
                        if isinstance(failure, dict) else failure
                    failures_txt += '{msg}\n'.format(msg=msg)
            else:
                failures_txt = \
                        failures.get('@message', failures.get('#text')) \
                        if isinstance(failures, dict) else failures

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
        full_log_attachment=dict(type='bool', default=False),
        reportportal_timezone=dict(type='str', default=None)
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
        rp_timezone = module.params.pop('reportportal_timezone')

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

        # Updates TestSuiteManager with all test suites from all files
        tsm = TestSuiteManager(expanded_paths)

        # Correct timezones difference
        if rp_timezone:
            rp_cur_time = int(datetime.datetime.now(
                pytz.timezone(rp_timezone)).timestamp() * 1000)
            tsm.correct_times(rp_cur_time)

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
            publisher.launch_start_time = tsm.oldest_start_time

        publisher.publish_tests()

        result['expanded_paths'] = expanded_paths
        result['expanded_exclude_paths'] = expanded_exclude_paths
        result['launch_id'] = service.launch_id

        # Set launch ending time
        if launch_end_time is None:
            launch_end_time = str(int(time.time() * 1000))

        # Finish launch.
        service.finish_launch(end_time=tsm.newest_end_time)

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
