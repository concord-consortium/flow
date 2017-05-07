from . import Filter


class Operator(Filter):
    def __init__(self, block_spec):
        super(Operator, self).__init__(block_spec)

    def compute(self, inputs, params):
        result = inputs[0]
        if self.type == 'and':
            result = int(inputs[0] and inputs[1])
        elif self.type == 'or':
            result = int(inputs[0] or inputs[1])
        elif self.type == 'xor':
            result = int((inputs[0] > 0) != (inputs[1] > 0))
        elif self.type == 'nand':
            result = int(not (inputs[0] and inputs[1]))
        elif self.type == 'not':
            result = int(not inputs[0])
        elif self.type == 'plus':
            result = inputs[0] + inputs[1]
        elif self.type == 'minus':
            result = inputs[0] - inputs[1]
        elif self.type == 'times':
            result = inputs[0] * inputs[1]
        elif self.type == 'divided by':
            result = inputs[0] / inputs[1] if abs(inputs[1]) > 1e-8 else None
        elif self.type == 'absolute value':
            result = abs(inputs[0])
        elif self.type == 'equals':
            result = int(inputs[0] == inputs[1])
        elif self.type == 'not equals':
            result = int(inputs[0] != inputs[1])
        elif self.type == 'less than':
            result = int(inputs[0] < inputs[1])
        elif self.type == 'greater than':
            result = int(inputs[0] > inputs[1])
        return result
