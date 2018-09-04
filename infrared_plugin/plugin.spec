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
                  port:
                      type: Value
                      help: ReportPortal URL port.
                      required: yes
                  project-name:
                      type: Value
                      help: Reportportal project name to push results to.
                      required: yes

            - title: ReportPortal Configuration
              options:
                  launch-id:
                      type: Value
                      help: ID of a launch.
                  launch-tags:
                      type: ListValue
                      help: Tags to be applied to a specified launch.
                      default: ''
                  launch-description:
                      type: Value
                      help: Description to be added to a specified launch.
                      default: ''
            - title: tasks
              options:
                  import:
                      type: Bool
                      help: Execute import tasks to import test results to ReportPortal
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
