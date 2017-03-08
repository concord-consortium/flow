import os
import json


# request a list of flow diagrams on the controller
def list_diagrams():
    diagram_infos = []
    if not os.path.exists('diagrams'):
        os.makedirs('diagrams')
    file_names = os.listdir('diagrams')
    for file_name in file_names:
        if file_name.endswith('.json'):
            name = file_name.rsplit('.')[0]
            diagram_infos.append(load_diagram(name))
    return diagram_infos


# load a flow diagram and send it as a message to the server
def load_diagram(name):
    file_name = 'diagrams/' + name + '.json'
    diagram = json.loads(open(file_name).read())
    diagram['name'] = name
    return diagram


# save a flow diagram in the controller's local file system
def save_diagram(name, diagram):
    illegal = set('*?/\\')
    if any((c in illegal) for c in name):
        return
    if not os.path.exists('diagrams'):
        os.makedirs('diagrams')
    file_name = 'diagrams/' + name + '.json'
    open(file_name, 'w').write(json.dumps(diagram))


# rename a flow diagram
def rename_diagram(old_name, new_name):
    old_file_name = 'diagrams/' + old_name + '.json'
    new_file_name = 'diagrams/' + new_name + '.json'
    if os.path.exists(old_file_name) and not os.path.exists(new_file_name):
        os.rename(old_file_name, new_file_name)


# delete a flow diagram
def delete_diagram(name):
    file_name = 'diagrams/' + name + '.json'
    if os.path.exists(file_name):
        os.unlink(file_name)
