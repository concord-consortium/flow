from flow.blocks.timer import Timer


def test_timer():
    params = [{'name': 'seconds_on', 'value': 5}, {'name': 'seconds_off', 'value': 5}]
    block_spec = {
        'name': 'timer',
        'id': 'timer',
        'type': 'timer',
        'params': params,
        'sources': [],
        'input_count': 0,
        'input_type': '',
        'output_type': '',
    }
    timer = Timer(block_spec)
    for i in range(20):
        timer.update()


if __name__ == '__main__':
    test_timer()
