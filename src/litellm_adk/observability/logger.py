import sys
from loguru import logger
from ..config.settings import settings

def setup_logger():
    """
    Configures loguru logger based on application settings.
    Supports both Human-readable text and Machine-readable JSON.
    """
    logger.remove()  # Remove default handler
    
    is_json = settings.log_format.lower() == "json"
    
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}" if not is_json else None,
        level=settings.log_level,
        serialize=is_json
    )
    return logger

# Initialize global logger
adk_logger = setup_logger()
adk_logger.info("LiteLLM ADK Logger Initialized")
