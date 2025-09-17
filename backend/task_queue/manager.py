import logging
from typing import Dict, Any
import pika
import os
import json

logger = logging.getLogger(__name__)

class QueueManager:
    
    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=os.environ.get("RABBITMQ_HOST", "localhost"))
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='analyzer_queue', durable=True)
    
    def send_message(self, message: Dict[str, Any]):
        self.channel.basic_publish(
            exchange='',
            routing_key='analyzer_queue',
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            ))
        logger.info(f"Sent message: {message}")

    def __del__(self):
        if self.connection:
            self.connection.close()

