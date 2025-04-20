import logging
import sys
from rich.logging import RichHandler

LOG_FILE = "debate.log"

def setup_logger(level=logging.INFO, log_file=LOG_FILE):
    """Configures the root logger for the application."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(level) # Set the minimum level for the logger itself
    
    # Remove existing handlers to avoid duplicates if called multiple times
    # (Though ideally it should only be called once)
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- Console Handler (Rich) --- 
    # Only add handler if running interactively (not imported for tests?)
    # For simplicity, let's always add it for now.
    console_handler = RichHandler(
        rich_tracebacks=True, 
        markup=True, # Allow rich markup in log messages
        level=level # Set level for this handler
    )
    console_handler.setFormatter(formatter) # Use basic format for console too?
                                            # RichHandler does its own formatting, 
                                            # but setting formatter might be needed for levelname/name?
                                            # Let's try without setFormatter first for console.
    # logger.addHandler(console_handler)
    # Let's use a basic StreamHandler for console for now to match file format
    # and avoid potential double formatting with Rich console in main script.
    console_handler_basic = logging.StreamHandler(sys.stdout)
    console_handler_basic.setLevel(level)
    console_handler_basic.setFormatter(formatter)
    logger.addHandler(console_handler_basic)

    # --- File Handler --- 
    try:
        file_handler = logging.FileHandler(log_file, mode='a') # Append mode
        file_handler.setLevel(level) # Log everything at INFO level or above to file
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logging.error(f"Failed to set up file handler for {log_file}: {e}", exc_info=True)

    logging.info(f"Logger configured. Level: {logging.getLevelName(level)}. Log file: {log_file}")

# Example usage:
# if __name__ == '__main__':
#     setup_logger(level=logging.DEBUG)
#     logging.debug("This is a debug message.")
#     logging.info("This is an info message.")
#     logging.warning("This is a warning message.")
#     logging.error("This is an error message.")
#     try:
#         1 / 0
#     except ZeroDivisionError:
#         logging.exception("Caught an exception.") 