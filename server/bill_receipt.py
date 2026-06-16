from server.bill_receipt_shared import *
from server.bill_receipt_part1 import BillReceiptMixinPart1
from server.bill_receipt_part2 import BillReceiptMixinPart2

class BillReceiptMixin(BillReceiptMixinPart1, BillReceiptMixinPart2):
    pass
