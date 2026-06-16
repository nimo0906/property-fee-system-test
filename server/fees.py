from server.fees_shared import *
from server.fees_part1 import FeeMixinPart1
from server.fees_part2 import FeeMixinPart2

class FeeMixin(FeeMixinPart1, FeeMixinPart2):
    pass
