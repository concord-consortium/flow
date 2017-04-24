from PIL import Image, ImageFilter, ImageEnhance
import cStringIO
import base64
from rhizo.extensions.camera import encode_image


# represents a data flow diagram
class Diagram(object):

    # create a data flow diagram using a spec dictionary
    def __init__(self, name, diagram_spec):
        self.name = name
        self.blocks = []
        for block_spec in diagram_spec['blocks']:
            self.blocks.append(Block(block_spec))
        
        # set source and destination blocks for each block using source_ids
        for block in self.blocks:
            for source_id in block.source_ids:
                source_block = self.find_block_by_id(source_id)
                source_block.dest_ids.append(block.id)
                block.sources.append(source_block)
    
    # get a block by ID; returns None if none found
    def find_block_by_id(self, id):
        for block in self.blocks:
            if block.id == id:
                return block
        return None
    
    # get a block by name; returns None if none found
    # (note: names may not be unique; will return first match)
    def find_block_by_name(self, name):
        for block in self.blocks:
            if block.name == name:
                return block
        return None
    
    # compute new values for all blocks
    def update(self):

        # mark all blocks as having a stale value
        for block in self.blocks:
            block.stale = True

        # update blocks without destinations; others will get updated recursively
        for block in self.blocks:
            if not block.dest_ids:
                block.update()


# represents a block (an input, filter, or output) in a data flow diagram
class Block(object):
    
    # create a block using a block spec dictionary
    def __init__(self, block_spec):
        self.id = block_spec['id']
        self.name = block_spec['name']
        self.type = block_spec['type']
        self.source_ids = block_spec['sources']
        self.required_source_count = block_spec['input_count']
        self.value = block_spec.get('value', None)
        self.params = block_spec.get('params', {})
        self.input_type = block_spec['input_type']
        self.output_type = block_spec['output_type']
        if (not self.value is None) and not self.output_type == 'i':  # if not image
            self.value = float(self.value)  # fix(later): handle non-numeric types?
        self.sources = []
        self.dest_ids = []
        self.stale = True

    # compute a new value for this block (assuming it has inputs/sources)
    def update(self):
    
        # we can only internally update blocks that have sources; others must be updated from the outside
        if self.required_source_count:
        
            # get all defined source values
            source_values = []
            for source in self.sources:
                if source.stale:
                    source.update()
                if source.value is not None:
                    source_values.append(source.value)
            
            # compute new value for this block
            if len(source_values) >= self.required_source_count:
                self.value = compute_filter(self.type, source_values, self.params)
            else:
                self.value = None
        
        # mark the block as non-stale, since we've updated the value or determined that no update is needed
        self.stale = False


# compute the value of a filter block based on its inputs
def compute_filter(type, inputs, params):
    result = inputs[0]
    if type == 'and':
        result = int(inputs[0] and inputs[1])
    elif type == 'or':
        result = int(inputs[0] or inputs[1])
    elif type == 'xor':
        result = int((inputs[0] > 0) != (inputs[1] > 0))
    elif type == 'nand':
        result = int(not (inputs[0] and inputs[1]))
    elif type == 'not':
        result = int(not inputs[0])
    elif type == 'plus':
        result = inputs[0] + inputs[1]
    elif type == 'minus':
        result = inputs[0] - inputs[1]
    elif type == 'times':
        result = inputs[0] * inputs[1]
    elif type == 'divided by':
        result = inputs[0] / inputs[1] if abs(inputs[1]) > 1e-8 else None
    elif type == 'absolute value':
        result = abs(inputs[0])
    elif type == 'equals':
        result = int(inputs[0] == inputs[1])
    elif type == 'not equals':
        result = int(inputs[0] != inputs[1])
    elif type == 'less than':
        result = int(inputs[0] < inputs[1])
    elif type == 'greater than':
        result = int(inputs[0] > inputs[1])
    elif type == 'blur':
        result = inputs[0]
        blur_amount = read_param(params, 'blur_amount')
        image_string = cStringIO.StringIO(base64.b64decode(result))  # decode image
        outImage = Image.open(image_string)
        outImage = outImage.filter(ImageFilter.GaussianBlur(radius=blur_amount))
        result = encode_image(outImage)

    elif type == 'brightness':
        result = inputs[0]
        brightness = read_param_obj(params, "brightness_adjustment")
        old_range = brightness["max"] - brightness["min"]
        brightness_amount = brightness["value"]

        # Pillow upper brightness range scales very high (1000 is still not pure white),
        # while a negative value scales small (i.e. 0 is pure black),
        # but value of 1 is the original image.
        if brightness_amount > 0:
            brightness_amount = brightness_amount * 10

        # Pillow's comparable brightness range
        new_min = 0
        new_max = 2
        new_range = new_max - new_min

        brightness_amount = (((brightness_amount - brightness["min"]) * new_range) / float(old_range)) + new_min
        imageString = cStringIO.StringIO(base64.b64decode(result))  # decode image
        outImage = Image.open(imageString)
        enhancer = ImageEnhance.Brightness(outImage)
        outImage = enhancer.enhance(brightness_amount)
        result = encode_image(outImage)
    return result


# a helper function for reading from a list of parameters
def read_param(params, name):
    param = read_param_obj(params, name)
    if param:
        return param['value']
    return None

def read_param_obj(params, name):
    for param in params:
        if param['name'] == name:
            return param
    return None

# compute the number of decimal places present in a string representation of a number
def compute_decimal_places(num_str):
    places = 0
    dot_pos = num_str.find('.')
    if dot_pos >= 0:
        places = len(num_str) - dot_pos - 1
    return places
