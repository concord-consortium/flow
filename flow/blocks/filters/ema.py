from . import Filter


class ExponentialMovingAverage(Filter):

    def __init__(self, block_spec):
        super(ExponentialMovingAverage, self).__init__(block_spec)
        self.default_moving_average_periods = 10
        self.period_history = []
        self.last_average = None

    def compute(self, inputs, params):
        new_average = 0
        result = inputs[0]
        period_history_length = len(self.period_history)
        moving_average_periods = self.read_param(params, 'period',
                                                 self.default_moving_average_periods)
        if (period_history_length > 0 and
                period_history_length >= moving_average_periods):
            self.period_history.pop(0)  # pop first item in the list
            period_history_length = period_history_length - 1
        self.period_history.append(result)

        if (self.last_average is not None):
            if(result is not None):
                alpha = 2.0 / (moving_average_periods + 1.0)
                new_average = result * alpha + self.last_average * (1 - alpha)
            else:
                new_average = self.last_average
        else:
            if(result is not None):
                new_average = result

        self.last_average = new_average

        # last_average = result
        # alpha = 2.0 / (moving_average_periods + 1.0)
        # for item in self.period_history:
        #     last_average = (item * alpha) + (last_average * (1.0-alpha))

        return new_average
