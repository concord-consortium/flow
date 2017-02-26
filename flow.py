import logging
import gevent
from PIL import Image
from rhizo.main import c
from rhizo.extensions.camera import encode_image
from sim_devices import simulate, add_sim_sensor, add_sim_actuator, remove_sim_device
from diagram_storage import list_diagrams, load_diagram, save_diagram, rename_diagram, delete_diagram
from diagram import Diagram


# this file is the main program for the data flow client running on a controller (e.g. Raspberry Pi)


# the currently running diagram (if any)
diagram = None


# handle messages from server (sent via websocket)
def message_handler(type, params):
    global diagram
    if type == 'list_devices':
        print 'list_devices'
        for device in c.auto_devices._auto_devices:
            c.send_message('device_added', device.as_dict())
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
    elif type == 'stop_diagram':
        pass
    elif type == 'add_camera':
        if hasattr(c, 'camera'):
            c.camera.open()
            if c.camera.device and c.camera.device.is_connected():
                print 'camera connected'
                c.send_message('device_added', {'type': 'camera', 'name': 'camera'})
            else:
                logging.warning('unable to open camera')
        else:
            logging.warning('camera extension not added')
    elif type == 'add_sim_sensor':
        add_sim_sensor()
    elif type == 'add_sim_actuator':
        add_sim_actuator()
    elif type == 'remove_sim_device':
        remove_sim_device()
    elif type == 'request_status':
        send_status()
    elif type == 'update_actuator':  # fix(clean): remove this?
        name = params['name']
        value = params['value']
        print 'update_actuator', name, value
        device = c.auto_devices.find_device(name)
        if device:
            device.send_command('set %s' % value)


# handle an incoming value from a sensor device (connected via USB)
def input_handler(name, values):
    if diagram:
        block = diagram.find_block_by_name(name)
        if block:
            block.value = float(values[0])


# send client info to server/browser
def send_status():
    c.send_message('status', {
        'flow_version': '0.0.1',
        'lib_version': c.VERSION + ' ' + c.BUILD,
        'device_count': len(c.auto_devices._auto_devices),
        'current_diagram': diagram.name,
    })


# create a sequence resource on the server
def create_sequence(server_path, device):
    print('creating new sequence for device: %s' % device.name)
    fileInfo = {
        'path': server_path,
        'name': device.name,
        'type': 21,  # sequence 
        'data_type': 1,  # numeric
    }
    c.resources.send_request_to_server('POST', '/api/v1/resources', fileInfo)


# check for new devices and create sequences for them
def check_devices():
    
    # get list of existing sequences
    server_path = c.path_on_server()
    print('server path: %s' % server_path)
    file_infos = c.resources.list_files(server_path, type = 'sequence')
    server_seqs = set([fi['name'] for fi in file_infos])
    print('server seqs: %s' % server_seqs)
    
    # loop forever checking for new devices
    while True:
        
        # if new device found, create sequence
        for device in c.auto_devices._auto_devices:  # fix(soon): change to serial.devices()? doesn't work with sim sensors
            if hasattr(device, 'name') and device.name:
                if device.name in server_seqs:
                    device.store_sequence = True
                else:
                    create_sequence(server_path, device)
                    device.store_sequence = True
                    server_seqs.add(device.name)
        
        # sleep for a bit
        c.sleep(5)


# run enabled data flow(s)
def start():
    while True:
        if diagram:
            update_camera_blocks()
            diagram.update()
            values = {}
            for block in diagram.blocks:
                value = block.value
                if (not value is None) and block.type != 'camera':
                    value = '%.2f' % value  # fix(soon): compute and propage decimal precision through diagram
                values[block.id] = value
            c.send_message('update_diagram', {'values': values})
        c.sleep(1)


# get a new image for the camera block and store it as a base64 encoded value;
# for now we'll support just one physical camera (though it can feed into multiple camera blocks)
def update_camera_blocks():
    if hasattr(c, 'camera') and c.camera.device and c.camera.device.is_connected():
        camera_block_defined = False
        for block in diagram.blocks:
            if block.type == 'camera':
                camera_block_defined = True
        if camera_block_defined:
            image = c.camera.device.capture_image()
            image.thumbnail((320, 240), Image.ANTIALIAS)
            data = encode_image(image)
            for block in diagram.blocks:
                if block.type == 'camera':
                    block.value = data


# if run as top-level script
if __name__ == '__main__':
    c.add_message_handler(message_handler)
    c.auto_devices.add_input_handler(input_handler)
    gevent.spawn(check_devices)
    start()
