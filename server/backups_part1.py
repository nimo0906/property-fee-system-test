from server.backups_part1_group1 import BackupMixinPart1Group1
from server.backups_part1_group2 import BackupMixinPart1Group2

class BackupMixinPart1(BackupMixinPart1Group1, BackupMixinPart1Group2):
    pass
