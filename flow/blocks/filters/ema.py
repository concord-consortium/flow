from . import Filter


class ExponentialMovingAverage(Filter):

    def __init__(self, block_spec):
        super(ExponentialMovingAverage, self).__init__(block_spec)
        self.moving_average_periods = 10
        self.period_history = []

    def compute(self, inputs, params):
        result = inputs[0]
        period_history_length = len(self.period_history)
        if (period_history_length > 0 and
                period_history_length >= self.moving_average_periods):
            self.period_history.pop(0)  # pop first item in the list
            period_history_length = period_history_length - 1
        self.period_history.append(result)

        last_average = result
        alpha = 2.0 / (self.moving_average_periods + 1.0)
        for item in self.period_history:
            #print "AVERAGE: ", item, alpha, last_average, (1.0-alpha)
            last_average = (item * alpha) + (last_average * (1.0-alpha))

        return last_average
