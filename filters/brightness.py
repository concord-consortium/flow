from filters import Filter
from PIL import Image, ImageEnhance
from rhizo.extensions.camera import encode_image


class Brightness(Filter):

    def compute(self, inputs, params):
        image_string = inputs[0]
        brightness = self.read_param_obj(params, "brightness_adjustment")
        old_range = brightness["max"] - brightness["min"]
        brightness_amount = brightness["value"]

        # Pillow upper brightness range scales very high
        # (1000 is still not pure white),
        # while a negative value scales small
        # (i.e. 0 is pure black),
        # but value of 1 is the original image.
        if brightness_amount > 0:
            brightness_amount = brightness_amount * 10

        # Pillow's comparable brightness range
        new_min = 0
        new_max = 2
        new_range = new_max - new_min

        brightness_amount = (
            ((brightness_amount - brightness["min"]) * new_range) /
            float(old_range)) + new_min

        image = self.decode_image(image_string)
        enhancer = ImageEnhance.Brightness(image)
        outImage = enhancer.enhance(brightness_amount)

        return encode_image(outImage)
