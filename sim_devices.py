import random
import gevent
from rhizo.main import c
from rhizo.extensions.auto_devices import AutoDevice


# true if simulate() greenlet has been launched
simulate_started = False


# specs for simulated sensors
sim_sensors = [
    {'type': 'temperature', 'model': 'DHT22', 'units': 'degrees C'},
    {'type': 'humidity', 'model': 'DHT22', 'units': 'percent'},
    {'type': 'light', 'model': 'photoresistor', 'units': None},
]


# an index into the sim_sensors data
next_sensor_index = 0


# generate simulated serial messages from the devices
def simulate():
    while True:
    
        # generate new sensor values
        index = 0
        for device in c.auto_devices._auto_devices:
            min = (index + 1) * 1000
            max = (index + 1) * 1000 + 800
            val_str = '%.2f' % (random.randint(min, max) * 0.01)
            if device.dir == 'in':
                device.process_serial_message('v', [val_str], '')
            index += 1
        
        # wait a second
        gevent.sleep(1)


# add a simulated sensor device
def add_sim_sensor():
    global next_sensor_index
    global simulate_started
    
    # create a sensor instance
    device_info = sim_sensors[next_sensor_index]
    device_id = device_info['type'][0]
    port_name = 'sim%d' % (len(c.auto_devices._auto_devices) + 1)
    print 'adding sensor: port: %s, id: %s' % (port_name, device_id)
    device = AutoDevice(device_id, c, port_name)
    next_sensor_index += 1
    if next_sensor_index == 3:
        next_sensor_index = 0
    
    # simulate info messages from it
    device.process_serial_message('dir', ['in'], '')
    device.process_serial_message('type', [device_info['type']], '')
    device.process_serial_message('model', [device_info['model']], '')
    if device_info['units']:
        device.process_serial_message('units', [device_info['units']], '')
    
    # add to auto-devices extension
    c.auto_devices.add_device(device)
    
    # if needed, start simulation greenlet to generate sim sensor values
    if not simulate_started:
        simulate_started = True
        gevent.spawn(simulate)


# add a simulated actuator device
def add_sim_actuator():
    print 'add_sim_actuator'
    port_name = 'sim%d' % (len(c.auto_devices._auto_devices) + 1)
    device = AutoDevice('r', c, port_name)
    
    # simulate info messages from it
    device.process_serial_message('dir', ['out'], '')
    device.process_serial_message('type', ['relay'], '')
    device.process_serial_message('model', ['small relay'], '')
    device.process_serial_message('ready', [], '')
    
    # add to sensor extension
    c.auto_devices.add_device(device)


# remove a simulated device
def remove_sim_device():
    print 'remove_sim_device'
    count = len(c.auto_devices._auto_devices)
    device = c.auto_devices._auto_devices[random.randint(0, count - 1)]
    c.auto_devices.remove_devices(device.port_name())
