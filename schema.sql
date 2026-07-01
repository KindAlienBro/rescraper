-- Vorniity Distributed Scraper Database Schema
-- You can import this file directly into your Hostinger phpMyAdmin or SQL panel

CREATE TABLE IF NOT EXISTS results_cache_v2 (
    usn VARCHAR(20),
    url VARCHAR(255),
    data JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (usn, url)
);

CREATE TABLE IF NOT EXISTS subject_credits (
    subject_code VARCHAR(50) PRIMARY KEY,
    credits INT NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    start_usn VARCHAR(20) NOT NULL,
    end_usn VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS scrape_history (
    id VARCHAR(255) PRIMARY KEY,
    start_usn VARCHAR(20),
    end_usn VARCHAR(20),
    total_usns INT,
    completed INT,
    time_taken FLOAT,
    status VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
