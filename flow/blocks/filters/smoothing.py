from . import Filter


class Smoothing(Filter):
    def __init__(self, block_spec):
        super(Smoothing, self).__init__(block_spec)

    def compute(self, inputs, params):
        image_string = inputs[0]
        blur_amount = self.read_param(params, 'blur_amount')
        image = self.decode_image(image_string)
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_amount))

        return encode_image(image)
