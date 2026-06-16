from server.backups_shared import *
from server.backups_part1 import BackupMixinPart1
from server.backups_part2 import BackupMixinPart2

class BackupMixin(BackupMixinPart1, BackupMixinPart2):
    pass
