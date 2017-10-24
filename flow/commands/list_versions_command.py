import subprocess

from command import Command

class ListVersionsCommand(Command):

    def __init__(self, flow, cmd_name, params):
        Command.__init__(self, flow, cmd_name, params)

    def exec_impl(self):
        output      = self.shell_helper(['git', 'tag'])
        versions    = output.split()
        self.response = {   'success': True,
                            'message': 'Found version list',
                            'version_list': versions }


