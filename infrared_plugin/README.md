Installation with InfraRed
-----------------------------

In order to install the plugin, the following InfraRed command should be used:

    infrared plugin add https://github.com/rhos-infra/reportportal.git --src-path infrared_plugin

After successfully adding the plugin a Symlink to roles path should be created:

    cd plugins/reportportal/infrared_plugin
    mkdir roles
    ln -s ../../../reportportal roles/reportportal