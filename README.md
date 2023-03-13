Reportportal
============

Ansible role for sending XUnit test results to ReportPortal.

ReportPortal is a service, that provides increased capabilities to speed up
results analysis and reporting through the use of built-in analytic features.

Configuration Flags
-------------------

* `--import`:
    Execute import tasks to import test results to ReportPortal.
    Set `yes` to run. Omitting the flag or setting it to `no` will skip that stage.
* `--url-address`:
    Path to ReportPortal URL.
* `--port`:
    ReportPortal URL port.
* `--token`:
    Reportportal API token.
* `--archive-import-path`:
    Pattern for the path location of test xml results.
* `--launch-tags`:
    Tags to be applied to a specified launch.
* `--launch-description`:
    Description to be added to a specified launch.
* `--project-name`:
    Reportportal project name to push results to.
* `--class-in-name`:
    For test case name in Reportportal use combination of classname+name. If not set (false) only name is used.

Jenkins Environment Variables
-----------------------------
Jenkins Set Environment Variables you can use for launch deployment description.

* `--jenkins-domain`:
    Domain of jenkins to add as meta data to results.
    For Current URL of the Jenkins master that's running the build use jenkins
    environment variables $JENKINS_URL.
    .. note:: This parameter is required when the import flag is on.
* `--jenkins-job-name`:
    Jenkins Job name.
    For Current project name of this build use jenkins environment variables $JOB_NAME.
    .. note:: This parameter is required when the import flag is on.
* `--jenkins-build-id`:
    Jenkins build ID.
    For Current build ID use jenkins environment variables $BUILD_ID.
* `--jenkins-user-name`:
    Specify Jenkins user which executed the job.


Example:

    infrared reportportal --import yes \
    --url-address http://reportportal_url.example.com \
    --port 8080 \
    --token 123456789 \
    --archive-import-path $WORKSPACE/junit/*.xml \
    --launch-tags DFG:network,COMPONENT:networking-ovn,RHEL_VERSION:rhel-7.5,PRODUCT_VERSION:13 \
    --project-name PROJECT_NAME \
    --jenkins-domain $JENKINS_URL \
    --jenkins-job-name  $JOB_NAME \
    --jenkins-build-id $BUILD_ID \
    --class-to-name true


Dashboard2Email
===============

The purpose of it is to capture info and a screenshot from a given RP Dashboard
and send it via email. One of the use cases for it may be to send a daily status email to the Team.

dashboard2email is one of the tasks under this Report Portal (RP) Ansible Playbook.

Dashboard2email does _not_ run by default when you run 'reportportal' plugin. To invoke it run:

    infrared reportportal --dashboard2email yes

All the required parameters, i.e.: url of the dashboard in RP, will be shown after running the above command.

Example:

    infrared reportportal -v --import no --analyze no --dashboard2email yes --token <token_here> --url-address http://seal51.qa.lab.tlv.redhat.com:8081/ui/#rhel_osp/dashboard/5af5938420b54300014d791d --port 8081 --project-name RHEL_OSP --email_to wznoinsk@redhat.com --email_subject "DFG OpenDaylight OSP13 CI status"

How it works
------------
1. Ansible Playbook

    a) prepares a docker container called 'reportportal_dashbaord2email' and installs all requirements inside

    b) starts a vncserver in it

2. dashboard2email.py

    a) starts a new, or reconnects to an existing, Firefox instance (it's using vncserver as display)
    NOTE: Report Portal is heavily dependent on JavaScript hence using a real web browser is a must.

    b) it's using 'Selenium' python lib to connect to the Firefox instance, open requested Report Portal dashboard, login, gather statistics and capture a screenshot of the dashboard

    c) sends an email with these stats + the screenshot


Requirements
------------

    yum install -y docker
    groupadd docker
    usermod -aG docker <username_that_dashboard2email_will_run_as>
    systemctl start docker
    systemctl enable docker

Troubleshooting
---------------
The Ansible and Python parts should be fairly self explanatory.

On the other hand, to troubleshoot problems related to Firefox and what happens inside it, it's recommended to connect using VNC client to started vncserver. dashboard2email docker container shares network namespace with its host hence connecting to its vncserver is <hosts_ip>:10, i.e.:

    rhosw08.oslab.openstack.engineering.redhat.com:10

Once connected over VNC you can rerun the Playbook and/or the dashboard2email.py itself and observe what happens on the VNC session.
