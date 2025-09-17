CREATE TABLE IF NOT EXISTS comics (
    id SERIAL PRIMARY KEY,
    title VARCHAR(500),
    url VARCHAR(1000) UNIQUE NOT NULL,
    publication_date TIMESTAMP,
    text JSONB, 
    panel_urls JSONB,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_comics_title ON comics USING gin(to_tsvector('english', title));
CREATE INDEX idx_comics_publication_date ON comics(publication_date);
CREATE INDEX idx_comics_processed ON comics(processed);
CREATE INDEX idx_comics_date_added ON comics(date_added);

-- Create GIN index on the text JSONB column for full-text search
CREATE INDEX idx_comics_text ON comics USING gin(text);
