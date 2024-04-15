from unittest.mock import Mock, patch

from django.test import TestCase, override_settings

from . import plausible
from .helpers import (
    check_cname_record,
    check_txt_record,
    compute_corners_from_kml_latlonbox,
    three_point_calibration_to_corners,
)


@override_settings(ANALYTICS_API_KEY=True)
class PlausibleTestCase(TestCase):
    @patch("curl_cffi.requests.get")
    def test_domain_setup(self, mock_get):
        mock_response = Mock()
        expected_dict = {}
        mock_response.json.return_value = expected_dict
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        self.assertTrue(plausible.domain_is_setup("example.com"))
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        self.assertFalse(plausible.domain_is_setup("example.com"))

    @patch("curl_cffi.requests.post")
    def test_create_domain(self, mock_post):
        mock_response = Mock()
        expected_dict = {}
        mock_response.json.return_value = expected_dict
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        self.assertTrue(plausible.create_domain("gps.example.com"))
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        self.assertFalse(plausible.create_domain("gps.example.com"))

    @patch("curl_cffi.requests.put")
    def test_change_domain(self, mock_put):
        mock_response = Mock()
        expected_dict = {}
        mock_response.json.return_value = expected_dict
        mock_response.status_code = 200
        mock_put.return_value = mock_response
        self.assertTrue(plausible.change_domain("olddomain.com", "gps.example.com"))
        mock_response.status_code = 400
        mock_put.return_value = mock_response
        self.assertFalse(plausible.change_domain("olddomain.com", "gps.example.com"))

    @patch("curl_cffi.requests.delete")
    def test_delete_domain(self, mock_delete):
        mock_response = Mock()
        expected_dict = {}
        mock_response.json.return_value = expected_dict
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        self.assertTrue(plausible.delete_domain("gps.example.com"))
        mock_response.status_code = 400
        mock_delete.return_value = mock_response
        self.assertFalse(plausible.delete_domain("gps.example.com"))


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

    def test_kml_cal(self):
        cal = compute_corners_from_kml_latlonbox(
            63.35268625254615,
            63.325978161823549,
            12.55481008348568,
            12.470815025221196,
            -5.6769774354892242,
        )
        self.assertEqual(
            cal,
            (
                (65.21144277090194, 15.781876945283638),
                (61.24478638169717, 66.38761575963139),
                (10.696053565129883, 60.0149162417611),
                (14.662709954334655, 9.409177427413347),
            ),
        )

    def test_check_dns(self):
        self.assertTrue(check_cname_record("live.kiilat.com"))
        self.assertTrue(check_txt_record("live.kiilat.com"))
