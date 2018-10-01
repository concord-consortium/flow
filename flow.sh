#!/bin/bash
#
# Start flow.py client
#
export PYTHONPATH=/home/pi/rhizo:/home/pi/sensaur
cd /home/pi/flow
python flow.py
read -rsp $'Press enter to continue...\n'
