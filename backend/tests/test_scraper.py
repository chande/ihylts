import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)


class TestScraperFunctions(unittest.TestCase):
    """Test scraper functionality with mocked dependencies"""
    
    def setUp(self):
        """Set up test environment with mocked dependencies"""
        # Mock the database and queue manager modules before importing scraper
        self.mock_db_module = MagicMock()
        self.mock_queue_module = MagicMock()
        
        sys.modules['database.manager'] = self.mock_db_module
        sys.modules['task_queue.manager'] = self.mock_queue_module
        
        # Create mock classes
        self.mock_db_module.DatabaseManager = Mock()
        self.mock_queue_module.QueueManager = Mock()
        
        from scraper.main import PennyArcadeScraper
        self.PennyArcadeScraper = PennyArcadeScraper
        
        self.mock_db = Mock()
        self.mock_queue = Mock()
        self.scraper = self.PennyArcadeScraper(
            db_connection=self.mock_db,
            queue_manager=self.mock_queue,
            base_url="https://www.penny-arcade.com"
        )

    def test_extract_comic_metadata_with_valid_html(self):
        mock_html = """
        <html>
        <head>
            <title>The SIN Of Long Load Times - Penny Arcade</title>
        </head>
        <body>
            <p class="details date">November 18, 1998</p>
            <div class="comic-area">
                <div class="comic-panel">
                    <img src="https://assets.penny-arcade.com/comics/panels/test.jpg" alt="">
                </div>
            </div>
        </body>
        </html>
        """
        
        url = "https://www.penny-arcade.com/comic/1998/11/18/test"
        result = self.scraper.extract_comic_metadata(mock_html, url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "The SIN Of Long Load Times")
        self.assertEqual(result['url'], url)
        self.assertEqual(result['publication_date'], datetime(1998, 11, 18))
        self.assertIn('panel_urls', result)

    def test_extract_comic_metadata_no_suffix(self):
        mock_html = """
        <html>
        <head>
            <title>Just A Title</title>
        </head>
        <body>
            <p class="details date">November 18, 1998</p>
        </body>
        </html>
        """
        
        url = "https://www.penny-arcade.com/comic/test"
        result = self.scraper.extract_comic_metadata(mock_html, url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "Just A Title")

    def test_extract_comic_metadata_no_title(self):
        mock_html = """
        <html>
        <body>
            <p class="details date">November 18, 1998</p>
        </body>
        </html>
        """
        
        url = "https://www.penny-arcade.com/comic/test"
        result = self.scraper.extract_comic_metadata(mock_html, url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "Untitled")

    def test_extract_comic_metadata_no_date(self):
        mock_html = """
        <html>
        <head>
            <title>Test Comic - Penny Arcade</title>
        </head>
        <body>
        </body>
        </html>
        """
        
        url = "https://www.penny-arcade.com/comic/test"
        result = self.scraper.extract_comic_metadata(mock_html, url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['title'], "Test Comic")
        self.assertIsNone(result['publication_date'])

    def test_extract_panel_urls_three_panels(self):
        mock_html = """
        <div class="comic-area">
            <a id="comic-panels" class="three-panel alt" href="/comic/1998/11/25/john-romero-artiste">
                <div class="comic-panel">
                    <img src="https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p1.jpg" 
                         srcset="https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p1.jpg 1x,https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p1@2x.jpg 2x" alt="">
                </div>
                <div class="comic-panel">
                    <img src="https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p2.jpg" 
                         srcset="https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p2.jpg 1x,https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p2@2x.jpg 2x" alt="">
                </div>
                <div class="comic-panel">
                    <img src="https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p3.jpg" 
                         srcset="https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p3.jpg 1x,https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p3@2x.jpg 2x" alt="">
                </div>
            </a>
        </div>
        """
        
        result = self.scraper.extract_panel_urls(mock_html)
        
        self.assertEqual(result['num_panels'], 3)
        self.assertEqual(result['panel1'], "https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p1@2x.jpg")
        self.assertEqual(result['panel2'], "https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p2@2x.jpg")
        self.assertEqual(result['panel3'], "https://assets.penny-arcade.com/comics/panels/19981118-3eI0Y0JV-p3@2x.jpg")

    def test_extract_panel_urls_no_srcset(self):
        mock_html = """
        <div class="comic-area">
            <div class="comic-panel">
                <img src="https://assets.penny-arcade.com/comics/panels/test-p1.jpg" alt="">
            </div>
            <div class="comic-panel">
                <img src="https://assets.penny-arcade.com/comics/panels/test-p2.jpg" alt="">
            </div>
        </div>
        """
        
        result = self.scraper.extract_panel_urls(mock_html)
        
        self.assertEqual(result['num_panels'], 2)
        self.assertEqual(result['panel1'], "https://assets.penny-arcade.com/comics/panels/test-p1.jpg")
        self.assertEqual(result['panel2'], "https://assets.penny-arcade.com/comics/panels/test-p2.jpg")

    def test_extract_panel_urls_no_comic_area(self):
        mock_html = """
        <div>
            <p>Some other content</p>
        </div>
        """
        
        result = self.scraper.extract_panel_urls(mock_html)
        
        self.assertEqual(result['num_panels'], 0)

    def test_extract_panel_urls_empty_panels(self):
        mock_html = """
        <div class="comic-area">
            <p>No panels here</p>
        </div>
        """
        
        result = self.scraper.extract_panel_urls(mock_html)
        
        self.assertEqual(result['num_panels'], 0)


if __name__ == '__main__':
    unittest.main()
