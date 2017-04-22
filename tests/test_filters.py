import pytest
import PIL
from rhizo.extensions.camera import encode_image

from ..filters.brightness import Brightness
from ..filters.blur import Blur


brightness = Brightness()
blur = Blur()


def test_brightness_range_mid_value():
    assert brightness.convert_value_to_new_range(0.0, -100, 100, 0, 2) == 1


def test_brightness_range_min_value():
    assert brightness.convert_value_to_new_range(-100, -100, 100, 0, 2) == 0


def test_brightness_range_max_value():
    assert brightness.convert_value_to_new_range(100, -100, 100, 0, 2) == 2


def test_brightness_range_mid_max_value():
    assert brightness.convert_value_to_new_range(50, -100, 100, 0, 2) == 1.5


def test_brightness_range_mid_min_value():
    assert brightness.convert_value_to_new_range(-50, -100, 100, 0, 2) == 0.5


def test_brightness_pillow_image_returned():
    inputs = [encode_image(PIL.Image.new('RGB', (100, 100), color=0))]
    params = [{'name': 'brightness_adjustment',
              'value': 50.0, 'min': -100, 'max': 100}]

    image = brightness.compute(inputs, params)
    assert isinstance(image, PIL.Image.Image) is False
    assert isinstance(image, (str, unicode)) is True


def test_blur_pillow_image_returned():
    inputs = [encode_image(PIL.Image.new('RGB', (100, 100), color=0))]
    params = [{'name': 'blur_amount',
              'value': 50.0, 'min': -100, 'max': 100}]

    image = blur.compute(inputs, params)
    assert isinstance(image, PIL.Image.Image) is False
    assert isinstance(image, (str, unicode)) is True
