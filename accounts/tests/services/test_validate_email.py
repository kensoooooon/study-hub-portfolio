from django.test import SimpleTestCase

from accounts.services.exceptions import InvalidEmailError
from accounts.services.validate_email import validate_email_address


class ValidateEmailAddressTests(SimpleTestCase):
    def test_accepts_valid_email(self):
        validate_email_address("test@example.com")

    def test_rejects_none(self):
        with self.assertRaises(InvalidEmailError):
            validate_email_address(None)

    def test_rejects_empty_string(self):
        with self.assertRaises(InvalidEmailError):
            validate_email_address("")

    def test_rejects_invalid_format(self):
        with self.assertRaises(InvalidEmailError):
            validate_email_address("abc")

    def test_rejects_whitespace_only_string(self):
        with self.assertRaises(InvalidEmailError):
            validate_email_address("   ")
