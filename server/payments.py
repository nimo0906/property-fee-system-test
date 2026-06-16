from server.payments_shared import *
from server.payments_part1 import PaymentMixinPart1
from server.payments_part2 import PaymentMixinPart2

class PaymentMixin(PaymentMixinPart1, PaymentMixinPart2):
    pass
