from django.test import TestCase

from .helpers import three_point_calibration_to_corners


class HelperTestCase(TestCase):

    def test_calibration_conversion(self):
        cal = three_point_calibration_to_corners(
            "9.5480564597566|46.701263850274|1|1|9.5617738453051|46.701010852567|4961|1|9.5475331306949|46.687915214433|1|7016",
            4961,
            7016,
        )
        self.assertEqual(
            cal,
            [
                46.70127,
                9.54805,
                46.70101,
                9.56177,
                46.68766,
                9.56125,
                46.68792,
                9.54753,
            ],
        )
