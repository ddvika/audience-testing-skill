import unittest
from audience_core.browser import validate_action


class WaitPolicyTests(unittest.TestCase):
    def test_bounded_wait_requires_no_target(self):
        self.assertTrue(validate_action({'type':'wait','seconds':10},{},{'https://example.com'}).allowed)

    def test_invalid_waits_never_reach_browser(self):
        for seconds in (True,0,11,float('nan'),float('inf'),'10'):
            self.assertFalse(validate_action({'type':'wait','seconds':seconds},{},{'https://example.com'}).allowed)


if __name__ == '__main__':
    unittest.main()
