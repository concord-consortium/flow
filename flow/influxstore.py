"""Influxdb store

Usage:

from influxstore import Store

# --- save

mypin = '2671'
store = Store(database="flow", pin=mypin)
store.save('sensor', 'light', 212.22)

# --- read

TODO: implement

mypin = '2671'
store = Store("flow", mypin)
rs = store.query('select * from sensor where time > now() - 1h limit 10')
rs.raw
Out[9]: 
{u'series': [{u'columns': [u'time', u'name', u'pin', u'value'],
   u'name': u'sensor',
   u'values': [[u'2017-05-24T20:43:30.297933056Z',
     u'lightttt',
     u'2671',
     205]]}],
 u'statement_id': 0}
rs.raw['series'][0]['values']
Out[11]: [[u'2017-05-24T20:43:30.297933056Z', u'lightttt', u'2671', 205]]


store.query("select * from sensor where \"name\"='lightttt' limit 10")

Other query strings examples with responses:

 select * from sensor order by time desc limit 10;

name: sensor
time                           name     pin  value
----                           ----     ---  -----
2017-05-24T13:27:32.361068032Z lightttt 1234 215.22
2017-05-24T13:26:11.977960192Z lightttt 1234 212.22
2017-05-23T11:13:12Z           light    1234 30
2017-05-23T11:13:11Z           light    1234 30
2017-05-23T11:13:10Z           light    1234 30
2017-05-23T11:13:09Z           light    1234 30
2017-05-23T11:13:08Z           light    1234 29
2017-05-23T11:13:07Z           light    1234 31
2017-05-23T11:13:06Z           light    1234 30
2017-05-23T11:13:05Z           light    1234 30
	



"""
import datetime
# start influxdb client
from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError



class Store(object):
    """Encapsulates influxdb store.
    """

    def __init__(self, database, pin, hostname="localhost", port=None):
        self.pin = pin
        self.hostname = hostname
        self.port = port if port else 8086
        self.database = database
        self.pin = pin
        self.dbclient = InfluxDBClient(hostname, database=database)

    def save(self, measurement, name, value, extra_tags = {}):
        dt = datetime.datetime.utcnow()
        tags = extra_tags.copy()
        tags.update({
                    "name": name,
                    "pin": self.pin,
                })
        point = {
            #"time": dt.strftime ("%Y-%m-%d %H:%M:%S.%s"),
            "time": dt,
            # "time": int(past_date.strftime('%s')),
            "measurement": measurement,
            'fields':  {
                'value': value,
                },
            'tags': tags,
            }
        self.dbclient.write_points([point])

    def save_many(self, points):
        self.write_points(points)
 
    def query(self, querystr):
        return self.dbclient.query(querystr)

    def close():
        pass

