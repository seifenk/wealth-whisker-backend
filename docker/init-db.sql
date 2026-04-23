-- Initialize TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create initial schema
CREATE SCHEMA IF NOT EXISTS wealthwhisker;

-- Set default timezone
SET timezone = 'Asia/Shanghai';