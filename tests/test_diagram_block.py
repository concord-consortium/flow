import pytest
from ..diagram import Block, compute_decimal_places

temperature_block = Block({
            'id': 1,
            'name': 'temperature',
            'type': 'temperature',
            'sources': [],
            'input_count': 0,
            'output_count': 1,
            'input_type': None,
            'output_type': 'n',
            'value': 24.12
        })

numeric_block = Block({
            'id': 2,
            'name': 'number',
            'type': 'number_entry',
            'sources': [],
            'input_count': 0,
            'output_count': 1,
            'input_type': 'n',
            'output_type': 'n',
            'value': 11.12234
        })


def test_is_numeric():
    assert numeric_block.is_numeric() is True
    assert temperature_block.is_numeric() is True


def test_source_values():
    assert numeric_block.get_source_values() == []
    assert temperature_block.get_source_values() == []


def test_compute_value():
    assert numeric_block.compute_value([]) is None
    assert temperature_block.compute_value([]) is None


def test_compute_decimal_places():
    assert compute_decimal_places("1e-11") == 11
    assert compute_decimal_places("12341.9201") == 4
    assert compute_decimal_places(".000") == 3
