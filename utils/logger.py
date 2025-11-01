import os
import sys
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Optional
import json


class StructuredLogger:
    def __init__(
        self,
        name: str,
        log_dir: str = "./data/logs",
        log_level: str = "INFO",
        log_format: str = "json",
        log_file_prefix: str = "agent-run",
        max_size_mb: int = 100,
        backup_count: int = 10
    ):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_format = log_format.lower()
        self.log_file_prefix = log_file_prefix
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.log_level)
        
        if self.logger.handlers:
            return
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_filename = f"{log_file_prefix}-{timestamp}.log"
        log_file_path = self.log_dir / log_filename
        
        max_bytes = max_size_mb * 1024 * 1024
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_formatter = JsonFormatter() if self.log_format == "json" else logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(pathname)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        self.current_log_file = str(log_file_path)
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs):
        extra = {
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }
        self.logger.log(level, message, extra=extra)
    
    def log_agent_start(self, agent_name: str, task: Optional[str] = None):
        self.info(
            f"Agent '{agent_name}' started",
            event="agent_start",
            agent_name=agent_name,
            task=task
        )
    
    def log_agent_end(self, agent_name: str, success: bool = True, duration: Optional[float] = None):
        self.info(
            f"Agent '{agent_name}' completed",
            event="agent_end",
            agent_name=agent_name,
            success=success,
            duration=duration
        )
    
    def log_action(self, action: str, details: Optional[dict] = None):
        self.info(
            f"Action: {action}",
            event="action",
            action=action,
            details=details or {}
        )
    
    def log_retry(self, attempt: int, max_attempts: int, reason: Optional[str] = None):
        self.warning(
            f"Retry attempt {attempt}/{max_attempts}",
            event="retry",
            attempt=attempt,
            max_attempts=max_attempts,
            reason=reason
        )
    
    def log_error(self, error: Exception, context: Optional[dict] = None):
        self.error(
            f"Error: {str(error)}",
            event="error",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context or {}
        )


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info']:
                log_data[key] = value
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


_logger_instance: Optional[StructuredLogger] = None


def get_logger(
    name: Optional[str] = None,
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file_prefix: Optional[str] = None,
    max_size_mb: Optional[int] = None,
    backup_count: Optional[int] = None
) -> StructuredLogger:
    global _logger_instance
    
    if _logger_instance is None:
        from dotenv import load_dotenv
        load_dotenv()
        
        name = name or os.getenv('LOG_NAME', 'agent-b')
        log_dir = log_dir or os.getenv('LOG_DIR', './data/logs')
        log_level = log_level or os.getenv('LOG_LEVEL', 'INFO')
        log_format = log_format or os.getenv('LOG_FORMAT', 'json')
        log_file_prefix = log_file_prefix or os.getenv('LOG_FILE_PREFIX', 'agent-run')
        max_size_mb = max_size_mb or int(os.getenv('LOG_MAX_SIZE_MB', '100'))
        backup_count = backup_count or int(os.getenv('LOG_BACKUP_COUNT', '10'))
        
        _logger_instance = StructuredLogger(
            name=name,
            log_dir=log_dir,
            log_level=log_level,
            log_format=log_format,
            log_file_prefix=log_file_prefix,
            max_size_mb=max_size_mb,
            backup_count=backup_count
        )
    
    return _logger_instance
