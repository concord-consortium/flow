#!/bin/bash
#
# Start flow.py client
#
export PYTHONPATH=/home/pi/rhizo
cd /home/pi/flow
python flow.py
read -rsp $'Press enter to continue...\n'
