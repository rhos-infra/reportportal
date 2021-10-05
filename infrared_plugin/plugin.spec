plugin_type: other
subparsers:
    reportportal:
        description: ReportPortal.
        include_groups: ["Ansible options", "Common options"]
        groups:
            - title: ReportPortal Configuration
              options:
                  token:
                      type: Value
                      help: Reportportal API token
                      required: yes
                  url-address:
                      type: Value
                      help: Path to ReportPortal URL.
                      required: yes
                  ssl-verify:
                      type: Bool
                      help: Reportportal url SSL verify
                      default: no
                  project-name:
                      type: Value
                      help: Reportportal project name to push results to.
                      required: yes
                  socket-timeout:
                      type: Value
                      help: Socket timeout
                  threads:
                      type: Value
                      help: Amount of API workers to upload results
                      default: '8'

            - title: ReportPortal launch options
              options:
                  launch-mode:
                      type: Value
                      help: The mode to set the launch with
                      default: DEFAULT
                  launch-id:
                      type: Value
                      help: ID of a launch.
                  launch-tags:
                      type: Value
                      help: |
                        Tags to be applied to a specified launch.
                        Tags should be separated with ';'.
                        --launch-tags "key1:value1;key2:value2_1,value2_2..."
                  launch-description:
                      type: Value
                      help: Description to be added to a specified launch.
                      default: ''
                  launch-core-puddle:
                      type: Value
                      help: Core Puddle
                  launch-start-time:
                      type: Value
                      help: Override the launch starting time instead of using current time as default.
                      ansible_variable: 'launch_start_time'
                  launch-end-time:
                      type: Value
                      help: Override the launch ending time instead of using current time as default.
                      ansible_variable: 'launch_end_time'
                  ignore-skipped-tests:
                      type: Bool
                      help: Ignore skipped tests and don't publish them to Reportportal at all
                      default: false
                  allow-empty-launches:
                      type: Bool
                      help: |
                        Whether or not to allow creation of empty launches
                        (no results) in case no XML junit reports are found
                      default: true
                  launch-id-dir:
                      type: Value
                      help: |
                        Path to a directory that will contain files with the ID
                        and the UUID of the newly created launch
                  post-validations:
                      type: Bool
                      help: |
                        Whether or nor to run some validation task after
                        performing launch operations
                      default: true

            - title: tasks
              options:
                  import:
                      type: Bool
                      help: |
                        Execute import tasks using custom ansible library
                        to import test results to ReportPortal
                      default: false
                  api-import:
                      type: Bool
                      help: |
                        Execute import tasks using reportportal import API
                        to import test results to ReportPortal
                      default: false
                  analyze:
                      type: Bool
                      help: Anazlyze failures of build (TBD)
                      default: false
                  dashboard2email:
                      type: Bool
                      help: Send a Report Portal Dashboard as an email
                      default: false
            - title: Jenkins Job Metadata
              options:
                  archive-import-path:
                      type: ListValue
                      default: "{{ inventory_dir }}/tempest_results/tempest-results-*.xml"
                      help: Pattern for the path location of test xml results
                  archive-dest-path:
                      type: Value
                      default: "{{ inventory_dir }}"
                      help: Directory location for archived zip of test results xmls
                  archive-exclude-path:
                      type: ListValue
                      default: "{{ inventory_dir }}/tempest_results/tempest-results-none*.xml"
                      help: Pattern for the path location of exluded test xml results

            - title: Jenkins Job Metadata
              options:
                  jenkins-domain:
                      type: Value
                      help: Domain of jenkins to add as meta data to results
                      required_when: "import == True"
                  jenkins-user-name:
                      type: Value
                      default: Jenkins
                      help: Current jenkins user which executed the job
                  jenkins-job-name:
                      type: Value
                      help: Jenkins Job name
                      required_when: "import == True"
                  jenkins-build-id:
                      type: Value
                      help: Jenkins build ID

            - title: dashboard2email params
              options:
                  vnc_password:
                      type: Value
                      help: Password VNC server will be protected with
                      required_when: "dashboard2email == True"
                  email_server_name:
                      type: Value
                      help: Hostname or IP of smtp server
                      required_when: "dashboard2email == True"
                  email_server_port:
                      type: Value
                      help: Port of smtp server
                      required_when: "dashboard2email == True"
                  email_from:
                      type: Value
                      help: Email address from which to send dashboard2email
                      required_when: "dashboard2email == True"
                  email_to:
                      type: Value
                      help: Email address to send dashboard2email to
                      required_when: "dashboard2email == True"
                  email_subject:
                      type: Value
                      help: Subject of dashboard2email
                  email_body:
                      type: Value
                      help: Body of dashboard2email
