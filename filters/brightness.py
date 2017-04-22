from . import Filter
from PIL import Image, ImageEnhance
from rhizo.extensions.camera import encode_image


class Brightness(Filter):

    def compute(self, inputs, params):
        image_string = inputs[0]
        brightness = self.read_param_obj(params, "brightness_adjustment")
        brightness_amount = brightness["value"]
        old_min = brightness["min"]
        old_max = brightness["max"]

        # Pillow upper brightness range scales very high
        # (1000 is still not pure white),
        # while a negative value scales small
        # (0 is pure black),
        # but value of 1 is the original image.
        if brightness_amount > 0:
            brightness_amount = brightness_amount * 10

        # Pillow's comparable brightness range
        new_min = 0
        new_max = 2

        # Convert brightness to Pillow's (PIL) brightness range
        brightness_amount = self.convert_value_to_new_range(
            brightness_amount,
            old_min, old_max,
            new_min, new_max)

        image = self.decode_image(image_string)
        enhancer = ImageEnhance.Brightness(image)
        outImage = enhancer.enhance(brightness_amount)

        return encode_image(outImage)

    def convert_value_to_new_range(self, value,
                                   old_min, old_max,
                                   new_min, new_max):
        new_range = new_max - new_min
        old_range = old_max - old_min
        value = (((value - old_min) * new_range) / float(old_range)) + new_min
        return value
