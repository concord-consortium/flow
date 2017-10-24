import subprocess

from command import Command

class UpdateSoftwareCommand(Command):

    def __init__(self, flow, cmd_name, params):
        Command.__init__(self, flow, cmd_name, params)

    def exec_impl(self):

        release = params['release']
        list_cmd = ListVersionsCommand(None, None, {})
        list_cmd.exec_cmd()

        if list_cmd.get_response().success is False:
            self.response = {   
                    'success': False,
                    'message': 'Unable to list available versions.' }
            return

        if not release in list_cmd.get_response()['version_list']:
            self.response = {   
                    'success': False,
                    'message': 'Version %s is not available' % (release) }
            return

        self.shell_helper(['git', 'checkout'. 'tags/'+release])

        self.response = {   
                'success': True,
                'message': 'Software version updated to %s' % (tag) }


