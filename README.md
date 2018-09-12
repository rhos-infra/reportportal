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
    --jenkins-build-id $BUILD_ID