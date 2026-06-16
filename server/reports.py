from server.reports_shared import *
from server.reports_part1 import ReportMixinPart1
from server.reports_part2 import ReportMixinPart2
from server.reports_part3 import ReportMixinPart3
from server.reports_exports import ReportExportMixin

class ReportMixin(ReportMixinPart1, ReportMixinPart2, ReportMixinPart3, ReportExportMixin):
    pass
