import unittest
from unittest.mock import patch, MagicMock
from src.rss_scraper import (
    load_existing_data, save_data, clean_html, parse_rss_feed, 
    get_weekly_file_path, load_config, get_current_year_and_week, 
    load_existing_news_data, add_new_items, setup_logging, main,
    scrape_rss_feed, handle_request_exception, run, parse_rss_item,
    fetch_rss_feed
)
import os
import json
from datetime import datetime
import shutil
import requests
import xml.etree.ElementTree as ET
import logging

class TestRSSScraper(unittest.TestCase):

    def setUp(self):
        self.test_dir = 'test_data'
        os.makedirs(self.test_dir, exist_ok=True)
        self.test_file = os.path.join(self.test_dir, 'test.json')
        self.sample_data = [{'id': '1', 'title': 'Test Title', 'description': 'Test Description', 'category': 'Test Category', 'pub_date': 'Test Date'}]
        self.sample_xml = """
        <rss>
            <channel>
                <item>
                    <title>Test Title</title>
                    <description>Test Description</description>
                    <guid>1</guid>
                    <pubDate>Test Date</pubDate>
                </item>
            </channel>
        </rss>
        """
        self.config_path = os.path.join(self.test_dir, 'config.json')
        self.log_file = os.path.join(self.test_dir, 'output.log')
        self.config_data = {
            "categories": {
                "Test Category": "https://example.com/rss"
            },
            "base_folder": self.test_dir,
            "retry_count": 3,
            "retry_delay": 2,
            "log_file": "output.log"
        }
        with open(self.config_path, 'w') as file:
            json.dump(self.config_data, file)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_load_existing_data(self):
        with open(self.test_file, 'w') as file:
            json.dump(self.sample_data, file)
        data = load_existing_data(self.test_file)
        self.assertEqual(data, self.sample_data)

    def test_save_data(self):
        save_data(self.test_file, self.sample_data)
        with open(self.test_file, 'r') as file:
            data = json.load(file)
        self.assertEqual(data, self.sample_data)

    def test_clean_html(self):
        test_cases = [
            ("<p>This is a <b>test</b> description.</p>", "This is a test description."),
            ("<div><p>Another <a href='#'>link</a></p></div>", "Another link")
        ]
        for raw_html, expected_text in test_cases:
            with self.subTest(raw_html=raw_html):
                self.assertEqual(clean_html(raw_html), expected_text)

    def test_parse_rss_feed(self):
        expected_output = [{'id': '1', 'title': 'Test Title', 'description': 'Test Description', 'category': 'Test Category', 'pub_date': 'Test Date'}]
        self.assertEqual(parse_rss_feed(self.sample_xml, 'Test Category'), expected_output)

    def test_parse_rss_item_no_guid(self):
        item = ET.Element('item')
        ET.SubElement(item, 'title').text = 'Test Title'
        ET.SubElement(item, 'description').text = '<p>Test Description</p>'
        ET.SubElement(item, 'pubDate').text = 'Test Date'
        
        result = parse_rss_item(item, 'Test Category')
        expected_result = {
            'id': None,
            'title': 'Test Title',
            'description': 'Test Description',
            'category': 'Test Category',
            'pub_date': 'Test Date'
        }
        self.assertEqual(result, expected_result)

    def test_parse_rss_item_no_pub_date(self):
        item = ET.Element('item')
        ET.SubElement(item, 'title').text = 'Test Title'
        ET.SubElement(item, 'description').text = '<p>Test Description</p>'
        ET.SubElement(item, 'guid').text = '1'
        
        result = parse_rss_item(item, 'Test Category')
        expected_result = {
            'id': '1',
            'title': 'Test Title',
            'description': 'Test Description',
            'category': 'Test Category',
            'pub_date': None
        }
        self.assertEqual(result, expected_result)

    def test_get_weekly_file_path(self):
        year, week = 2024, 20
        expected_path = os.path.join(self.test_dir, 'news_2024_20.json')
        self.assertEqual(get_weekly_file_path(self.test_dir, year, week), expected_path)

    def test_get_weekly_file_path_creates_folder(self):
        year, week = 2024, 20
        base_folder = os.path.join(self.test_dir, 'non_existent_folder')
        expected_path = os.path.join(base_folder, 'news_2024_20.json')
        result_path = get_weekly_file_path(base_folder, year, week)
        self.assertTrue(os.path.exists(base_folder))
        self.assertEqual(result_path, expected_path)

    def test_load_config(self):
        config = load_config(self.config_path)
        self.assertEqual(config, self.config_data)

    @patch('src.rss_scraper.datetime')
    def test_get_current_year_and_week(self, mock_datetime):
        mock_datetime.now.return_value = datetime(2024, 5, 20)
        year, week = get_current_year_and_week()
        self.assertEqual((year, week), (2024, 21))

    def test_load_existing_news_data(self):
        with open(self.test_file, 'w') as file:
            json.dump(self.sample_data, file)
        existing_data, existing_ids = load_existing_news_data(self.test_file)
        self.assertEqual(existing_data, self.sample_data)
        self.assertEqual(existing_ids, {'1'})

    def test_add_new_items(self):
        new_items = [{'id': '2', 'title': 'New Title', 'description': 'New Description', 'category': 'Test Category', 'pub_date': 'New Date'}]
        existing_data = self.sample_data.copy()
        existing_ids = {'1'}
        added_count = add_new_items(new_items, existing_data, existing_ids)
        self.assertEqual(added_count, 1)
        self.assertEqual(len(existing_data), 2)
        self.assertEqual(existing_data[-1]['id'], '2')

    def test_add_new_items_existing_id(self):
        new_items = [{'id': '1', 'title': 'Duplicate Title', 'description': 'Duplicate Description', 'category': 'Test Category', 'pub_date': 'Duplicate Date'}]
        existing_data = self.sample_data.copy()
        existing_ids = {'1'}
        added_count = add_new_items(new_items, existing_data, existing_ids)
        self.assertEqual(added_count, 0)
        self.assertEqual(len(existing_data), 1)

    @patch('src.rss_scraper.setup_logging')
    @patch('src.rss_scraper.requests.get')
    def test_main_function(self, mock_get, mock_setup_logging):
        with self.suppress_logging():
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = self.sample_xml
            mock_get.return_value = mock_response

            expected_log_file_path = os.path.abspath(os.path.join(os.path.dirname(self.config_path), "..", "output.log"))

            main(self.config_path)

            mock_setup_logging.assert_called_once_with(expected_log_file_path)

            with open(self.log_file, 'w') as file:
                file.write("Script completed successfully")

            with open(self.log_file, 'r') as file:
                log_content = file.read()
            self.assertIn("Script completed successfully", log_content)

    @patch('src.rss_scraper.logging.getLogger')
    def test_main_logging_level(self, mock_get_logger):
        with self.suppress_logging():
            logger = MagicMock()
            mock_get_logger.return_value = logger

            main(self.config_path)

            logger.setLevel.assert_any_call(logging.INFO)
            logger.setLevel.assert_any_call(logging.ERROR)

    def test_setup_logging(self):
        log_file = os.path.join(self.test_dir, 'test.log')
        setup_logging(log_file)
        self.assertTrue(os.path.exists(log_file))

    @patch('src.rss_scraper.fetch_rss_feed')
    @patch('src.rss_scraper.handle_request_exception')
    def test_scrape_rss_feed_retries(self, mock_handle_request_exception, mock_fetch_rss_feed):
        with self.suppress_logging():
            mock_fetch_rss_feed.side_effect = requests.RequestException("Network error")
            result = scrape_rss_feed("http://example.com/rss", "Test Category", retries=2, delay=1)
            self.assertEqual(result, [])
            self.assertEqual(mock_handle_request_exception.call_count, 2)

    @patch('src.rss_scraper.fetch_rss_feed', side_effect=requests.RequestException("Network error"))
    @patch('src.rss_scraper.handle_request_exception')
    def test_scrape_rss_feed_exception(self, mock_handle_request_exception, mock_fetch_rss_feed):
        with self.suppress_logging():
            result = scrape_rss_feed("http://example.com/rss", "Test Category", retries=1, delay=1)
            self.assertEqual(result, [])
            mock_handle_request_exception.assert_called_once()
            called_args, called_kwargs = mock_handle_request_exception.call_args
            self.assertIsInstance(called_args[0], requests.RequestException)
            self.assertEqual(called_args[1], "http://example.com/rss")
            self.assertEqual(called_args[2], 0)
            self.assertEqual(called_args[3], 1)
            self.assertEqual(called_args[4], 1)

    @patch('src.rss_scraper.logging')
    @patch('src.rss_scraper.time.sleep', return_value=None)
    def test_handle_request_exception_retry(self, mock_sleep, mock_logging):
        with self.suppress_logging():
            e = requests.RequestException("Network error")
            handle_request_exception(e, "http://example.com/rss", 0, 2, 1)
            mock_logging.error.assert_called_with("Error fetching http://example.com/rss: Network error")
            mock_logging.info.assert_called_with("Retrying in 1 seconds...")
            mock_sleep.assert_called_with(1)

    @patch('src.rss_scraper.logging')
    def test_handle_request_exception_fail(self, mock_logging):
        with self.suppress_logging():
            e = requests.RequestException("Network error")
            handle_request_exception(e, "http://example.com/rss", 1, 2, 1)
            mock_logging.error.assert_any_call("Error fetching http://example.com/rss: Network error")
            mock_logging.error.assert_any_call("Failed to fetch http://example.com/rss after 2 attempts")

    @patch('sys.argv', ['rss_scraper.py', '--config', 'test_data/config.json'])
    @patch('src.rss_scraper.main')
    def test_run(self, mock_main):
        with self.suppress_logging():
            run()
            mock_main.assert_called_once_with('test_data/config.json')

    @patch('requests.get')
    def test_fetch_rss_feed_exception(self, mock_get):
        with self.suppress_logging():
            mock_get.side_effect = requests.RequestException("Network error")
            with self.assertRaises(requests.RequestException):
                fetch_rss_feed("http://example.com/rss", {"User-Agent": "test-agent"})
            mock_get.assert_called_once()

    # Context manager to suppress logging
    from contextlib import contextmanager
    @contextmanager
    def suppress_logging(self):
        logging.disable(logging.CRITICAL)
        try:
            yield
        finally:
            logging.disable(logging.NOTSET)

if __name__ == "__main__":
    unittest.main()

