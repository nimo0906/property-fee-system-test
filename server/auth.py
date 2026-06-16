from server.auth_shared import *
from server.auth_part1 import AuthMixinPart1
from server.auth_part2 import AuthMixinPart2

class AuthMixin(AuthMixinPart1, AuthMixinPart2):
    pass
