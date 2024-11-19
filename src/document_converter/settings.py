import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IMAGE_RESOLUTION_SCALE = 1
MAX_TOKENS = 256
TEMPERATURE = 0.3
TOP_P = 0.95