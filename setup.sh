#!/bin/bash
#

if [ "$EUID" -ne 0 ]; then
    printf "Please run as root with \"sudo ./setup.sh\"\n";
    exit
fi

INSTALL_DIRECTORY=$( cd "$( dirname "${BASH_SOURCE[0]}" )/" && pwd -P )
cd $INSTALL_DIRECTORY

printf "Installing Mycodo\n"

printf "#### Setting up folders, files, and permissions.\n"
if [ -f $INSTALL_DIRECTORY/mycodo/scripts/update_mycodo.sh ]; then
    $INSTALL_DIRECTORY/mycodo/scripts/update_mycodo.sh upgrade-packages &&
    $INSTALL_DIRECTORY/mycodo/scripts/update_mycodo.sh setup &&
    $INSTALL_DIRECTORY/mycodo/scripts/update_mycodo.sh initialize &&
    printf "#### Mycodo successfully installed\n"
    read -r -p "You need to reboot to complete the installation. Reboot now? [y/n] " response
    if [[ $response =~ ^([yY][eE][sS]|[yY])$ ]]; then
        shutdown now -r
    fi
else
    printf "Error: $INSTALL_DIRECTORY/mycodo/scripts/update_mycodo.sh not found\n"
fi
