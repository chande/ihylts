import os
import logging
import gzip
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from io import BytesIO
from prometheus_flask_exporter import PrometheusMetrics

from database.manager import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
metrics = PrometheusMetrics(app)

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    logger.error("DATABASE_URL environment variable must be set")
    exit(1)

db_manager = DatabaseManager(db_url)

@app.before_request
def before_request():
    db_manager.connect()

@app.teardown_request
def teardown_request(exception=None):
    db_manager.disconnect()

def gzip_response(data):
    json_str = json.dumps(data)
    
    # Create gzipped content
    buffer = BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb') as f:
        f.write(json_str.encode('utf-8'))
    
    compressed_data = buffer.getvalue()
    
    response = app.response_class(
        compressed_data,
        mimetype='application/json',
        headers={'Content-Encoding': 'gzip'}
    )
    
    return response

@app.route('/api/comics/searchable')
def get_searchable_comics():
    try:
        comics = db_manager.get_all_comics()
        
        searchable = []
        for comic in comics:
            text_content = ""
            if comic.get('text'):
                if isinstance(comic['text'], str):
                    text_content = comic['text']
                elif isinstance(comic['text'], dict):
                    text_parts = []
                    for key, value in comic['text'].items():
                        if key.startswith('panel') and isinstance(value, str):
                            text_parts.append(value)
                    text_content = ' '.join(text_parts)
            
            searchable_comic = {
                'id': comic['id'],
                'title': comic['title'],
                'text': text_content,
                'url': comic['url'],
                'date': comic['publication_date'].isoformat() if comic['publication_date'] else None
            }
            searchable.append(searchable_comic)
        
        logger.info(f"Returning {len(searchable)} comics for search")
        return gzip_response(searchable)
        
    except Exception as e:
        logger.error(f"Error getting searchable comics: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
