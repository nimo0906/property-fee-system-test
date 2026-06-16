from server.payments_part1_group1 import PaymentMixinPart1Group1
from server.payments_part1_group2 import PaymentMixinPart1Group2

class PaymentMixinPart1(PaymentMixinPart1Group1, PaymentMixinPart1Group2):
    pass
