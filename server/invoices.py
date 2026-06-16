from server.invoices_shared import *
from server.invoices_part1 import InvoiceMixinPart1
from server.invoices_part2 import InvoiceMixinPart2

class InvoiceMixin(InvoiceMixinPart1, InvoiceMixinPart2):
    pass
