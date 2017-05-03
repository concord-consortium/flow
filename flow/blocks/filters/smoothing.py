from . import Filter


class Smoothing(Filter):

    def __init__(self, block_spec):
        super(Smoothing, self).__init__(block_spec)
        self.default_moving_average_periods = 10
        self.period_history = []

    def compute(self, inputs, params):
        result = inputs[0]
        period_history_length = len(self.period_history)
        if (period_history_length > 0 and
                period_history_length >= self.default_moving_average_periods):
            self.period_history.pop(0)  # pop first item in the list
            period_history_length = period_history_length - 1
        self.period_history.append(result)
        moving_average = sum(iter(self.period_history))/(period_history_length + 1)
        return moving_average
