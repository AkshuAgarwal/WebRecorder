class SiteDownError(Exception):
    def __init__(self) -> None:
        self.message = "The requested url server is down. Please try again later"
        self.status_code = 500

        super().__init__(self.message)


class PageNotFoundError(Exception):
    def __init__(self) -> None:
        self.message = "The requested page is not found"
        self.status_code = 404

        super().__init__(self.message)


class InvalidURLError(Exception):
    def __init__(self) -> None:
        self.message = (
            "The given URL is invalid or does not point to an existing website"
        )

        super().__init__(self.message)
