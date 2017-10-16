#!/bin/bash
#
# Start flow.py client
#
export PYTHONPATH=/home/pi/rhizo

CONFIG_FILE=config.hjson

cd /home/pi/flow

if [ ! -f $CONFIG_FILE ]; then
    cp sample_settings/$CONFIG_FILE $CONFIG_FILE
fi

python flow.py
read -rsp $'Press enter to continue...\n'
