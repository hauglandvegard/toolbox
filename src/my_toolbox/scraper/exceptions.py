class ScraperError(Exception):
    """Custom exception raised when the scraper fails to fetch or parse a page."""

    def __init__(self, message, url="", status_code=-1):
        super().__init__(message)
        self.url = url
        self.status_code = status_code
