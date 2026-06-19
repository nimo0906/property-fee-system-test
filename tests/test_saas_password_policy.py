import unittest

from server.saas_password_policy import (
    PASSWORD_MIN_LENGTH,
    password_length_error,
    password_meets_policy,
)


class TestSaasPasswordPolicy(unittest.TestCase):
    def test_password_policy_uses_single_minimum_length(self):
        self.assertEqual(PASSWORD_MIN_LENGTH, 8)
        self.assertFalse(password_meets_policy('short'))
        self.assertFalse(password_meets_policy(''))
        self.assertFalse(password_meets_policy(None))
        self.assertTrue(password_meets_policy('12345678'))
        self.assertEqual(password_length_error('新密码'), '新密码至少 8 位')
        self.assertEqual(password_length_error('临时密码'), '临时密码至少 8 位')


if __name__ == '__main__':
    unittest.main()
