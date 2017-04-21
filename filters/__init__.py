import abc
import base64
import cStringIO
from PIL import Image


class Filter(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def compute(self, inputs, params):
        """Retrieve input(s) and return the output(s)."""
        return

    def decode_image(self, image_string):
        imageString = cStringIO.StringIO(base64.b64decode(image_string))
        outImage = Image.open(imageString)
        return outImage

    # a helper function for reading from a list of parameters
    def read_param(self, params, name):
        param = self.read_param_obj(params, name)
        if param:
            return param['value']
        return None

    def read_param_obj(self, params, name):
        for param in params:
            if param['name'] == name:
                return param
        return None
