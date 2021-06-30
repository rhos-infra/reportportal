#!/usr/bin/env python

# coding: utf-8 -*-

# (c) 2018, Waldemar Znoinski <wznoinsk@redhat.com>
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


import re
import os
import smtplib
import sys
import time

from ansible.module_utils.basic import AnsibleModule
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from time import sleep


DOCUMENTATION = '''
---
module: dashboard2email
version_added: "2.4"
short_description: Captures information and screenshot of Report Portal Dashboard and sends it as an email
description:
   - The purpose of it is to capture info and a screenshot from a given RP Dashboard
     and send it via email. One of the use cases for it may be to send a daily status email to the Team.

options:
    display:
      description: Display (HOST:PORT) to connect to (that vncserver or Xvfb is listening on).
      required: True
      type: str
    url:
      description: The URL of the Report Portal Dashboard to capture.
      required: True
      type: str
    user_name:
      description: Name of the user of Report Portal Dashboard
      required: True
      type: str
    token:
      description: Reportportal API token.
      required: True
      type: str
    email_server_name:
      description: Hostname or IP of smtp server
      required: True
      type: str
    email_server_port:
      description: Port of smtp server
      required: True
      type: str
    email_from:
      description: Sender's email address
      required: True
      type: str
    email_to:
      description: Recipient's email address
      required: True
      type: str
    email_subject:
      description: Email's subject
      required: False
      type: str
      default: 'Report Portal Dashboard2Email report'
    email_body:
      description: Email's body
      required: False
      type: str
      default: ''
   
requirements:
    - "selenium"
'''

RETURN = '''
email_stats:
    description: Number of failed tests as reported in the e-mail
    type: str
    returned: always
'''


def process_exception(step='step unknown', debug=None, _browser=None, _notify=None, msg=sys.exc_info()[1]):
    dt = time.localtime()
    datetime = "%04d%02d%02d_%02d%02d%02d" % (dt.tm_year, dt.tm_mon, dt.tm_yday, dt.tm_hour, dt.tm_min, dt.tm_sec)

    print("step: %s, exception: %s" % (step, msg))

    if debug == "text":
        file_name = 'debug/debug_text_%s.txt' % datetime
        _step("DEBUG saving text: %s" % file_name)
        with open(file_name, 'w') as fp:
            fp.write("%s" % _browser.page_source.encode('utf-8').strip())

    if debug == "screenshot":
        file_name = 'debug/debug_screenshot_%s.jpg' % datetime
        _step("DEBUG saving screenshot: %s" % file_name)
        _browser.get_screenshot_as_file(file_name)

    if _browser:
        _browser.quit()
    exit(5)


def _step(msg):
    dt = time.localtime()
    datetime = "%04d%02d%02d_%02d%02d%02d" % (dt.tm_year, dt.tm_mon, dt.tm_mday, dt.tm_hour, dt.tm_min, dt.tm_sec)
    print("%s | %s" % (datetime, msg))


def open_rp_dashboard(params=None, _browser=None):
    _step("Logging in to Report Portal")
    try:
        user_name = params['user_name']
        user_pass = user_name
        user_token = params['token']

        _browser.get(params['url'])
        assert 'Report Portal' in _browser.title

        # fill in username and password and login
        login_form = _browser.find_element_by_class_name('login-form')
        login_form_input_fields = login_form.find_elements_by_tag_name('input')
        login_form_input_fields[0].send_keys(user_name)
        login_form_input_fields[1].send_keys(user_pass + Keys.RETURN)

        try:
            _browser.find_element_by_partial_link_text('DFG Opendaylight OSP13 HA standard deployment')

        except Exception as ex:
            process_exception(step='open_rp_dashboard', msg="It looks like the 'DFG Opendaylight OSP13 HA standard deployment' cannot be loaded: %s" % ex.message)

        sleep(15)

        try:
            _step('Gathering statistics on failed tests')
            # find info about Failed tests in the widgets
            # find widgets first, then stats fields and failed info inside
            failed = {}
            widgets = _browser.find_elements_by_class_name('gadget-wrapper')
            for _w in widgets:
                w_name = _w.find_element_by_class_name('gadget-header').find_element_by_class_name('info-block'). \
                    find_element_by_tag_name('h2').text

                if 'Last CI run stats' in w_name:
                    failed[w_name] = _w.find_element_by_class_name('statistics-block').find_element_by_class_name('failed')
        except Exception as ex:
            process_exception(step='Gathering statistics on failed tests (consider restarting docker container)', msg=ex.message)

        screenshot_png = _browser.get_screenshot_as_png()

    except Exception as ex:
        process_exception(step='open_rp_dashboard', msg=ex.message)

    return (screenshot_png, failed)


