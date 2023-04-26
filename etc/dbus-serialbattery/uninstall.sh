#!/bin/bash

# remove comment for easier troubleshooting
#set -x

# handle read only mounts
sh /opt/victronenergy/swupdate-scripts/remount-rw.sh

# remove files, don't use variables here, since on an error the whole /opt/victronenergy gets deleted
rm -f /data/conf/serial-starter.d/dbus-serialbattery.conf
rm -rf /opt/victronenergy/service/dbus-serialbattery
rm -rf /opt/victronenergy/service-templates/dbus-serialbattery
rm -rf /opt/victronenergy/dbus-serialbattery
rm -rf /service/dbus-blebattery-*

# kill if running
pkill -f "python .*/dbus-serialbattery.py"

# remove install-script from rc.local
sed -i "/sh \/data\/etc\/dbus-serialbattery\/reinstalllocal.sh/d" /data/rc.local
sed -i "/sh \/data\/etc\/dbus-serialbattery\/installble.sh/d" /data/rc.local

# remove cronjob
sed -i "/5 0,12 \* \* \* \/etc\/init.d\/bluetooth restart/d" /var/spool/cron/root

# uninstall modules
read -r -p "Do you also want to uninstall bleak, python3-pip and python3-modules? If you don't know select y. [Y/n] " response
echo
response=${response,,} # tolower
if [[ $response =~ ^(y| ) ]] || [[ -z $response ]]; then
    echo "Uninstalling modules..."
    pip3 uninstall bleak
    opkg remove python3-pip python3-modules
    echo "done."
    echo
fi
