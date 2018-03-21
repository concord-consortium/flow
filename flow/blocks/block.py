import abc
import logging

from decimal import Decimal, ROUND_HALF_UP


# represents a block (an input, filter, or output) in a data flow diagram
class Block(object):
    __metaclass__ = abc.ABCMeta

    #
    # Block device types that map to physical sensors.
    #
    SENSOR_DEVICE_TYPES = [ "temperature", 
                            "humidity", 
                            "light",
                            "soilmoisture",
                            "CO2" ]

    # create a block using a block spec dictionary
    def __init__(self, block_spec=None):
        if block_spec is not None:
            self.id = block_spec['id']
            self.name = block_spec['name']
            self.type = block_spec['type']
            self.source_ids = block_spec['sources']
            self.required_source_count = block_spec['input_count']

            #
            # Do not set value from the spec for actual sensors which
            # might not be connected and therefore should not return 
            # a value.
            #
            if self.type not in self.SENSOR_DEVICE_TYPES:
                #
                # For non device types (like numeric blocks) set the
                # value from the spec.
                #
                self.value = block_spec.get('value', None)
            else:
                self.value = None

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

            # logging.debug("%s Checking source %s" % (self.name, source))

            if source.stale:
                # logging.debug("%s Source is stale. Updating..." % (self.name))
                source.update()
            if source.value is not None:
                # logging.debug("%s Appending %s..." % (self.name, source.value))
                if source.decimal_places > self.decimal_places:
                    self.decimal_places = source.decimal_places
                source_values.append(source.value)
        return source_values

    def compute_value(self, source_values):
        source_values_length = len(source_values)
        if source_values_length > 0 and source_values_length >= self.required_source_count:
            self.value = self.compute(source_values, self.params)
            if self.is_numeric() and self.value is not None:
                self.value = round(self.value, self.decimal_places)
        else:
            self.value = None

    def round(self, value, decimal_places):
        # Convert decimal places, so quanitize can be used for accurate rounding
        # 6 decimal places -> .000001 = decimal_exp
        # 2 decimal places -> .01 = decimal_exp
        decimal_exp = Decimal(10) ** (-1 * decimal_places)
        return float(Decimal(str(value)).quantize(decimal_exp, rounding=ROUND_HALF_UP))

    # compute a new value for this block (assuming it has inputs/sources)
    def update(self):
        # we can only internally update blocks that have sources; others must be updated from the outside

        # logging.debug("Block update() %s %s" % 
        #                (self.name, self.get_source_values()))

        if self.required_source_count:

            # logging.debug("Block update() checking sources")

            # get all defined source values
            source_values = self.get_source_values()

            # compute new value for this block
            self.compute_value(source_values)

        # logging.debug("Block update() %s value %s" % 
        #                (self.name, self.value))

        # mark the block as non-stale, since we've updated the value or determined that no update is needed
        self.stale = False

    # compute the number of decimal places present in a string
    # representation of a number.
    # examples: "1e-11" = 11, "10.0001" = 4
    def compute_decimal_places(self, num_str):
        return abs(Decimal(str(num_str)).as_tuple().exponent)

    # a helper function for reading from a list of parameters
    def read_param(self, params, name, default=None):
        if params is not None:
            param = self.read_param_obj(params, name)
            if param:
                return param['value']
        return default

    def read_param_obj(self, params, name):
        for param in params:
            if param['name'] == name:
                return param
        return None
