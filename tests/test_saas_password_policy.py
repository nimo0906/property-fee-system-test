import unittest

from server.saas_password_policy import (
    PASSWORD_MIN_LENGTH,
    password_change_error,
    password_length_error,
    password_meets_policy,
    password_reset_error,
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

    def test_password_policy_rejects_same_old_and_new_password(self):
        self.assertEqual(password_change_error('same-password', 'same-password'), '新密码不能与原密码相同')
        self.assertIsNone(password_change_error('old-password', 'new-password'))

    def test_password_policy_rejects_same_reset_password(self):
        self.assertEqual(password_reset_error(True), '临时密码不能与当前密码相同')
        self.assertIsNone(password_reset_error(False))


if __name__ == '__main__':
    unittest.main()
