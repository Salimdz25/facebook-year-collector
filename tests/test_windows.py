import unittest
from datetime import date

from src.windows import choose_window, iso_utc, normalize_page_url, storage_suffix


class WindowTests(unittest.TestCase):
    def test_initial_window(self):
        self.assertEqual(choose_window(date(2025, 1, 1), 3, 2025),
                         (date(2025, 1, 1), date(2025, 1, 4)))

    def test_final_window_stops_at_year_boundary(self):
        self.assertEqual(choose_window(date(2025, 12, 31), 3, 2025),
                         (date(2025, 12, 31), date(2026, 1, 1)))

    def test_utc_format(self):
        self.assertEqual(iso_utc(date(2025, 1, 1)), "2025-01-01T00:00:00Z")

    def test_independent_storage_for_pages_and_years(self):
        a = normalize_page_url("https://facebook.com/UC3SB/")
        self.assertEqual(a, "https://www.facebook.com/UC3SB")
        self.assertNotEqual(storage_suffix(a, 2025), storage_suffix(a, 2026))
        self.assertNotEqual(storage_suffix(a, 2025), storage_suffix("https://www.facebook.com/other", 2025))

    def test_non_facebook_url_rejected(self):
        with self.assertRaises(ValueError):
            normalize_page_url("https://other.example/UC3SB")


if __name__ == "__main__":
    unittest.main()
