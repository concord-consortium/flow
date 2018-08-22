# Flow

_This material is based upon work supported by the National Science Foundation under Grant No. DRL-1640054. Any opinions, findings, and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect the views of the National Science Foundation._

Developed by the Concord Consortium in collaboration with Manylabs, the data flow client program
runs on a local computer (e.g. Raspberry Pi).

## Overview

The flow program receives data from sensors and can send outputs to actuators. It can execute
a data flow diagram that describes operations that transform the inputs to outputs. It can
also store sensor data on a server for later viewing.

The flow program uses the [rhizo](https://github.com/rhizolab/rhizo) client library to
communicate with a [rhizo-server](https://github.com/rhizolab/rhizo-server) machine.

### Diagrams

The flow program can run one diagram at a time. A diagram is made up of a collection of blocks,
which can include inputs, outputs, and filters. At each point in time, each block has either a
single value (typically a number or image) or an undefined value. The flow program propagates
values through the diagram.

Diagrams are currently stored as JSON files in the local file system. The flow program can
load, save, rename, and delete diagrams.

### Data Storage

The user can instruct the flow program to begin recording data. Currently recorded data is sent
to the server at a user-specified sampling rate (e.g. once every 5 seconds).
Any block connected to a data storage block is stored.

Data is stored as sequence objects on the server. If a sequence does not exist for an input block,
the flow program will create one. Currently data is stored using PUT requests made via the rhizo
client library.

### Messages

The flow program communicates with the flow browser app via messages. The browser can send a message
to the rhizo-server via a websocket and the server will then send that message to the flow program.
Code in the rhizo client library receives the message and then passes it along to the flow program's
message handler (in `flow/flow.py`).

Message types recognized by the flow program include:

*   request a list of currently attached hardware devices
*   request a list of types of blocks supported by the flow program
*   list/load/save/rename/delete diagrams (stored in local file system)
*   start/stop diagram execution
*   start/stop data recording
*   rename a block in the current diagram
*   testing/diagnostic messages

Each time the flow program computes a new set of values for the blocks in a diagram, it sends the
updated values to the browser via a message. It stops sending these update messages if it hasn't received
any messages from the browser recently (so as to reduce unnecessary network traffic).

## Optional/Experimental Components

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
