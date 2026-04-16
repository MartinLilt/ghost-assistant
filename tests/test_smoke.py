import unittest

from opp_server import greet


class SmokeTest(unittest.TestCase):
    def test_greet_default(self) -> None:
        self.assertEqual(greet(), "Hello, world!")


if __name__ == "__main__":
    unittest.main()

