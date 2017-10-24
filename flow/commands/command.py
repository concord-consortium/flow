import abc
import subprocess
import json
import logging

class Command(object):
    __metaclass__ = abc.ABCMeta

    # logging.basicConfig(level=logging.DEBUG)

    #
    # Create a new Command base class.
    #
    def __init__(self, flow, cmd_name, params):
        self.flow       = flow
        self.cmd_name   = cmd_name
        self.params     = params
        self.response   = None

    #
    # Clients call this to perform some operation
    #
    def exec_cmd(self):
        try:
            self.exec_impl()
        except subprocess.CalledProcessError as e:
            #
            # Failure path
            #
            logging.debug("Error executing: %s %s" % (e.cmd, e.output));
            if self.flow is not None:
                self.flow.send_message(self.cmd_name + "_response",
                    {   'success': False,
                        'message': 'Error executing command: %s' % (e.output) })
            return
        
        #
        # Success path
        #
        logging.debug("Sending response: %s" % (self.response))
        if self.flow is not None:
            self.flow.send_message(self.cmd_name + "_response", self.response)


    #
    # Helper to execute subprocess commands
    #
    def shell_helper(self, cmd_arr):
        output = subprocess.check_output(cmd_arr, stderr=subprocess.STDOUT)
        return output

    #
    # Override this to perform some subclass specific operation
    #
    @abc.abstractmethod
    def exec_impl(self):
        """ Subclasses implement this method to perform specific operations """
        return
    

