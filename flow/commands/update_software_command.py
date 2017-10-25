import subprocess

from command                import Command
from list_versions_command  import ListVersionsCommand

from ..git_tools            import git_base_command

class UpdateSoftwareCommand(Command):

    def __init__(self, flow, cmd_name, params):
        Command.__init__(self, flow, cmd_name, params)

    def exec_impl(self):

        release = self.params['release']
        list_cmd = ListVersionsCommand(None, None, {})
        list_cmd.exec_cmd()

        if list_cmd.get_response()['success'] is False:
            self.response = {   
                    'success': False,
                    'message': 'Unable to list available versions.' }
            return

        if not release in list_cmd.get_response()['version_list']:
            self.response = {   
                    'success': False,
                    'message': 'Version %s is not available' % (release) }
            return

        self.shell_helper(git_base_command() + ['checkout', 'tags/'+release])

        if self.flow is not None:
            self.flow.set_operational_status(self.flow.OP_STATUS_UPDATING)

        self.response = {   
                'success': True,
                'message': 'Software version updating to %s' % (tag) }

    def post_exec(self):
        if self.flow is not None:
            self.flow.send_status()
        self.shell_helper(['sudo', 'reboot'])


