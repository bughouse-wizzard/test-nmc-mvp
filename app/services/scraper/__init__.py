"""
Scraper module for web scraping functionality.
"""

from .search import ZakupkiSearchScraper, search_contracts_async

__all__ = ["ZakupkiSearchScraper", "search_contracts_async"]