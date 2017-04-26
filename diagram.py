from decimal import Decimal, ROUND_HALF_UP
from filters.brightness import Brightness
from filters.blur import Blur

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
        self.decimal_places = block_spec.get('decimal_places', None)
        if self.value is not None and (not self.output_type == 'i'):  # if not image
            self.decimal_places = compute_decimal_places(self.value)
            self.value = float(self.value)  # fix(later): handle non-numeric types?
        self.sources = []
        self.dest_ids = []
        self.stale = True

    def is_numeric(self):
        return not self.output_type == 'i'

    def get_source_values(self):
        source_values = []
        self.decimal_places = 0
        for source in self.sources:
            if source.stale:
                source.update()
            if source.value is not None:
                if source.decimal_places > self.decimal_places:
                    self.decimal_places = source.decimal_places
                source_values.append(source.value)
        return source_values

    def compute_value(self, source_values):
        source_values_length = len(source_values)
        if source_values_length > 0 and source_values_length >= self.required_source_count:
            self.value = compute_filter(self.type, source_values, self.params)
            if self.is_numeric():
                # Convert decimal places, so quanitize can be used for accurate rounding
                # 6 decimal places -> .000001 = decimal_exp
                # 2 decimal places -> .01 = decimal_exp
                decimal_exp = Decimal(10) ** (-1 * self.decimal_places)
                self.value = float(Decimal(str(self.value)).quantize(decimal_exp, rounding=ROUND_HALF_UP))
        else:
            self.value = None

    # compute a new value for this block (assuming it has inputs/sources)
    def update(self):
        # we can only internally update blocks that have sources; others must be updated from the outside
        if self.required_source_count:

            # get all defined source values
            source_values = self.get_source_values()

            # compute new value for this block
            self.compute_value(source_values)
        
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
        blur = Blur()
        result = blur.compute(inputs, params)
    elif type == 'brightness':
        brightness = Brightness()
        result = brightness.compute(inputs, params)

    return result


# compute the number of decimal places present in a string
# representation of a number.
# examples: "1e-11" = 11, "10.0001" = 4
def compute_decimal_places(num_str):
    return abs(Decimal(str(num_str)).as_tuple().exponent)
