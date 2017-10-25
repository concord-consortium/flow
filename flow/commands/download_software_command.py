import subprocess

from command    import Command
from git_tools  import git_base_command

class DownloadSoftwareCommand(Command):

    def __init__(self, flow, cmd_name, params):
        Command.__init__(self, flow, cmd_name, params)

    def exec_impl(self):
        output = self.shell_helper(git_base_command() + ['fetch'])
        self.response   = { 'success':  True,
                            'message':  'Downloaded latest software.',
                            'output':   output }


