"""
Zakupki.gov.ru scraping services.

This package provides functionality for scraping contract data from zakupki.gov.ru.
"""

from .search import ZakupkiSearchScraper, create_scraper

__all__ = ["ZakupkiSearchScraper", "create_scraper"]