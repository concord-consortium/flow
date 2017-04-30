import time
import logging
import gevent
from PIL import Image
from rhizo.main import c
from rhizo.extensions.camera import encode_image
from flow.sim_devices import simulate, add_sim_sensor, add_sim_actuator, remove_sim_device
from flow.diagram_storage import list_diagrams, load_diagram, save_diagram, rename_diagram, delete_diagram
from flow.diagram import Diagram
from flow.flow import message_handler, input_handler, check_devices, start

# this file is the main program for the data flow client running on a controller (e.g. Raspberry Pi)

# if run as top-level script
if __name__ == '__main__':
    c.add_message_handler(message_handler)
    c.auto_devices.add_input_handler(input_handler)
    gevent.spawn(check_devices)
    if c.config.get('startup_diagram', ''):  # run last diagram on startup
        name = c.config.startup_diagram
        diagram_spec = load_diagram(name)
        diagram = Diagram(name, diagram_spec)
    start()
