import subprocess

from command import Command

class DownloadSoftwareCommand(Command):

    def __init__(self, flow, cmd_name, params):
        Command.__init__(self, flow, cmd_name, params)

    def exec_impl(self):
        output = self.shell_helper(['git', '--git-dir=/home/pi/flow/.git', 'fetch'])
        self.response   = { 'success':  True,
                            'message':  'Downloaded latest software.',
                            'output':   output }


