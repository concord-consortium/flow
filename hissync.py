#!/usr/bin/env python
"""
Synchronize a specific time series/history between local and remote influxdb database/measurement.

Can be used from crontab, e.g. like this every 5 minutes or every minute:

*   * * * * PYTHONPATH=/Users/peter/git-clones/flow /opt/venv/flow3/bin/python /Users/peter/git-clones/flow/hissync.py localhost influxdb_main.example.com flow sensor_mean,run,diagram >> /tmp/hissync.out 2>&1
*/5 * * * * PYTHONPATH=/Users/peter/git-clones/flow /opt/venv/flow3/bin/python /Users/peter/git-clones/flow/hissync.py localhost influxdb_main.example.com flow sensor_mean --verbose 2>&1


"""
import sys
import argparse
import datetime
from dateutil.parser import parse
from flow.influxstore import Store


def perform_bulk_transfer(from_store, to_store, measurement, sync_start, chunk_size, verbose=False):
    """Performs bulk transfer from source to destination.

    This assumes that we are performing bulk transfer/sync of a series that looks like this:

    select * from sensor_mean order by time desc limit 40
    name: sensor_mean
    time                 count max mean               min name  pin
    ----                 ----- --- ----               --- ----  ---
    2017-06-14T00:02:00Z 60    124 120.31666666666666 115 light 2671
    2017-06-14T00:01:00Z       124 119.63333333333334 115 light 2671
    2017-06-14T00:00:00Z       124 117.76666666666667 113 light 2671
    2017-06-13T23:59:00Z       127 124.33333333333333 115 light 2671
    2017-06-13T23:58:00Z       129 122.3              115 light 2671
    2017-06-13T23:57:00Z       137 122.95             111 light 2671

    :param from_store:
    :param to_store:
    :param measurement:
    :param sync_start:
    :param chunk_size: chunk size (number of records transferred at the same time) to use during read/write operations
    :param verbose: if True, print progress of transfer
    :return: number of records transferred

    """

    current_start = sync_start.isoformat()

    # calculate number of points
    rs = from_store.query(
        "select count(*) from %s where time > '%s'" % (measurement, current_start))
    points = list(rs.get_points())

    # get count value from any items other than time
    #   this is needed for generic ount retrieval instead of doing this:
    #   count = points[0]['count'] if points else 0
    count_points = list(rs.get_points())
    if not count_points:
        if verbose:
            print("%s: no new records to sync since %s." % (measurement, current_start))
        return 0

    count_dict = count_points[0]
    # any item name other than time
    item_name = list(filter(lambda x: x != 'time', count_dict.keys()))[0]
    count = count_dict[item_name]
    if verbose:
        print("%s: performing bulk transfer of about %d records in chunks of max %d records." % \
              (measurement, count, chunk_size))
    start = datetime.datetime.now()
    total = 0
    # TODO: unhardcode fields via:
    #   query("show field keys from sensor_mean", database="flow")
    field_keys = ['min', 'max', 'mean', 'count']
    non_tag_keys = field_keys + ['time']
    while True:
        rs = from_store.query(
            "select * from %s where time > '%s' limit %s" % (measurement, current_start, chunk_size))
        if not rs:
            break
        points = list(rs.get_points())
        last_record = points[-1]
        current_start = last_record.get("time")
        target_points = []
        for p in points:
            """
            each point looks like this:
            [{'max': 148,
              'mean': 147.88333333333333,
              'min': 145,
              'count': 60,
              'name': 'light',
              'pin': '2671',
              'time': '2017-06-13T21:00:00Z'},
            """
            #vmin, vmax, vmean = p['min'], p['max'], p['mean']
            tag_keys = p.keys() - non_tag_keys
            tags = dict((k, p[k]) for k in tag_keys)
            fields = dict((k, float(p[k])) for k in field_keys)
            target_point = {
                "time": p['time'],
                "measurement": measurement,
                "fields": fields,
                "tags": tags
            }
            target_points.append(target_point)
        to_store.dbclient.write_points(target_points)
        total += len(points)
        if verbose:
            print("%s: transferring: %d out of %d" % (measurement, total, count))



    if verbose:
        duration = (datetime.datetime.now() - start).total_seconds()
        print("Finished bulk transfer: total transferred: %d records in %.2f seconds." % (total, duration))
    return total



def do_hissync(from_db, to_db, dbname, measurements, verbose=False):
    """Do history sync.

    :param from_db: source db host/port as host[:port]
    :param to_db: destination db host/port  url  as host[:port]
    :param measurements: measurements to synchronize
    :param verbose: if True, print progress of transfer
    :return: number of records transferred

    Examples:
    >>> do_hissync("localhost", "influx.example.com", ["sensor_mean", "run"], verbose=True)
    >>> # if destination is via a port 80 tunnel, you may need to specify port (default is 8086)
    >>> do_hissync("localhost:8086", "influx.example.com:80", "sensor_mean")

    """
    fport = None
    dport = None

    # parse arguments
    fhost_port = from_db.split(":")
    fhost = fhost_port[0]
    if len(fhost_port) > 1:
        fport = fhost_port[1]
    dhost_port = to_db.split(":")
    dhost = dhost_port[0]
    if len(dhost_port) > 1:
        dport = dhost_port[1]

    from_store = Store(dbname, "", fhost, fport)
    to_store = Store(dbname, "", dhost, dport)

    # TODO: create db if it doesn't exist
    #  to_store.dbclient.create_database('flow')

    sync_count = 0
    for measurement in measurements:
        # get last record timestamp
        sync_start = parse("1970-01-01T00:00:00Z")
        rs = to_store.query("select * from %s order by time desc limit 1" % measurement)
        if rs:
            last_record = list(rs.get_points())[0]
            ts = last_record.get("time")
            if not ts:
                raise Exception("Can't retrieve timestamp from %s" % last_record)
            sync_start = parse(ts)
        # perform sync, starting at last record that has already been synced
        sync_count += perform_bulk_transfer(from_store, to_store, measurement, sync_start, 100, verbose)
    return sync_count


if __name__ == '__main__':
    """Main program for hisSync.

    Returns value to the shell:
    0: 1 or more records transferred
    2: 0 records transferred, the databases are in sync and no action necessary
    1: An error occurred.

    Example usage from shell:

    python3 hissync.py rpi localhost flow sensor_mean
    python3 hissync.py localhost influxdb_main.example.com flow sensor_mean,run,diagram --verbose

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("from_db", help="source db host:port",
                        type=str)
    parser.add_argument("to_db", help="destination db host:port",
                        type=str)
    parser.add_argument("dbname", help="db name",
                        type=str)
    parser.add_argument("measurements", help="measurements (separated by comma if more than one)",
                        type=str)
    parser.add_argument("-v", "--verbose", help="print progress (verbose on)", action="store_true")
    args = parser.parse_args()
    from_db, to_db, dbname, measurements_str, verbose = \
      args.from_db, args.to_db, args.dbname, args.measurements, args.verbose

    measurements = measurements_str.split(",")

    #from_db = "rpi"
    #to_db = "localhost"
    #dbname = "flow"
    #measurements = ["sensor_mean"]
    #measurements = ["sensor_mean", "run", "diagram"]
    #verbose = True
    rc = do_hissync(from_db, to_db, dbname, measurements, verbose=verbose)
    if rc > 0:
        ret = 0
    else:
        ret = 2
    sys.exit(ret)
