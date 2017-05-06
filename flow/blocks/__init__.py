from filters.blur import Blur
from filters.brightness import Brightness
from filters.operator import Operator
from filters.sma import SimpleMovingAverage
from filters.ema import ExponentialMovingAverage
from block import Block

non_operator_blocks = {
    'blur': Blur,
    'brightness': Brightness,
    'simple moving average': SimpleMovingAverage,
    'exponential moving average': ExponentialMovingAverage
}


def createBlock(block_spec):
    type = block_spec.get('type', None)
    block = None

    if type is not None:
        class_definition = non_operator_blocks.get(type.lower(), None)
        if class_definition is None:
            class_definition = Operator
        block = class_definition(block_spec)
    else:
        raise NotImplementedError('The block spec must contain a type, in order to create a Block')

    return block
