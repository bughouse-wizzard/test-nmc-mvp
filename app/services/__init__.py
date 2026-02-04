"""
Application services.

This package contains various services used by the application.
"""

from .scraper import ZakupkiSearchScraper, create_scraper

__all__ = ["ZakupkiSearchScraper", "create_scraper"]