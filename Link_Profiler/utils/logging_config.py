import logging.config
import logging
import os
import json
from typing import Dict, Any

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)

class ContextFilter(logging.Filter):
    """Add contextual information to log records."""
    
    def __init__(self, context: Dict[str, Any] = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record."""
        if not hasattr(record, 'extra_fields'):
            record.extra_fields = {}
        
        record.extra_fields.update(self.context)
        return True

class LoggingConfig:
    """Production-ready logging configuration."""
    
    @staticmethod
    def setup_logging(
        level: str = "INFO",
        log_file: Optional[str] = None,
        json_format: bool = False,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        context: Dict[str, Any] = None
    ):
        """
        Set up comprehensive logging configuration.
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (optional)
            json_format: Use JSON formatting
            max_file_size: Maximum file size before rotation
            backup_count: Number of backup files to keep
            context: Additional context to add to all logs
        """
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # Set level
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        root_logger.setLevel(numeric_level)
        
        # Create formatters
        if json_format:
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # Add context filter if provided
        if context:
            context_filter = ContextFilter(context)
            console_handler.addFilter(context_filter)
        
        root_logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            
            if context:
                file_handler.addFilter(context_filter)
            
            root_logger.addHandler(file_handler)
        
        # Error file handler (separate file for errors)
        if log_file:
            error_file = log_file.replace('.log', '_errors.log')
            error_handler = logging.handlers.RotatingFileHandler(
                error_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            
            if context:
                error_handler.addFilter(context_filter)
            
            root_logger.addHandler(error_handler)
        
        # Suppress noisy third-party loggers
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        
        logging.info(f"Logging configured: level={level}, json_format={json_format}, file={log_file}")
    
    @staticmethod
    def get_logger_with_context(name: str, **context) -> logging.Logger:
        """Get a logger with additional context."""
        logger = logging.getLogger(name)
        
        # Add context filter to all handlers
        context_filter = ContextFilter(context)
        for handler in logger.handlers:
            handler.addFilter(context_filter)
        
        return logger
