import abc
import base64
import cStringIO
from PIL import Image
from ..block import Block


class Filter(Block):
    __metaclass__ = abc.ABCMeta

    def __init__(self, block_spec):
        super(Filter, self).__init__(block_spec)

    @abc.abstractmethod
    def compute(self, inputs, params):
        """Retrieve input(s) and return the output(s)."""
        return

    def decode_image(self, image_string):
        imageString = cStringIO.StringIO(base64.b64decode(image_string))
        outImage = Image.open(imageString)
        return outImage
