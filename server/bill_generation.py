from server.bill_generation_shared import *
from server.bill_generation_part1 import BillGenerationMixinPart1
from server.bill_generation_part2 import BillGenerationMixinPart2

class BillGenerationMixin(BillGenerationMixinPart1, BillGenerationMixinPart2):
    pass
