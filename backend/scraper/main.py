import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
import requests

from database.manager import DatabaseManager
from task_queue.manager import QueueManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PennyArcadeScraper:
    
    def __init__(self, db_connection: DatabaseManager, queue_manager: QueueManager, base_url: str):
        self.db = db_connection
        self.queue = queue_manager
        self.base_url = base_url
        self.session = None  # Will hold requests session

    def initialize_session(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive',
        })
        logger.info("HTTP session initialized")
    
    def fetch_comic_page(self, url: str) -> Optional[str]:
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()  # Raise an exception for bad status codes
            logger.info(f"Successfully fetched {url}")
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def extract_comic_metadata(self, html: str, url: str) -> Optional[Dict[str, Any]]:
        try:
            soup = BeautifulSoup(html, 'lxml')

            title_tag = soup.find('title')
            title_text = title_tag.text.strip() if title_tag else "Untitled"
            
            suffix = " - Penny Arcade"
            if title_text.endswith(suffix):
                title = title_text[:-len(suffix)].strip()
            else:
                title = title_text

            date_tag = soup.find('p', class_='details date')
            date_str = date_tag.text.strip() if date_tag else None
            publication_date = datetime.strptime(date_str, '%B %d, %Y') if date_str else None

            panel_urls = self.extract_panel_urls(html)

            comic_data = {
                "title": title,
                "url": url,
                "publication_date": publication_date,
                "panel_urls": panel_urls,
            }
            
            logger.info(f"Extracted metadata for: {title}")
            return comic_data

        except Exception as e:
            logger.error(f"Error extracting metadata from {url}: {e}")
            return None
    
    def extract_panel_urls(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'lxml')
        comic_area = soup.find('div', class_='comic-area')
        panels_data = {"num_panels": 0}
        
        if comic_area:
            panels = comic_area.find_all('div', class_='comic-panel')
            panels_data["num_panels"] = len(panels)
            for i, panel in enumerate(panels):
                img = panel.find('img')
                if not img:
                    continue

                panel_url = ""
                if img.has_attr('srcset'):
                    srcset = img['srcset']
                    sources = [s.strip().split() for s in srcset.split(',')]
                    for src in sources:
                        if len(src) == 2 and src[1] == '2x':
                            panel_url = src[0]
                            break
                
                # Fallback to the standard src if no 2x URL was found
                if not panel_url and img.has_attr('src'):
                    panel_url = img['src']

                if panel_url:
                    panels_data[f"panel{i+1}"] = panel_url
        
        return panels_data
    
    def get_next_comic_url(self, most_recent_comic: Optional[Dict[str, Any]]) -> Optional[str]:
        if most_recent_comic:
            latest_comic_url = most_recent_comic.get('url')
            if not latest_comic_url:
                logger.error("Latest comic from DB has no URL.")
                return None

            html = self.fetch_comic_page(latest_comic_url)
            if not html:
                return None

            soup = BeautifulSoup(html, 'lxml')
            next_button = soup.find('a', class_='orange-btn newer')

            if next_button and next_button.has_attr('href'):
                next_comic_path = next_button['href']
                next_comic_url = f"{self.base_url}{next_comic_path}"
                logger.info(f"Next comic URL to scrape: {next_comic_url}")
                return next_comic_url
            else:
                logger.info("No 'newer' button found. We might be at the latest comic.")
                return None
        else:
            first_comic_url = 'https://www.penny-arcade.com/comic/1998/11/18/the-sin-of-long-load-times'
            logger.info(f"No comics in DB, starting with first comic: {first_comic_url}")
            return first_comic_url
    
    def scrape_comic(self, url: str):
        logger.info(f"Scraping comic: {url}")
        
        html = self.fetch_comic_page(url)
        if not html:
            return

        comic_data = self.extract_comic_metadata(html, url)
        if not comic_data:
            return

        comic_id = self.db.insert_comic(comic_data)
        if comic_id:
            logger.info(f"Comic '{comic_data['title']}' added to database with ID: {comic_id}")
            
            message = {
                "comic_id": comic_id, 
                "url": comic_data["url"],
                "panel_urls": comic_data["panel_urls"],
                "title": comic_data["title"]
            }
            self.queue.send_message(message)
            
            return comic_id
        else:
            logger.error(f"Failed to add comic '{comic_data['title']}' to database.")
            return None
    
    def run_scraping_cycle(self):
        logger.info("Starting scraping cycle")
        
        try:
            self.db.connect()
            for i in range(2):
                # 1. Get the most recent comic from DB
                most_recent_comic = self.db.get_latest_comic()

                # 2. Determine next comic to scrape
                next_comic_url = self.get_next_comic_url(most_recent_comic)

                if not next_comic_url:
                    logger.info("Scraping cycle complete: No new comics to fetch.")
                    return
                
                # 3. Fetch and extract data
                self.scrape_comic(next_comic_url)
                
                logger.info("Scraping cycle completed")
            
        except Exception as e:
            logger.error(f"Error during scraping cycle: {e}")
            raise
        finally:
            self.db.disconnect()


def main():
    db_url = os.environ.get("DATABASE_URL")
    base_url = os.environ.get("PENNY_ARCADE_BASE_URL")
    scrape_interval = int(os.environ.get("SCRAPE_INTERVAL_SECONDS", 600))

    if not db_url or not base_url:
        logger.error("DATABASE_URL and PENNY_ARCADE_BASE_URL must be set")
        sys.exit(1)

    db_manager = DatabaseManager(db_url)
    queue_manager = QueueManager()
    
    scraper = PennyArcadeScraper(
        db_connection=db_manager,
        queue_manager=queue_manager,
        base_url=base_url
    )
    scraper.initialize_session()

    while True:
        scraper.run_scraping_cycle()
        logger.info(f"Waiting for {scrape_interval} seconds before next cycle...")
        time.sleep(scrape_interval)



if __name__ == "__main__":
    main()
