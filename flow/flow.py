# standard python imports
import os
import time
import json
import logging
import datetime
import subprocess
from dateutil.parser import parse
import numbers

# external imports
import hjson
import gevent
from PIL import Image
from rhizo.main import c
from rhizo.extensions.camera import encode_image
import requests

# our own imports
from sim_devices import simulate, add_sim_sensor, add_sim_actuator, remove_sim_device
from diagram_storage import list_diagrams, load_diagram, save_diagram, rename_diagram, delete_diagram
from diagram import Diagram

from git_tools                          import git_base_command

from commands.command                   import Command
from commands.list_versions_command     import ListVersionsCommand
from commands.download_software_command import DownloadSoftwareCommand
from commands.update_software_command   import UpdateSoftwareCommand

#
# Check if we can include IP addresses in our status
#
include_network_status = True
try:
    from netifaces import interfaces, ifaddresses, AF_INET
except ImportError:
    include_network_status = False

include_version_info = True
try:
    import subprocess
except ImportError:
    include_version_info = False

# threshold for idle use messages indicating to stop sending update messages
IDLE_STOP_UPDATE_THRESHOLD = 5 * 60.0

# The Flow class holds the state and control code for the data flow client program (running on a RasPi or similar).
class Flow(object):

    #
    # Values for set_operational_status
    #
    OP_STATUS_READY     = "READY"
    OP_STATUS_UPDATING  = "UPDATING"


    #
    # Get version info
    #
    FLOW_VERSION = None

    if include_version_info:

        try:
            #
            # Track version with git tags.
            # If this head is tagged, then this returns the tag name.
            # Otherwise this returns a short hash of the head.
            #
            FLOW_VERSION = subprocess.check_output( git_base_command() +
                                                    [   'describe',
                                                        '--tags',
                                                        '--always'  ]).rstrip()

        except Exception as err:
            FLOW_VERSION = "unknown"

        logging.debug("Found flow version '%s'" % (FLOW_VERSION))


    def __init__(self):
        self.diagram = None  # the currently running diagram (if any)
        # used to perform always save history for each non-sim sensor
        #   at sensor raw reading interval
        self.integ_test = False
        self.publisher = None
        self.store = None
        self.sensaur_hub = None
        self.last_user_message_time = None  # the last user message time (if any)
        self.last_camera_store_time = None  # the last camera sequence update time (if any)
        self.last_record_timestamp = None  # datetime object of last values recorded to long-term storage
        self.recording_interval = None  # number of seconds between storing values in long-term storage
        self.run_name = "Noname"  # name of run for which recording is being saved
        self.sequence_names = {}  # a dictionary mapping block IDs to sequence names (when recording to server)

        c.add_message_handler(self)  # register to receive messages from server/websocket
        c.auto_devices.add_input_handler(self)

        # if using sensaur system, initialize it
        if c.config.get('enable_sensaur') and c.config.get('sensaur_port'):
            import sensaur
            self.sensaur_hub = sensaur.Hub(c.config['sensaur_port'])
            self.sensaur_hub.add_input_handler(self)
        else:
            self.sensaur_hub = None

        # load last diagram on startup
        # TODO: decide to use this or self.store("diagram"...) below
        if c.config.get('startup_diagram', ''):
            name = c.config.startup_diagram
            diagram_spec = load_diagram(name)
            logging.debug("Flow.__init__: loading diagram: %s" % name)
            self.diagram = Diagram(name, diagram_spec)


        # call init functions. if they fail, mqtt, store resp. will be noop
        if c.config.get('enable_ble', False):
            self.init_mqtt()
        else:
            logging.debug("MQTT and BLE disabled.")

        if c.config.get('enable_store', False):
            self.init_store()
            # if store enabled, restore recording_interval
            rs = self.store.query("select * from run order by time desc limit 2")
            points = list(rs.get_points())
            logging.debug("Flow.__init__: run points: %s" % points)
            if points:
                point = points[0]
                if point.get("action") == "start":
                    logging.info("Flow.__init__: loading last run info: %s" % point)
                    # last action was start, not stop: load name and interval
                    self.recording_interval = int(point.get("value"))
                    self.run_name = point.get("name")
            # sample data:
            # points: [{u'count': 60, u'name': u'light', u'pin': u'2671', u'min': 242,
            #  u'max': 245, u'time': u'2017-06-16T20:42:00Z', u'mean': 244.8}, ...

            # if diagram not loaded from hardcoded config, load from influxdb 'diagram' measurement
            if not self.diagram:
                rs = self.store.query("select * from diagram order by time desc limit 2")
                points = list(rs.get_points())
                logging.debug("Flow.__init__: diagram points: %s" % points)
                if points:
                    point = points[0]
                    if point.get("action") == "start":
                        #logging.info("Flow.__init__: loading last diagram: %s" % point)
                        name = point.get("name")
                        try:
                            diagram_spec = load_diagram(name)
                            logging.debug("Flow.__init__: loading diagram: %s" % name)
                            self.diagram = Diagram(name, diagram_spec)
                        except Exception as err:
                            logging.warning("Flow.__init__: can't load diagram %s: %s" % (name, err))
        else:
            logging.debug("Store disabled.")


        self.operational_status     = self.OP_STATUS_READY

        self.available_versions     = []    # Available software versions

        self.username               = None  # User currently recording

        self.recording_location     = None  # Folder path on server of
                                            # named dataset

        self.device_check_greenlet  = None  # The recording greenlet.

        self.sensor_data_latest     = {}    # For the sensor data greenlet,
                                            # keep the last input_handler
                                            # value received for each physical
                                            # device so that we can return
                                            # sensor data to the user without
                                            # having a diagram loaded.

        self.sensor_data_greenlet   = None  # Greenlet for sending sensor
                                            # data over the websocket.

        self.firebase                      = None  # Holds parameters from flow_server::firebase_init message
        self.firebase_sensor_data_greenlet = None # Greenlet for sending sensor data to Firebase.


    # MQTT integration
    def init_mqtt(self):
        """Initialize mqtt."""
        try:
            from mqttclient import MqttPublisher
            #TODO: load mq_topic from config. It has to be the same
            # --- as in gattserver/hpserver.py
            mq_topic = "flow/ble"
            self.publisher = MqttPublisher(mq_topic)
            self.publisher.start()
            #print("MQTT Initialized.")
            logging.info("MQTT Initialized.")
        except:
            logging.error("Can't initialize MQTT. Probably some components not installed. MQTT publish will be disabled.")
            #print("Can't initialize MQTT. Probably some components not installed. MQTT publish will be disabled.")

    # store integration
    def init_store(self):
        """Initialize store."""
        try:
            from influxstore import Store
            # TODO load pin for this device
            my_pin = '2671'
            # open store to flow database
            self.store = Store(database="flow", pin=my_pin)
            logging.info("Influxdb store Initialized.")
        except Exception as err:
            logging.error("Can't initialize store. Probably influxdb library not installed or influxdb not running. Store will be disabled: %s" % \
              err)

    #
    # Set operational status
    #
    def set_operational_status(self, status):
        self.operational_status = status

    #
    # Get operational status
    #
    def get_operational_status(self):
        return self.operational_status

    # run the current diagram (if any); this is the main loop of the flow program
    def start(self):

        # launch a greenlet to send watchdog messages to server
        gevent.spawn(self.send_watchdog)

        # launch sensaur greenlets if enabled
        if self.sensaur_hub:
            self.sensaur_hub.start_greenlets()

        # loop forever
        timestamp = datetime.datetime.utcnow().replace(microsecond=0)
        while True:

            # if the current time is greater than our target timestamp, run our processing
            if datetime.datetime.utcnow() > timestamp:
                if self.diagram:
                    self.update_diagram_and_send_values(timestamp)

                # the processing could have taken more than a second, so update the target timestamp as many times as needed (by an integer amount) to be in the future
                # alternative: could compute timedelta and do some math to do this in a single step
                while timestamp < datetime.datetime.utcnow():
                    timestamp += datetime.timedelta(seconds=1)

            # sleep until it is time to do another update
            c.sleep(0.1)

    # updates the current diagram and sends values to server and external hardware;
    # this function should be called once a second;
    # timestamp should always be 1 second after the last timestamp (and should be an even number of seconds)
    def update_diagram_and_send_values(self, timestamp):

        # update diagram values
        self.update_camera_blocks()
        self.diagram.update()

        # send values to server and actuators
        values = {}
        for block in self.diagram.blocks:
            value = None
            #logging.debug('flow.start loop: block=%s' % block)
            if block.output_type == 'i':  # only send camera/image updates if recent message from user
                if self.last_user_message_time and time.time() < self.last_user_message_time + 300:
                    value = block.value
            else:
                if block.value is not None:
                    format = '%' + '.%df' % block.decimal_places
                    value = format % block.value
            values[block.id] = value

            # send values to actuators
            if not block.output_type:
                device = self.find_device(block.name)  # fix(later): does this still work if we rename a block?
                if device and device.dir == 'out':
                    try:
                        value = int(block.value)
                    except:
                        value = None
                    if value is not None:
                        if hasattr(device, 'send_command'):
                            device.send_command('set %d' % value)  # for auto_devices devices
                        else:
                            self.sensaur_hub.set_output_value(device, value)  # for sensaur components

        #logging.debug('flow.start loop: values=%s' % values)
        if self.last_user_message_time and (time.time() - self.last_user_message_time < IDLE_STOP_UPDATE_THRESHOLD):
            #logging.debug("IDLE_STOP_UPDATE_THRESHOLD passed")
            self.send_message('update_diagram', {'values': values})
        else:
            pass
            #logging.debug("IDLE_STOP_UPDATE_THRESHOLD failed")

        # send sequence values
        if self.recording_interval and ((self.last_record_timestamp is None) or timestamp >= self.last_record_timestamp + datetime.timedelta(seconds = self.recording_interval)):
            data_storage_block = None
            for block in self.diagram.blocks:
                if block.type == 'data storage':
                    data_storage_block = block
                    break
            if data_storage_block:  # if data storage block is defined, store everything that feeds into it
                record_blocks = [b for b in data_storage_block.sources]
                self.record_data(record_blocks, timestamp)
                self.last_record_timestamp = timestamp

    def calc_auto_interval(self, start, end):
        """Calculate automatic interval.
          About 120 records should fit in start/end range.

          :param start: start of history range for which interval is calculated
          :param end: end of history range for which interval is calculated
          :return: string compatible with influxdb group by interval, e.g. 5s, 1m, 60m
                   or None if auto interval is < 1m and no grouping needs to be done
        """
        ret = None
        try:
            start = parse(start)
            end = parse(end)
            diff = end - start
            #interval_diff = diff/120
            total_seconds = diff.total_seconds()
            if total_seconds <= 600:
                # < 10m
                ret = None
            elif total_seconds <= 3600:
                # < 1h and < 10m
                ret = "1m"
            elif total_seconds <= 24*3600:
                # > 1h and < 1d
                # 48 records max
                ret = "30m"
            elif total_seconds <= 7*24*3600:
                # > 1d and < 7d
                # 84 records max
                ret = "4h"
            elif total_seconds <= 30*24*3600:
                # > 7d and < 30d
                # 120 records max
                ret = "8h"
        except Exception as err:
            # Can't parse: return default (None)
            ret = None
        return ret

    #
    # handle messages from server (sent via websocket)
    #
    def handle_message(self, type, params):

        logging.debug('handle_message: %s %s' % (type, params))

        #
        # For any messages that choose to implement the command interface,
        # they can be instantiated using their message type as key.
        #
        command_class_dict = {
            'download_software_updates':    DownloadSoftwareCommand,
            'list_software_versions':       ListVersionsCommand,
            'update_software_version':      UpdateSoftwareCommand }

        #
        # Messages allowed when in recording mode
        #
        allowed_when_recording = [  'stop_recording',
                                    'stop_diagram',
                                    'list_diagrams',
                                    'request_status',
                                    'rename_diagram',
                                    'delete_diagram',
                                    'flow_server::firebase_init'  ]

        #
        # Restrict allowed operations while recording.
        # Do not allow modification of the running diagram while
        # recording.
        #
        if self.recording_interval is not None:
            if not type in allowed_when_recording:
                logging.debug("Message %s not allowed while recording." % (type))
                username = self.username
                diagram_name = None
                if self.diagram:
                    diagram_name = self.diagram.name

                self.send_message(type + '_response',
                        {   'success':  False,
                            'error':    'recording_in_progress',
                            'data':     {   'username': username,
                                            'diagram':  diagram_name },
                            'message':  'Cannot perform operation %s while controller is recording.' % (type)
                        })
                self.last_user_message_time = time.time()
                return True

        used = True
        if type == 'list_devices':
            print 'list_devices'
            for device in self.device_list():
                self.send_message('device_added', device.as_dict())

        elif type == 'history':
            self.send_history(params)
        elif type == 'request_block_types':
            block_types = hjson.loads(open('block_types.hjson').read())
            self.send_message('block_types', block_types)
        elif type == 'list_diagrams':
            self.send_message('diagram_list', {'diagrams': list_diagrams()})
        elif type == 'save_diagram':
            save_diagram(params['name'], params['diagram'])

            logging.debug("Sending save_diagram_response")
            self.send_message(  'save_diagram_response',
                                {   'success': True,
                                    'message': "Saved diagram: %s" % (params['name'])
                                })

        elif type == 'rename_diagram':

            #
            # Do not allow renaming of recording diagram
            #
            if self.recording_interval is not None:
                if params['old_name'] == self.diagram.name:

                    self.send_message(
                                'rename_diagram_response',
                                {   'success': False,
                                    'message': "Cannot rename diagram while recording"
                                })
                    return

            rename_diagram(params['old_name'], params['new_name'])
            self.send_message(
                                'rename_diagram_response',
                                {   'success': True,
                                    'message': "Diagram renamed"
                                })

        elif type == 'delete_diagram':

            #
            # Do not allow deleting of recording diagram
            #
            if self.recording_interval is not None:
                if params['name'] == self.diagram.name:

                    self.send_message(
                                'delete_diagram_response',
                                {   'success': False,
                                    'message': "Cannot delete diagram while recording"
                                })
                    return

            delete_diagram(params['name'])

            self.send_message(
                                'delete_diagram_response',
                                {   'success': True,
                                    'message': "Diagram deleted"
                                })


        elif type == 'set_diagram':

            self.set_diagram(params)

        elif type == 'start_diagram':  # start a diagram running on the controller; this will stop any diagram that is already running

            logging.debug("handle_message: start_diagram - loading diagram: %s" % params['name'])
            diagram_spec = load_diagram(params['name'])
            self.diagram = Diagram(params['name'], diagram_spec)
            #local_config = hjson.loads(open('local.hjson').read())  # save name of diagram to load when start script next time
            #local_config['startup_diagram'] = params['name']
            #open('local.hjson', 'w').write(hjson.dumps(local_config))
            if self.store:
                self.store.save('diagram', params['name'], 0, {'action': 'start'})

            self.send_message(  'start_diagram_response',
                                {   'success': True,
                                    'message': "Started diagram: %s" % (params['name'])
                                })


        elif type == 'stop_diagram':

            #
            # Need to update the metadata in the recording location
            # indicating that we are no longer recording to that location.
            # Note if a controller dies while recording, the metadata
            # will still indicate 'recording: True', so someone might stop
            # a recording (to update the metadata to set 'recording: False')
            # even though the controller might no longer be recording to that
            # location. There should probably be a better way to handle this.
            #
            stop_location = params.get('stop_location')
            if stop_location is None:
                stop_location = self.recording_location

            #
            # Set this recording as done.
            #
            if stop_location:
                if not stop_location.startswith('/'):
                    stop_location = '/' + stop_location

                metadata = c.resources.read_file(stop_location + "/metadata")
                if metadata is not None:
                    metadata = json.loads(metadata)
                    metadata['recording'] = False
                    metadata['end_time'] = '%s' % (datetime.datetime.utcnow())
                    c.resources.write_file(
                        stop_location + "/metadata",
                        json.dumps(metadata) )
                else:
                    c.resources.write_file(
                        stop_location + "/metadata",
                        json.dumps({    'controller_path': c.path_on_server(),
                                        'recording': False,
                                        'recording_interval': self.recording_interval }))
            #
            # Stop recording if in progress.
            # Remove the currently running diagram program.
            # Remove the currently set user.
            #
            self.recording_interval = None
            self.diagram            = None
            self.username           = None

            if self.recording_location != stop_location:
                #
                # We are not really recording to the location we
                # have been asked to "stop" so just update the
                # above metadata and continue.
                #
                self.send_message(  type + '_response',
                                    {   'success': True,
                                        'message': "This controller was no longer recording at that location, but the recording has been marked as stopped."
                                    })
                return

            self.recording_location = None

            self.send_message(  type + '_response',
                                {   'success': True,
                                    'message': "Program stopped"
                                })
            #
            # Ensure latest status reflects that this controller is
            # not recording.
            #
            self.send_status()


        elif type == 'start_recording':

            #
            # Allow 'set_diagram' and 'start_recording' to be
            # an atomic operation.
            # Caller can specify diagram and username in params.
            #
            if set(('diagram', 'username')) <= set(params):
                self.set_diagram(params)

            metadata = {
                'controller_path': c.path_on_server(),
                'controller_name': self.controller_name(),
                'program':  self.diagram.diagram_spec,
            }

            # check for data storage block
            data_storage_block = None
            for block in self.diagram.blocks:
                if block.type == 'data storage':
                    data_storage_block = block
                    break

            # if data storage block, get recording info from it
            if data_storage_block:
                dataset_displayedName = data_storage_block.read_param(data_storage_block.params, 'dataset_location', 'data')
                self.recording_location = params['recording_location']
                self.recording_interval = data_storage_block.read_param(data_storage_block.params, 'recording_interval', 1)
                self.sequence_names = data_storage_block.read_param(data_storage_block.params, 'sequence_names', 'data')
                metadata_location = self.recording_location
                metadata['displayedName'] = dataset_displayedName
                metadata['recording'] = True
                metadata['start_time'] = '%s' % (datetime.datetime.utcnow())  # TODO: should use ISO string
                metadata['recording_location'] = self.recording_location
                metadata['recording_user'] = self.username
                metadata['recording_interval'] = self.recording_interval

            # otherwise, we still want to create a metadata file (using the recording location specified with this message)
            else:
                metadata['recording'] = True  # note: not really recording; just need this to work with current front-end code
                metadata['is_empty'] = True
                self.recording_location = None
                self.recording_interval = None
                self.sequence_names = []
                metadata_location = params['recording_location']  # TODO: rethink this

            #
            # Create metadata file.
            #
            logging.info("Creating sequences...")
            c.resources.create_folder(metadata_location)
            c.resources.write_file(metadata_location + "/metadata", json.dumps(metadata))

            # Create sequences for blocks
            if data_storage_block:
                record_blocks = [b for b in data_storage_block.sources]
                self.create_sequences(record_blocks)

            self.send_message('start_recording_response',
                                {   'success': True,
                                    'message': "Recording started."
                                })

            #
            # Ensure latest status reflects that this controller is
            # recording.
            #
            self.send_status()


        elif type == 'stop_recording':
            logging.info('stop recording data')

            if self.store:
                # save stop for current run
                if self.recording_interval:
                    self.store.save('run', self.run_name, self.recording_interval, {'action': 'stop'})
                else:
                    logging.info('stop recording data not saved (recording_interval none)')
            self.recording_interval = None
            self.recording_location = None
            if self.device_check_greenlet:
                self.device_check_greenlet.kill()

            self.send_message(  type + '_response',
                                {   'success': True,
                                    'message': "Recording stopped."
                                })

        elif type == 'send_sensor_data':

            if self.sensor_data_greenlet is not None:
                return

            stoptime = params.get('stoptime')
            if stoptime is None:
                stoptime = 60

            self.sensor_data_greenlet = gevent.spawn(   self.send_sensor_data,
                                                        stoptime )

            self.send_message(  type + '_response',
                                {   'success': True,
                                    'message': "Sending sensor data."
                                })


        elif type == 'rename_block':
            old_name = params['old_name']
            new_name = params['new_name']
            device = self.find_device(old_name)
            device.name = new_name
            rename_sequence(c.path_on_server(), old_name, new_name)  # change sequence name on server

        elif type == 'update_actuator':
            name = params['name']
            value = params['value']
            device = c.auto_devices.find_device(name)
            if device:
                device.send_command('set %s' % value)
            elif self.sensaur_hub:
                component = self.sensaur_hub.find_component(name)
                if component:
                    self.sensaur_hub.set_output_value(component, value)

        elif type == 'add_camera':
            self.add_camera()
        elif type == 'add_sim_sensor':
            add_sim_sensor()
        elif type == 'add_sim_actuator':
            add_sim_actuator()
        elif type == 'remove_sim_device':
            remove_sim_device()
        elif type == 'request_status':
            self.send_status()

        elif type in [  'download_software_updates',
                        'list_software_versions',
                        'update_software_version' ]:

            class_  = command_class_dict[type]
            cmd     = class_(self, type, params)
            cmd.exec_cmd()

        elif type == 'flow_server::firebase_init':
            self.firebase = params
            send_sensor_data = self.firebase['send_sensor_data']
            if send_sensor_data and send_sensor_data['enabled'] and c.config.get('firebase_send_sensor_data', True):
                if self.firebase_sensor_data_greenlet is not None:
                    self.firebase_sensor_data_greenlet.kill()
                self.firebase_sensor_data_greenlet = gevent.spawn(self.firebase_send_sensor_data, self.firebase, send_sensor_data)

        else:
            used = False

        # keep track of last message from web interface
        if used:
            self.last_user_message_time = time.time()
        return used

    # a wrapper used to send messages to server or BLE
    def send_message(self, type, parameters):
        """Send message to websocket and/or ble.
        Currently, we support two modes:
         - websocket
         - websocket plus ble

        if elable_ble is set in config, we send to both ble (via mqtt) and websocket (via c._send_message).
        Otherwise, we send to websocket only via c.send_message
        """
        #logging.debug('send_message type=%s' % type)

        #
        # Add our folder name to the params so that the client knows
        # which controller is responding in case they have
        # sent messages to multiple controllers.
        #
        own_path = c.path_on_server()
        parameters['src_folder'] = own_path

        if c.config.get('enable_ble', False) and self.publisher:
            # update_sequence not needed by ble, only by store
            if type != "update_sequence":
                jsonobj = {"type": type, "parameters": parameters}
                #jsonmsg = '{"type":"sensor_update","parameters":{"values":[388.0],"name":"light"}}'
                jsonmsg = json.dumps(jsonobj)
                #logging.debug('mqtt published : %s' % jsonmsg)
                #if not self.integ_test:
                self.publisher.publish(jsonmsg)
            # also send message to websocket
            c.send_message(type, parameters)
        else:
            # send message to websocket
            c.send_message(type, parameters)

    #
    # Handle an incoming value from a sensor device (connected via USB)
    #
    # Duplicate device types append a space followed by an integer
    # starting at 2. E.g.:
    #
    # "CO2"
    # "CO2 2"
    # "humidity"
    # "humidity 2"
    #
    # How do we map these?
    #
    def handle_input(self, device_or_name, value):

        # get the device name
        # the auto_devices code provides a name; the senaur code provides a device object
        if hasattr(device_or_name, 'name'):
            name = device_or_name.name
            values = [value]  # the sensaur system just sends a single value at a time
        else:
            name = device_or_name
            values = value  # the auto_devices system provides a list of values for one device

        # logging.debug('input_handler: name=%s, values[0]=%s' % (name, values[0]))
        # ---- start of send_message replacement (store and ble test without diagram open)
        if self.integ_test:
            if self.store:
                value = float(values[0])
                try:
                    self.store.save('sensor', name, value)
                except Exception as err:
                    logging.error("store.save error: %s" % err)
            # simulate update_diagram when it was not requested by flow-server
            #  i.e. when flow-server is not reachable after flow restart
            #if self.publisher:
            #    jsonobj = {"type": "update_diagram", "parameters": {'values': { '1': value}}}
            #    jsonmsg = json.dumps(jsonobj)
            #    #logging.debug('mqtt published : %s' % jsonmsg)
            #    self.publisher.publish(jsonmsg)
        # ---- end of of send_message replacement

        if self.diagram:
            block = self.diagram.find_block_by_name(name)
            if block:
                block.decimal_places = block.compute_decimal_places(values[0])
                block.value = float(values[0])

        #
        # Store last read sensor data associated with a physical sensor.
        #
        now     = datetime.datetime.utcnow()
        value   = float(values[0])
        self.sensor_data_latest[name] = (now, value)

    # record data by sending it to the server and/or storing it locally
    def record_data(self, blocks, timestamp):

        # publish to recording queue to be saved by storage service or save directly
        # store block_name and value into 'sensor' measurement
        # perform store only if store has been initialized properly
        if not self.integ_test:
            if self.store:
                for block in blocks:
                    try:
                        logging.debug("record_data: %s=%s" % (block.name, block.value))
                        self.store.save('sensor', block.name, block.value)
                    except Exception as err:
                        logging.error("store.save error: %s" % err)

        # store blocks on server
        sequence_prefix = self.recording_location + '/'
        values = {}
        for b in blocks:
            id_str = str(b.id)
            if id_str in self.sequence_names:
                seq_name = sequence_prefix + self.sequence_names[id_str]
                values[seq_name] = b.value
        logging.debug('c.update_sequences %s' % (values))
        if values:
            c.update_sequences(values, timestamp)

    # send locally recorded time series data to browser
    def send_history(self, params):

        # history is currently only used for sending local history
        #  over ble
        #  Sample parameters for type history: {u'count': 100000, u'start_timestamp': u'2017-06-15T23:50:19.567Z',
        #    u'name': u'temperature', u'end_timestamp': u'2017-06-16T00:00:19.567Z'}
        history = []
        if self.store:
            name = params.get("name")
            start = params.get("start_timestamp")
            end = params.get("end_timestamp")
            count = params.get("count")
            # auto interval allows for automatic adjustment of history timestamp interval
            #   so that it fits into ble packet (< 120 records)
            auto_interval = params.get("auto_interval")
            interval = None
            if auto_interval is None:
                auto_interval = True
            if auto_interval:
                #
                interval = self.calc_auto_interval(start, end)
                #
            try:
                if interval:
                    query = \
                      """SELECT mean(mean) from sensor_mean where "name"='%s' and time > '%s' and time <= '%s' group by time(%s) limit %s""" % \
                      (name, start, end, interval, count)
                else:
                    query = \
                      """SELECT mean from sensor_mean where "name"='%s' and time > '%s' and time <= '%s' limit %s""" % \
                      (name, start, end, count)
                logging.debug("interval=%s, query=%s" % (interval, query))
                rs = self.store.query(query)

                # sample data:
                # points: [{u'count': 60, u'name': u'light', u'pin': u'2671', u'min': 242,
                #  u'max': 245, u'time': u'2017-06-16T20:42:00Z', u'mean': 244.8}, ...

                points = list(rs.get_points())
                #logging.debug("%d points: first 10: %s" % (len(points), points[:10]))

                if c.config.get('enable_ble', False) and self.publisher:
                    # extract rounded numbers for 'mean' field
                    values = [round(x['mean'],2) if isinstance(x['mean'], numbers.Number) else x['mean']  for x in points]
                    timestamps = [x['time'] for x in points]
                    if not values:
                        values = [0,0]
                        timestamps = [start, end]
                    jsonobj = {"type": type, "parameters": { "name": name,
                      "values": values, "timestamps": timestamps }
                    }
                    #jsonmsg = '{"type":"sensor_update","parameters":{"values":[388.0],"name":"light"}}'
                    jsonmsg = json.dumps(jsonobj)
                    #logging.debug('mqtt published : %s' % jsonmsg)
                    self.publisher.publish(jsonmsg)
            except Exception as err:
                logging.error("store.query error: %s" % err)
        #self.send_message('history', {'values': history})

    #
    # send client info to server/browser
    #
    def send_status(self):

        #
        # Get IP info
        #
        ip_map = None

        if include_network_status:
            ip_map = {}
            for interface in interfaces():
                if interface == 'lo':
                    continue
                addresses = ifaddresses(interface)
                if AF_INET in addresses:
                    links = addresses[AF_INET]
                    for link in links:
                        ip_map[interface] = link['addr']

        if os.path.exists('/sys/class/net/wlan0/address'):
            mac_addr = subprocess.check_output(['cat', '/sys/class/net/wlan0/address']).strip()  # for raspi
        else:
            mac_addr = 'N/A'

        status = {
            'operational_status':   self.operational_status,
            'available_versions':   self.available_versions,
            'username':             self.username,
            'flow_version':         Flow.FLOW_VERSION,
            'lib_version':          c.VERSION + ' ' + c.BUILD,
            'device_count':         len(self.device_list()),
            'recording_interval':   self.recording_interval,
            'ip_addresses':         ip_map,
            'mac_address':          mac_addr,
        }

        if self.diagram:
            logging.debug("Setting name %s" % (self.diagram.name))
            status['current_diagram'] = self.diagram.name
        else:
            logging.debug("No diagram name to set.")
            status['current_diagram'] = None

        self.send_message('status', status)

        # update controller status table on server
        own_path = c.path_on_server()
        c.resources.send_request_to_server('PUT', '/api/v1/resources' + own_path, {'status': json.dumps(status)})

    # create sequences on server for the given blocks
    def create_sequences(self, blocks):

        # get list of existing sequences
        print('recording location: %s' % self.recording_location)
        file_infos = c.resources.list_files(self.recording_location, type = 'sequence')
        server_seqs = set([fi['name'] for fi in file_infos])
        print('server seqs: %s' % server_seqs)

        # create a sequence for each block (that doesn't already have a sequence)
        for block in blocks:
            id_str = str(block.id)
            if id_str in self.sequence_names:
                seq_name = self.sequence_names[id_str]
                if seq_name not in server_seqs:
                    device = self.find_device(block.name)
                    units = device.units if device else None
                    create_sequence(self.recording_location, seq_name, data_type=1, units=units)  # data_type 1 is numeric
                    server_seqs.add(block.name)

    # get sensor data
    def get_sensor_data(self):
        data = []
        for device in self.device_list():

            dict    = device.as_dict()
            name    = dict['name']
            value   = None

            if name in self.sensor_data_latest:
                (time, value) = self.sensor_data_latest[name]
                #
                # How to decide when a value is stale?
                # This might not be necessary since _auto_devices
                # removes the unplugged USB device...
                #
                now = datetime.datetime.utcnow()
                if time < now - datetime.timedelta(seconds=5):
                    value = None

            dict['value'] = value
            data.append(dict)

        # add timer blocks
        # TODO: rename send_sensor_data since we're adding timer data
        if self.diagram:
            for block in self.diagram.blocks:
                if block.type == 'timer':
                    d = {
                        'id': block.id,
                        'name': block.name,
                        'type': block.type,
                        'value': block.value,
                    }
                    data.append(d)

        return data

    # get list of devices
    def device_list(self):
        devices = c.auto_devices._auto_devices
        if self.sensaur_hub:
            if devices:  # handle this case separately, since it will be slow (making copies of lists) and unusual (only when have both old and new hardware attached at the same time)
                devices = devices + self.sensaur_hub.components  # note: a device is called a component in the sensaur system
            else:
                devices = self.sensaur_hub.components
        return devices

    # find a device by name; assumes each device has a unique name
    def find_device(self, name):
        device = c.auto_devices.find_device(name)
        if not device and self.sensaur_hub:
            device = self.sensaur_hub.find_component(name)  # note: a device is called a component in the sensaur system
        return device

    #
    # Send all sensor data to Firebase including sensor values
    #
    def firebase_send_sensor_data(self, firebase, send_sensor_data):
        started  = datetime.datetime.utcnow().replace(microsecond=0)
        interval = send_sensor_data["interval"]

        api_key = firebase["api_key"]
        google_auth_url = 'https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyCustomToken?key=%s' % (api_key)
        refresh_token_url = 'https://securetoken.googleapis.com/v1/token?key=%s' % (api_key)

        logging.debug("firebase_send_sensor_data start: %s, interval: %s" % (started, interval))

        # Enable https connection reuse to Firebase
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter())

        # Exchange the custom token for an id token
        post_succeeded = False;
        while not post_succeeded:
            try:
                r = session.post(google_auth_url, headers={'Content-Type': 'application/json'}, data = json.dumps({'token': firebase["token"], 'returnSecureToken': True}))
                if r.status_code != 200:
                    logging.error('ABORTING firebase_send_sensor_data thread!  POST to %s returned %s' % (google_auth_url, r.status_code))
                    return
                post_succeeded = True
            except Exception as err:
                logging.error("Session post error: %s" % (err))
                c.sleep(1)

        auth = r.json()
        id_token = auth["idToken"]
        refresh_token = auth["refreshToken"]
        expires_in = int(time.time()) + int(auth["expiresIn"])

        while True:
            try:
                # refresh token when there is 5 minutes left
                now = int(time.time())
                if now >= expires_in - (5*60):
                    logging.debug('Refreshing token')
                    r = session.post(refresh_token_url, headers={'Content-Type': 'application/json'}, data = json.dumps({'refresh_token': refresh_token, 'grant_type': 'refresh_token'}))
                    if r.status_code != 200:
                        logging.error('ABORTING firebase_send_sensor_data thread!  POST to %s returned %s' % (refresh_token_url, r.status_code))
                        return
                    refresh = r.json()
                    id_token = refresh["id_token"]
                    refresh_token = refresh["refresh_token"]
                    expires_in = int(time.time()) + int(refresh["expires_in"])

                # Get data
                data = self.get_sensor_data()
                timestamp = datetime.datetime.utcnow().isoformat() + "Z"

                # Send PUT request
                firebase_url = 'https://%s.firebaseio.com%s.json?auth=%s' % (firebase["project_id"], send_sensor_data["path"], id_token)
                r = session.put(firebase_url, data = json.dumps({'timestamp': timestamp, 'data': data}))
                if r.status_code == 200:
                    logging.debug('Sent %s to %s' % (data, firebase_url))
                else:
                    logging.error('PUT to %s returned %s - %s' % (firebase_url, r.status_code, r.text))
            except Exception as err:
                logging.error("Exception sending sensor data to Firebase: %s" % (err))

            # Sleep
            c.sleep(interval)

    #
    # Send all sensor data over websocket including sensor values
    # Stop after specified number of minutes.
    #
    def send_sensor_data(self, minutes):

        timestamp   = datetime.datetime.utcnow().replace(microsecond=0)
        stoptime    = timestamp + datetime.timedelta(minutes=minutes)

        logging.debug("send_sensor_data start: %s stop: %s" %
                        (timestamp, stoptime))

        while True:

            #
            # Only loop for the specified number of minutes
            #
            if datetime.datetime.utcnow() > stoptime:
                logging.debug("Stopping send_sensor_data")
                self.sensor_data_greenlet = None
                break

            #
            # Send all sensor data.
            #
            c.send_message('send_sensor_data_response',
                            {   'success':      True,
                                'data':         self.get_sensor_data(),
                                'src_folder':   c.path_on_server()  } )
            #
            # Sleep
            #
            c.sleep(1)


    #
    # Send watchdog message to server so that it knows which
    # controllers are online
    #
    def send_watchdog(self):
        minutes = 0
        while True:
            if minutes == 0:
                self.available_versions = []
                list_cmd = ListVersionsCommand(None, None, {})
                list_cmd.exec_cmd()
                if list_cmd.get_response() and list_cmd.get_response()['version_list']:
                    self.available_versions = list_cmd.get_response()['version_list']
            if minutes == 10:
                minutes = 0
            minutes += 1

            self.send_status()
            c.send_message('watchdog', {})
            c.sleep(60)

    # start capturing from a camera
    def add_camera(self):
        if hasattr(c, 'camera'):
            c.camera.open()
            if c.camera.device and c.camera.device.is_connected():
                self.send_message('device_added', {'type': 'camera', 'name': 'camera', 'dir': 'in'})

                # create image sequence on server if doesn't already exist
                server_path = c.path_on_server()
                if not c.resources.file_exists(server_path + '/image'):
                    create_sequence(server_path, 'image', data_type=3)
            else:
                logging.warning('unable to open camera')
        else:
            logging.warning('camera extension not added')

    # get a new image for the camera block and store it as a base64 encoded value;
    # for now we'll support just one physical camera (though it can feed into multiple camera blocks)
    def update_camera_blocks(self):
        if hasattr(c, 'camera') and c.camera.device and c.camera.device.is_connected():
            camera_block_defined = False
            for block in self.diagram.blocks:
                if block.type == 'camera':
                    camera_block_defined = True
            if camera_block_defined:
                image = c.camera.device.capture_image()

                # store camera image once a minute
                current_time = time.time()
                if not self.last_camera_store_time or current_time > self.last_camera_store_time + 60:
                    image.thumbnail((720, 540), Image.ANTIALIAS)
                    self.send_message('update_sequence', {'sequence': 'image', 'value': encode_image(image)})
                    self.last_camera_store_time = current_time
                    logging.debug('updating image sequence')

                # create small thumbnail to send to UI
                image.thumbnail((320, 240), Image.ANTIALIAS)
                data = encode_image(image)
                for block in self.diagram.blocks:
                    if block.type == 'camera':
                        block.value = data

    #
    # Get user friendly controller display name
    #
    def controller_name(self):
        parts = c.path_on_server().split('/')
        return parts[-1]

    #
    # Set the currently running diagram
    #
    def set_diagram(self, params):

        #
        # v2.0 messages should associate a username with a running
        # program.
        #
        if set(('diagram', 'username')) <= set(params):
            diagram_spec = params['diagram']

            if 'name' not in diagram_spec:
                self.send_message(
                            'set_diagram_response',
                            {   'success': False,
                                'message': "No program name specified."
                            })
                return

            name            = diagram_spec['name']
            self.diagram    = Diagram(name, diagram_spec)
            self.username   = params['username']

            self.send_message(
                            'set_diagram_response',
                            {   'success': True,
                                'message': "Set running program %s for user %s." % (name, self.username)
                            })

        else:

            #
            # Support legacy flow for backwards compatibility.
            # TODO remove this once v1.0 is no longer supported.
            #

            diagram_spec = params['diagram']

            name = '_temp_'
            if 'name' in diagram_spec:
                name = diagram_spec['name']
            logging.debug(
                "handle_message: set_diagram name %s" % (name))

            self.diagram = Diagram(name, diagram_spec)


# ======== UTILITY FUNCTIONS ========


# create a sequence resource on the server
# data types: 1 = numeric, 2 = text, 3 = image
def create_sequence(server_path, name, data_type, units = None):
    print('creating new sequence: %s' % name)
    sequence_info = {
        'path': server_path,
        'name': name,
        'type': 21,  # sequence
        'data_type': data_type,
        'min_storage_interval': 0,
    }
    if units:
        sequence_info['units'] = units
    c.resources.send_request_to_server('POST', '/api/v1/resources', sequence_info)


# change the name of a sequence on the server
def rename_sequence(server_path, old_name, new_name):
    print('renaming sequence: %s -> %s' % (old_name, new_name))
    c.resources.send_request_to_server('PUT', '/api/v1/resources' + server_path + '/' + old_name, {'name': new_name})
