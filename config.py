"""
config.py
---------
Central configuration for the Smart Warehouse Storage Allocation System.
All tunable constants (allowed enum values, upload limits, DB path, etc.)
live here so the rest of the codebase can import a single source of truth.
"""

import os

# Absolute path to the project root (folder containing this file)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base Flask configuration."""

    # Secret key used to sign session cookies / flash messages
    SECRET_KEY = os.environ.get("WAREHOUSE_SECRET_KEY", "smart-warehouse-dev-secret-key-2024")

    # SQLite database stored in the project root
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload handling
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"txt"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload size

    # Domain enumerations used across parser / allocation / templates
    VALID_PRIORITIES = ["High", "Medium", "Low"]
    VALID_STORAGE_TYPES = ["Normal", "Fragile", "Cold", "Hazardous"]
    VALID_FRAGILE_FLAGS = ["Yes", "No"]
    VALID_TEMPERATURE_REQUIREMENTS = ["None", "Cold", "Frozen"]

    # Allocation algorithm identifiers -> friendly display names
    ALGORITHMS = {
        "first_fit": "First Fit",
        "best_fit": "Best Fit",
        "worst_fit": "Worst Fit",
        "priority_based": "Priority Based Allocation",
        "space_optimized": "Space Optimized Allocation",
        "weight_balanced": "Weight Balanced Allocation",
    }

    # Default warehouse rack layout (used to seed the database on first run)
    DEFAULT_RACKS = [
        # rack_id, length(cm), width(cm), height(cm), max_weight(kg), rack_type
        {"rack_id": "Rack A", "length": 200, "width": 150, "height": 250, "max_weight": 1000, "rack_type": "Normal"},
        {"rack_id": "Rack B", "length": 150, "width": 100, "height": 200, "max_weight": 500, "rack_type": "Fragile"},
        {"rack_id": "Rack C", "length": 180, "width": 120, "height": 220, "max_weight": 800, "rack_type": "Cold"},
        {"rack_id": "Rack D", "length": 220, "width": 160, "height": 260, "max_weight": 1200, "rack_type": "Hazardous"},
    ]

    # Number of expected comma separated fields in each dataset row
    EXPECTED_FIELD_COUNT = 11
