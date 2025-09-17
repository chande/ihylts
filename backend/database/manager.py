import logging
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any, List
import json
import atexit

logger = logging.getLogger(__name__)

class DatabaseManager:

    pool = None

    def __init__(self, database_url: str, min_conn: int = 1, max_conn: int = 10):
        if not DatabaseManager.pool:
            try:
                DatabaseManager.pool = ThreadedConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    dsn=database_url
                )
                logger.info(f"Database connection pool created (min: {min_conn}, max: {max_conn})")
                atexit.register(self.close_all_connections)
            except psycopg2.Error as e:
                logger.error(f"Failed to create database connection pool: {e}")
                raise
        
        self.conn = None
        self.cursor = None

    def connect(self):
        try:
            if self.conn is None:
                self.conn = self.pool.getconn()
                self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                logger.debug("Acquired a database connection from the pool")
        except psycopg2.Error as e:
            logger.error(f"Failed to get connection from pool: {e}")
            raise

    def disconnect(self):
        if self.conn:
            try:
                if self.cursor:
                    self.cursor.close()
                self.pool.putconn(self.conn)
                logger.debug("Returned a database connection to the pool")
            except psycopg2.Error as e:
                logger.error(f"Error putting connection back to pool: {e}")
            finally:
                self.conn = None
                self.cursor = None

    def close_all_connections(self):
        if DatabaseManager.pool:
            DatabaseManager.pool.closeall()
            logger.info("All database connections in the pool have been closed")

    def get_latest_comic(self) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM comics ORDER BY date_added DESC LIMIT 1;"
        try:
            self.cursor.execute(query)
            latest_comic = self.cursor.fetchone()
            if latest_comic:
                logger.info(f"Latest comic found: {latest_comic['title']} ({latest_comic['date_added']})")
                return dict(latest_comic)
            else:
                logger.info("No comics found in the database yet.")
                return None
        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve latest comic: {e}")
            self.conn.rollback()
            return None
    
    def get_all_comics(self) -> List[Dict[str, Any]]:
        query = "SELECT * FROM comics ORDER BY publication_date DESC;"
        try:
            self.cursor.execute(query)
            comics = self.cursor.fetchall()
            logger.info(f"Retrieved {len(comics)} comics from database")
            return [dict(comic) for comic in comics]
        except psycopg2.Error as e:
            logger.error(f"Failed to retrieve all comics: {e}")
            self.conn.rollback()
            return []
    
    def insert_comic(self, comic_data: Dict[str, Any]) -> Optional[int]:
        query = """
            INSERT INTO comics (title, url, publication_date, panel_urls)
            VALUES (%(title)s, %(url)s, %(publication_date)s, %(panel_urls)s)
            ON CONFLICT (url) DO NOTHING
            RETURNING id;
        """
        try:
            data_to_insert = comic_data.copy()
            data_to_insert['panel_urls'] = json.dumps(data_to_insert['panel_urls'])
            
            self.cursor.execute(query, data_to_insert)
            result = self.cursor.fetchone()
            self.conn.commit()
            
            if result:
                comic_id = result['id']
                logger.info(f"Successfully inserted comic '{comic_data['title']}' with ID: {comic_id}")
                return comic_id
            else:
                logger.warning(f"Comic at {comic_data['url']} already exists. Skipping insertion.")
                return None
        except psycopg2.Error as e:
            logger.error(f"Failed to insert comic: {e}")
            self.conn.rollback()
            return None
    
    def update_comic(self, comic_id: int, updates: Dict[str, Any]) -> bool:
        try:
            set_clauses = []
            params = {'comic_id': comic_id}
            
            for key, value in updates.items():
                if key in ['text', 'processed']:
                    set_clauses.append(f"{key} = %({key})s")
                    if key == 'text' and isinstance(value, dict):
                        params[key] = json.dumps(value)
                    else:
                        params[key] = value
            
            if not set_clauses:
                logger.warning("No valid update fields provided")
                return False
            
            query = f"UPDATE comics SET {', '.join(set_clauses)} WHERE id = %(comic_id)s;"
            
            self.cursor.execute(query, params)
            self.conn.commit()
            
            if self.cursor.rowcount > 0:
                logger.info(f"Successfully updated comic ID {comic_id}")
                return True
            else:
                logger.warning(f"No comic found with ID {comic_id}")
                return False
                
        except psycopg2.Error as e:
            logger.error(f"Failed to update comic {comic_id}: {e}")
            self.conn.rollback()
            return False

