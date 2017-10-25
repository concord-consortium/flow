from rhizo.main import c

#
# Create the git base command with default options
#
def git_base_command():
    git_flow_dir = c.config.get('git_flow_dir', '/home/pi/flow')
    return [    'git', 
                '--git-dir=%s/.git' % (git_flow_dir), 
                '--work-tree=%s'    % (git_flow_dir)    ]

