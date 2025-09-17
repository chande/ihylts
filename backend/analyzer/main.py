import logging
import os
import pika
import time
import json
import requests
import re
from io import BytesIO
from typing import Dict, Any, Optional
import pytesseract
from PIL import Image

from database.manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ComicAnalyzer:

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def download_image(self, url: str) -> Optional[Image.Image]:
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            image = Image.open(BytesIO(response.content))
            logger.info(f"Successfully downloaded image from {url}")
            return image
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            return None
    
    def extract_text_from_image(self, image: Image.Image) -> str:
        try:
            # Convert to grayscale
            gray_image = image.convert('L')

            text = pytesseract.image_to_string(gray_image)
            text = text.strip()
            
            logger.info(f"Extracted text: {text[:100]}..." if len(text) > 100 else f"Extracted text: {text}")
            return text
        except Exception as e:
            logger.error(f"Failed to extract text from image: {e}")
            return ""
    
    def filter_copyright_text(self, text: str) -> str:
        if not text:
            return text
        
        copyright_pattern = r'(copyright|©)\s*\d{4}\s*Mike\s*Krahulik\s*(?:&|and)\s*Jerry\s*Holkins'
        
        url_pattern = r'www\.penny-arcade\.com'
        
        # Remove copyright text
        cleaned_text = re.sub(copyright_pattern, '', text, flags=re.IGNORECASE)
        
        # Remove URL
        cleaned_text = re.sub(url_pattern, '', cleaned_text, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and multiple spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
        
        return cleaned_text.strip()
    
    def process_comic_panels(self, panel_urls: Dict[str, Any]) -> Dict[str, Any]:
        text_data = {"num_panels": panel_urls.get("num_panels", 0)}
        
        num_panels = panel_urls.get("num_panels", 0)
        
        for i in range(1, num_panels + 1):
            panel_key = f"panel{i}"
            panel_url = panel_urls.get(panel_key)
            
            if not panel_url:
                logger.warning(f"No URL found for {panel_key}")
                text_data[panel_key] = ""
                continue
            
            image = self.download_image(panel_url)
            if not image:
                text_data[panel_key] = ""
                continue
            
            raw_text = self.extract_text_from_image(image)
            
            clean_text = self.filter_copyright_text(raw_text)
            
            text_data[panel_key] = clean_text
            logger.info(f"Processed {panel_key}: '{clean_text[:50]}...' " if len(clean_text) > 50 else f"Processed {panel_key}: '{clean_text}'")
        
        return text_data
    
    def analyze_comic(self, message_data: Dict[str, Any]) -> bool:
        try:
            comic_id = message_data.get("comic_id")
            title = message_data.get("title", "Unknown")
            panel_urls = message_data.get("panel_urls", {})

            if isinstance(panel_urls, str):
                logger.warning("panel_urls field is a string, attempting to parse as JSON.")
                try:
                    panel_urls = json.loads(panel_urls)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode panel_urls JSON string for comic ID {comic_id}")
                    return False
            
            logger.info(f"Starting analysis of comic ID {comic_id}: {title}")
            
            text_data = self.process_comic_panels(panel_urls)
            
            updates = {
                "text": text_data,
                "processed": True
            }
            
            success = self.db.update_comic(comic_id, updates)
            
            if success:
                logger.info(f"Successfully completed analysis of comic ID {comic_id}")
                return True
            else:
                logger.error(f"Failed to update database for comic ID {comic_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error analyzing comic: {e}")
            return False

def get_rabbitmq_connection():
    max_retries = 30
    retry_delay = 5
    retries = 0

    while retries < max_retries:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=os.environ.get("RABBITMQ_HOST", "localhost"))
            )
            logger.info("Successfully connected to RabbitMQ")
            return connection
        except pika.exceptions.AMQPConnectionError as e:
            logger.warning(f"Could not connect to RabbitMQ: {e}. Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retries += 1
    
    logger.error("Failed to connect to RabbitMQ after several retries. Exiting.")
    return None

def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable must be set")
        return
    
    db_manager = DatabaseManager(db_url)
    analyzer = ComicAnalyzer(db_manager)
    
    connection = get_rabbitmq_connection()
    if not connection:
        return

    channel = connection.channel()
    channel.queue_declare(queue='analyzer_queue', durable=True)

    def callback(ch, method, properties, body):
        try:
            logger.info(f"Received message: {body.decode()}")
            
            message_data = json.loads(body.decode())
            
            success = analyzer.analyze_comic(message_data)
            
            if success:
                logger.info("Comic analysis completed successfully")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            else:
                logger.error("Comic analysis failed")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message JSON: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue='analyzer_queue', on_message_callback=callback)

    logger.info('Waiting for messages. To exit press CTRL+C')
    try:
        db_manager.connect()
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info('Stopping analyzer service...')
        channel.stop_consuming()
        connection.close()
        db_manager.disconnect()

if __name__ == '__main__':
    main()
