import time
import json
import logging
import hjson
import gevent
from PIL import Image
from rhizo.main import c
from rhizo.extensions.camera import encode_image
from sim_devices import simulate, add_sim_sensor, add_sim_actuator, remove_sim_device
from diagram_storage import list_diagrams, load_diagram, save_diagram, rename_diagram, delete_diagram
from diagram import Diagram, compute_decimal_places


# this file is the main program for the data flow client running on a controller (e.g. Raspberry Pi)


# global variables
diagram = None  # the currently running diagram (if any)
last_user_message_time = None  # the last user message time (if any)
last_camera_store_time = None  # the last camera sequence update time (if any)
last_record_time = None  # timestamp of last values recorded to long-term storage
recording_interval = None  # number of seconds between storing values in long-term storage


# handle messages from server (sent via websocket)
def message_handler(type, params):
    global diagram
    global last_user_message_time
    global recording_interval
    used = True
    if type == 'list_devices':
        print 'list_devices'
        for device in c.auto_devices._auto_devices:
            c.send_message('device_added', device.as_dict())
    elif type == 'request_block_types':
        block_types = hjson.loads(open('block_types.hjson').read())
        c.send_message('block_types', block_types)
    elif type == 'list_diagrams':
        c.send_message('diagram_list', {'diagrams': list_diagrams()})
    elif type == 'save_diagram':
        save_diagram(params['name'], params['diagram'])
    elif type == 'rename_diagram':
        rename_diagram(params['old_name'], params['new_name'])
    elif type == 'delete_diagram':
        delete_diagram(params['name'])
    elif type == 'set_diagram':
        diagram_spec = params['diagram']
        diagram = Diagram('_temp_', diagram_spec)
    elif type == 'start_diagram':  # start a diagram running on the controller; this will stop any diagram that is already running
        diagram_spec = load_diagram(params['name'])
        diagram = Diagram(params['name'], diagram_spec)
        #local_config = hjson.loads(open('local.hjson').read())  # save name of diagram to load when start script next time
        #local_config['startup_diagram'] = params['name']
        #open('local.hjson', 'w').write(hjson.dumps(local_config))
    elif type == 'stop_diagram':
        pass
    elif type == 'start_recording':
        recording_interval = float(params['rate'])
        print('start recording data (every %.2f seconds)' % recording_interval)
    elif type == 'stop_recording':
        print('stop recording data')
        recording_interval = None
    elif type == 'add_camera':
        add_camera()
    elif type == 'add_sim_sensor':
        add_sim_sensor()
    elif type == 'add_sim_actuator':
        add_sim_actuator()
    elif type == 'remove_sim_device':
        remove_sim_device()
    elif type == 'request_status':
        send_status()
    else:
        used = False

    # keep track of last message from web interface
    if used:
        last_user_message_time = time.time()
    return used


# handle an incoming value from a sensor device (connected via USB)
def input_handler(name, values):
    if diagram:
        block = diagram.find_block_by_name(name)
        if block:
            block.decimal_places = compute_decimal_places(values[0])
            block.value = float(values[0])


# send client info to server/browser
def send_status():
    status = {
        'flow_version': '0.0.1',
        'lib_version': c.VERSION + ' ' + c.BUILD,
        'device_count': len(c.auto_devices._auto_devices)
    }

    if diagram:
        status['current_diagram'] = diagram.name

    c.send_message('status', status)


# create a sequence resource on the server
# data types: 1 = numeric, 2 = text, 3 = image
def create_sequence(server_path, name, data_type):
    print('creating new sequence: %s' % name)
    file_info = {
        'path': server_path,
        'name': name,
        'type': 21,  # sequence
        'data_type': data_type,
    }
    c.resources.send_request_to_server('POST', '/api/v1/resources', file_info)


