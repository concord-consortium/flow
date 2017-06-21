# this file is the main program for the data flow client running on a controller (e.g. Raspberry Pi)
from flow.flow import Flow


# if run as top-level script
if __name__ == '__main__':
    flow = Flow()
    flow.start()