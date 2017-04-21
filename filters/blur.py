from filters import Filter
from PIL import Image, ImageFilter
from rhizo.extensions.camera import encode_image


class Blur(Filter):

    def compute(self, inputs, params):
        image_string = inputs[0]
        blur_amount = self.read_param(params, 'blur_amount')
        image = self.decode_image(image_string)
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_amount))

        return encode_image(image)