# check for new devices and create sequences for them
def check_devices():

    # get list of existing sequences
    server_path = c.path_on_server()
    print('server path: %s' % server_path)
    file_infos = c.resources.list_files(server_path, type = 'sequence')
    server_seqs = set([fi['name'] for fi in file_infos])
    print('server seqs: %s' % server_seqs)

    # loop forever checking for new devices; if found, create sequences for them
    while True:

        # if new device found, create sequence
        for device in c.auto_devices._auto_devices:  # fix(soon): change to serial.devices()? doesn't work with sim sensors
            if hasattr(device, 'name') and device.name:
                if device.name in server_seqs:
                    device.store_sequence = False  # going to do in main loop below
                else:
                    create_sequence(server_path, device.name, data_type=1)  # data_type 1 is numeric
                    device.store_sequence = False  # going to do in main loop below
                    server_seqs.add(device.name)

        # sleep for a bit
        c.sleep(5)


# start capturing from a camera
def add_camera():
    if hasattr(c, 'camera'):
        c.camera.open()
        if c.camera.device and c.camera.device.is_connected():
            c.send_message('device_added', {'type': 'camera', 'name': 'camera', 'dir': 'in'})

            # create image sequence on server if doesn't already exist
            server_path = c.path_on_server()
            if not c.resources.file_exists(server_path + '/image'):
                create_sequence(server_path, 'image', data_type=3)
        else:
            logging.warning('unable to open camera')
    else:
        logging.warning('camera extension not added')


# run enabled data flow(s)
def start():
    global last_record_time
    while True:
        if diagram:

            # update diagram values
            update_camera_blocks()
            diagram.update()

            # send values to server and actuators
            values = {}
            for block in diagram.blocks:
                value = None
                if block.output_type == 'i':  # only send camera/image updates if recent message from user
                    if last_user_message_time and time.time() < last_user_message_time + 300:
                        value = block.value
                else:
                    if block.value is not None:
                        format = '%' + '.%df' % block.decimal_places
                        value = format % block.value
                values[block.id] = value

                # send values to actuators
                if not block.output_type:
                    device = c.auto_devices.find_device(block.name)  # fix(later): does this still work if we rename a block?
                    if device and device.dir == 'out':
                        try:
                            value = int(block.value)
                        except:
                            value = None
                        if value is not None:
                            device.send_command('set %d' % value)

            c.send_message('update_diagram', {'values': values})

            # send sequence values
            current_time = time.time()
            if recording_interval and ((last_record_time is None) or current_time > last_record_time + recording_interval):
                for block in diagram.blocks:
                    if not block.input_type:
                        c.update_sequence(block.name, block.value)
                        print 'update sequence', block.name, block.value
                last_record_time = current_time

        # sleep until it is time to do another update
        c.sleep(1)


# get a new image for the camera block and store it as a base64 encoded value;
# for now we'll support just one physical camera (though it can feed into multiple camera blocks)
def update_camera_blocks():
    global last_camera_store_time
    if hasattr(c, 'camera') and c.camera.device and c.camera.device.is_connected():
        camera_block_defined = False
        for block in diagram.blocks:
            if block.type == 'camera':
                camera_block_defined = True
        if camera_block_defined:
            image = c.camera.device.capture_image()

            # store camera image once a minute
            current_time = time.time()
            if not last_camera_store_time or current_time > last_camera_store_time + 60:
                image.thumbnail((720, 540), Image.ANTIALIAS)
                c.update_sequence('image', encode_image(image))
                last_camera_store_time = current_time
                logging.debug('updating image sequence')

            # create small thumbnail to send to UI
            image.thumbnail((320, 240), Image.ANTIALIAS)
            data = encode_image(image)
            for block in diagram.blocks:
                if block.type == 'camera':
                    block.value = data


# if run as top-level script
if __name__ == '__main__':
    block_types = hjson.loads(open('block_types.hjson').read())
    open('test.json', 'w').write('%s' % json.dumps(block_types))
    c.add_message_handler(message_handler)
    c.auto_devices.add_input_handler(input_handler)
    gevent.spawn(check_devices)
    if c.config.get('startup_diagram', ''):  # run last diagram on startup
        name = c.config.startup_diagram
        diagram_spec = load_diagram(name)
        diagram = Diagram(name, diagram_spec)
    start()
