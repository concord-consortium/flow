import abc
from decimal import Decimal, ROUND_HALF_UP


# represents a block (an input, filter, or output) in a data flow diagram
class Block(object):
    __metaclass__ = abc.ABCMeta

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
            self.decimal_places = self.compute_decimal_places(self.value)
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
            self.value = self.compute(source_values, self.params)
            if self.is_numeric() and self.value is not None:
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

    # compute the number of decimal places present in a string
    # representation of a number.
    # examples: "1e-11" = 11, "10.0001" = 4
    def compute_decimal_places(self, num_str):
        return abs(Decimal(str(num_str)).as_tuple().exponent)
