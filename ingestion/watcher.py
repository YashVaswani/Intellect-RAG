# ingestion/watcher.py
"""
Folder watcher — automatically ingests new files dropped into watch_folder/.
Uses the watchdog library for filesystem monitoring.
"""
import os
import time
import logging
import threading
import config

logger = logging.getLogger(__name__)


def _process_new_file(file_path: str):
    """Process a newly detected file."""
    try:
        from ingestion import ingest_document
        logger.info(f"Auto-ingesting: {file_path}")
        result = ingest_document(file_path)
        if result.get("success"):
            logger.info(f"Auto-ingested: {os.path.basename(file_path)} → {result['chunks_created']} chunks")
        else:
            logger.warning(f"Auto-ingestion failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"Auto-ingestion error: {e}")


def start_watcher():
    """
    Start watching the watch_folder/ directory for new files.
    Runs in a background thread.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class NewFileHandler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                ext = os.path.splitext(event.src_path)[1].lower()
                all_supported = config.SUPPORTED_DOCUMENT_TYPES + config.SUPPORTED_AUDIO_TYPES + config.SUPPORTED_IMAGE_TYPES
                if ext in all_supported:
                    # Wait a moment for the file to finish writing
                    time.sleep(2)
                    _process_new_file(event.src_path)

        watch_path = config.WATCH_FOLDER
        os.makedirs(watch_path, exist_ok=True)

        observer = Observer()
        observer.schedule(NewFileHandler(), watch_path, recursive=False)
        observer.daemon = True
        observer.start()

        logger.info(f"Folder watcher started: monitoring '{watch_path}/' for new files")
        return observer

    except ImportError:
        logger.warning("watchdog not installed — folder watching unavailable. Run: pip install watchdog")
        return None
    except Exception as e:
        logger.error(f"Failed to start folder watcher: {e}")
        return None
