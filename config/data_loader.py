import os
import json
from core.logger import logger

def load_guest_form_data():
    """Load configuration from JSON file"""
    try:
        # Navigate up from config/data_loader.py to project root
        project_root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(
            project_root,
            'data',
            'guest_form_data.json'
        )
        with open(config_path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")
        return data
    except Exception as e:
        logger.error(f"Failed to load config JSON: {e}")
        return None
