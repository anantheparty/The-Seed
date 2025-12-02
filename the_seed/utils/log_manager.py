import logging
import os
from datetime import datetime


class LogManager:
    _instance = None

    def __new__(
        cls,
        logfile_level: str = "debug",
        console_level: str | None = None,
        debug_mode: bool = False,
        log_dir: str = "Logs",
    ):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logger = logging.getLogger("AI_Assistant")
            cls._instance.logger.propagate = False
            cls._instance._formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            cls._instance._handlers_ready = False
            cls._instance._current_config = None
            cls._instance._apply_configuration(logfile_level, console_level, debug_mode, log_dir)
        return cls._instance

    @classmethod
    def configure(
        cls,
        *,
        logfile_level: str = "debug",
        console_level: str | None = None,
        debug_mode: bool = False,
        log_dir: str = "Logs",
    ) -> None:
        instance = cls()
        instance._apply_configuration(logfile_level, console_level, debug_mode, log_dir)

    def _apply_configuration(
        self,
        logfile_level: str,
        console_level: str | None,
        debug_mode: bool,
        log_dir: str,
    ) -> None:
        file_level = getattr(logging, logfile_level.upper(), logging.INFO)
        console_level_name = console_level or logfile_level
        console_level_value = getattr(logging, console_level_name.upper(), file_level)

        # debug_mode 可用于触发额外的调试行为（预留钩子）
        if debug_mode and console_level_value < logging.DEBUG:
            console_level_value = logging.DEBUG

        config_tuple = (file_level, console_level_value, log_dir)
        if getattr(self, "_current_config", None) == config_tuple and self._handlers_ready:
            return

        self.logger.setLevel(file_level)
        self._rebuild_handlers(file_level=file_level, console_level=console_level_value, log_dir=log_dir)
        self._current_config = config_tuple
        self._handlers_ready = True

    def _rebuild_handlers(self, *, file_level: int, console_level: int, log_dir: str) -> None:
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            handler.close()

        os.makedirs(log_dir, exist_ok=True)
        filename = os.path.join(log_dir, f"{datetime.now().strftime('%Y%m%d%H%M%S')}.log")

        file_handler = logging.FileHandler(filename=filename, encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(self._formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(self._formatter)

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    @classmethod
    def get_logger(cls) -> logging.Logger:
        instance = cls()
        if not instance._handlers_ready:
            instance._apply_configuration("debug", None, False, "Logs")
        return instance.logger