from typing import Optional
from pyhub.sdk.base.client import ClientBase


class SMSHubClient(ClientBase):
    """
    Client for SMSHub API.
    """

    def __init__(
        self,
        api_key: str,
        proxy: Optional[str] = None,
        timeout: int = 30,
        base_url: str = "https://smshub.org/stubs/handler_api.php"
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            proxy=proxy,
            timeout=timeout
        )
