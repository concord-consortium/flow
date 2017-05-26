# Flow

This is the Manylabs data flow client program that runs on a local computer (e.g. Raspberry Pi).

## Requirements 

### Flow to Flow-ble Integration Setup 

Note: for flow service side of integration, only pip2 install below is needed.

Also see flow-ble/README.md

Setup MQTT:

```bash
sudo apt-get install mosquitto mosquitto-clients
# install mqtt python library for python2 and python3
sudo pip2 install paho-mqtt
sudo pip3 install paho-mqtt
```

Note: if pip3 fails, you may need to do the following update:

```bash
sudo pip3 install --upgrade setuptools
```

### Store Database Setup
 
Currently, store will be disabled if influxdb service is not running or influxdb Python
library is not installed.

The instructions below uses the latest influxdb .deb package for arm binaries available as of 5/25/2017.
This should be updated as influxdb becomes part of standard raspian distribution.
See https://portal.influxdata.com/downloads "Standalone Linux Binaries (ARM)"

To install influxdb service and library:

```bash
mkdir ~/download
cd ~/download
wget https://dl.influxdata.com/influxdb/releases/influxdb_1.2.4_amd64.deb
dpkg -i influxdb_1.2.4_armhf.deb

# install Python library
sudo pip2 install influxdb
```
