import subprocess

from command    import Command
from git_tools  import git_base_command 

class ListVersionsCommand(Command):

    def __init__(self, flow, cmd_name, params):
        Command.__init__(self, flow, cmd_name, params)

    def exec_impl(self):
        output      = self.shell_helper(git_base_command() + ['tag'])
        versions    = output.split()
        self.response = {   'success': True,
                            'message': 'Found version list',
                            'version_list': versions }


