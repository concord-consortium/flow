import pytest
import PIL
from rhizo.extensions.camera import encode_image

from flow.blocks.filters.brightness import Brightness
from flow.blocks.filters.blur import Blur
from flow.blocks.filters.smoothing import Smoothing

brightness = Brightness(None)
blur = Blur(None)
smoothing = Smoothing(None)


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


def test_smoothing_values():
    data = [12.44, 17.1, 11.15, 12.38, 13.22,
            16.87, 16.14, 14.22, 13.08, 10.27]
    for item in data:
        moving_average = smoothing.round(smoothing.compute([item], None), 3)
    assert moving_average == 13.687

    smoothing.period_history = [13.54]
    data = [16.17, 11.25, 16.52, 14.87]
    for item in data:
        moving_average = smoothing.round(smoothing.compute([item], None), 2)
    assert moving_average == 14.47

    smoothing.period_history = []
    data = [16.17]
    for item in data:
        moving_average = smoothing.round(smoothing.compute([item], None), 2)
    assert moving_average == 16.17

    smoothing.period_history = [11.7, 14.92]
    data = [14.29, 14.71, 10.97, 17.7, 15.86, 14.63, 16.02, 13.29]
    for item in data:
        moving_average = smoothing.round(smoothing.compute([item], None), 3)
    assert moving_average == 14.409

    smoothing.period_history = []
    data = [16.17, 13.54, 11.25, 16.52, 14.87, 12.93, 13.18, 12.95, 10.09]
    for item in data:
        moving_average = smoothing.round(smoothing.compute([item], None), 1)
    assert moving_average == 13.5

    smoothing.period_history = []
    data = [16.17, 13.54, 11.25, 16.52]
    for item in data:
        moving_average = smoothing.round(smoothing.compute([item], None), 2)
    assert moving_average == 14.37