def send_email(params=None, img=None, stats=None):
    email_to = params['email_to']
    _step('Sending email to %s' % email_to)

    email_from = params['email_from']
    email_subject = params['email_subject']
    email_stats = ''

    for s in sorted(stats.keys()):
        _text = re.search('CSIT|TEMPEST', s)
        email_stats += ", %s: %s" % (_text.group(0), stats[s].text)

    msgRoot = MIMEMultipart('related')
    msgRoot['From'] = email_from
    msgRoot['To'] = email_to
    msgRoot['Subject'] = "%s%s" % (email_subject, email_stats)

    # Create the body of the message.
    html = """\
        <p><br/>
            <a href=%s>Open Dashboard</a><br/>
            <br/>%s<br/>
            <a href=%s><img src="cid:image1"></a>
        </p>
    """ % (params['url'], params['email_body'], params['url'])

    # Record the MIME types.
    msgHtml = MIMEText(html, 'html')
    msgImg = MIMEImage(img, 'png')
    msgImg.add_header('Content-ID', '<image1>')
    msgImg.add_header('Content-Disposition', 'inline')

    msgRoot.attach(msgHtml)
    msgRoot.attach(msgImg)

    try:
        server = smtplib.SMTP(params['email_server_name'], params['email_server_port'])
        server.ehlo()
        server.sendmail(email_from, email_to, msgRoot.as_string())
        server.close()

        print('Email sent!')
    except Exception as ex:
        process_exception(step='Send email', msg=ex.message)

    return email_stats


def main():
    result = {}
    env = os.environ

    module_args = dict(
        display=dict(type='str', required=True),
        url=dict(type='str', required=True),
        user_name=dict(type='str', required=True),
        token=dict(type='str', required=True),
        email_server_name=dict(type='str', required=True),
        email_server_port=dict(type='str', required=True),
        email_from=dict(type='str', required=True),
        email_to=dict(type='str', required=True),
        email_subject=dict(type='str', required=False, default='Report Portal Dashboard2Email'),
        email_body=dict(type='str', required=False, default='')
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False)

    params = dict(
        display = module.params.pop('display'),
        url = module.params.pop('url'),
        user_name = module.params.pop('user_name'),
        token = module.params.pop('token'),
        email_server_name = module.params.pop('email_server_name'),
        email_server_port = module.params.pop('email_server_port'),
        email_from = module.params.pop('email_from'),
        email_to = module.params.pop('email_to'),
        email_subject = module.params.pop('email_subject'),
        email_body = module.params.pop('email_body')
    )

    _step("Starting with params... display: %s, url: %s, user_name: %s, token: %s, email_to: %s, email_subject: %s, email_body: %s" % \
          (params['display'], params['url'], params['user_name'], params['token'], params['email_to'], params['email_subject'], params['email_body']))
    _step("Starting with env: %s" % env)

    try:
        # TODO: need to create and use a FirefoxProfile so an existing (already running) Firefox instance may be reused
        # geckodriver's option: --connect-existing

        _step('Open new or connect to already running Firefox instance')
        browser_options = webdriver.FirefoxOptions()
        browser_options.add_argument('--display %s' % params['display'])
        # browser_options.add_argument('--safe-mode')

        browser = webdriver.Firefox(timeout=120, firefox_options=browser_options)
        browser.set_script_timeout(300)
        browser.set_page_load_timeout(60)
        browser.implicitly_wait(15)

        # NOTE: if it's bigger than '-geometry' parameter vncserver was started with there may be problems with capturing the whole browser windows
        browser.set_window_size('1280', '700')

        # NOTE: maximize didn't do anything, fullscreen made the firefox window behave funny
        # browser.maximize_window()
        # browser.fullscreen_window()

    except Exception as ex:
        process_exception(step='open browser', msg="%s\n !!! check whether all dependencies from README are met !!!\n" % ex.message, _notify=None)

    (screenshot_png, failed) = open_rp_dashboard(params=params, _browser=browser)
    result['email_stats'] = send_email(params=params, img=screenshot_png, stats=failed)

    browser.quit()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
