from block import Block


# a basic timer block; turns on for a specified numbers of seconds then turns off for a specified number of seconds
class Timer(Block):

    def __init__(self, block_spec):
        super(Timer, self).__init__(block_spec)
        self.counter = 0
        params = block_spec['params']
        self.seconds_on = self.read_param(params, 'seconds_on')
        self.seconds_off = self.read_param(params, 'seconds_off')
        print('Timer init; seconds_on: %d, seconds_off: %d' % (self.seconds_on, self.seconds_off))

    # this overrides the update function in the Block class
    def update(self):
        if self.counter < self.seconds_on + self.seconds_off:
            self.counter += 1
        else:
            self.counter = 0
        if self.counter < self.seconds_on:
            self.value = 1
        else:
            self.value = 0
        self.stale = False
        print('Timer update counter: %d, value: %d' % (self.counter, self.value))
