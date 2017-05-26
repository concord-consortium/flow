"""Simple MQTT wrapper for subscriber and publisher.

Usage:

from mqttclient import MqttPublisher, MqttSubscriber

# --- init subscriber

# msg: MQTTMessage class, which has members topic, payload, qos, retain and mid.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.qos)+" "+str(msg.payload))    

s = MqttSubscriber("hello/world")
s.start(on_message)

# --- init publisher

p = MqttPublisher("hello/world")
p.start()

# publish something
p.publish('test 123')


"""
import paho.mqtt.client as mqtt  
import time

def on_connect(client, userdata, flags, rc):
    m="Connected flags"+str(flags)+"; result code="\
    +str(rc)+"; client: "+str(client)
    print(m)

def on_subscribe(client, userdata, mid, granted_qos):
    print("Subscribed: "+str(mid)+" "+str(granted_qos))

def on_disconnect(client, userdata, rc):
    print("on_disconnect: userdata=%s; rc=%d" % (userdata, rc))
    if rc != 0:
        print("Unexpected disconnect")

class MqttBrokerClient(object):
    def __init__(self, topic, client_id=None, hostname="localhost"):
        self.topic = topic
        self.hostname = hostname
        self.client = mqtt.Client(client_id)
        #attach function to callback
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect

    def start(self):
        #connect to broker
        self.client.connect(self.hostname)
        # start the loop to receive callbacks for both subscriber and publisher
        self.client.loop_start()    
 
    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def user_data_set(self, userdata):
        self.client.user_data_set(userdata)

class MqttPublisher(MqttBrokerClient):

    def publish(self, msg):
        self.client.publish(self.topic, msg) 
        
class MqttSubscriber(MqttBrokerClient):

    def start(self, receiver_cb):
        MqttBrokerClient.start(self)
        #attach function to callback
        self.client.on_subscribe = on_subscribe
        self.client.on_message=receiver_cb
        #self.client.subscribe(self.topic, qos=1)
        self.client.subscribe(self.topic)

    def loop_forever(self):
        """Blocking loop."""
        self.client.loop_forever()

        
