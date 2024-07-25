import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set level to DEBUG to capture all log messages
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),  # Log to a file
        logging.StreamHandler()          # Also log to the console
    ]
)
