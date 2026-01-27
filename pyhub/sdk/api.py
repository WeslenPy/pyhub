from typing import Optional, Dict, Type
from .smshub import SMSHubClient
from .herosms import HeroSMSClient
from .smsactivate import SMSActivateClient
from .smsbower import SMSBowerClient
from .base.client import ClientBase


class PyHub:
    """
    Central manager to identify and instantiate the correct SMS API client.
    """
    
    _providers: Dict[str, Type[ClientBase]] = {
        "smshub": SMSHubClient,
        "herosms": HeroSMSClient,
        "smsactivate": SMSActivateClient,
        "smsbower": SMSBowerClient,
        "hero": HeroSMSClient, # Alias
        "bower": SMSBowerClient, # Alias
    }

    _url_patterns: Dict[str, str] = {
        "smshub.org": "smshub",
        "hero-sms.com": "herosms",
        "sms-activate": "smsactivate",
        "smsbower": "smsbower",
    }

    @classmethod
    def get_client(
        cls,
        api_key: str,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        proxy: Optional[str] = None,
        timeout: int = 30,
        **kwargs
    ) -> ClientBase:
        """
        Identifies the provider (by name or URL) and returns the standardized client.
        
        Args:
            api_key: API key for the service
            provider: Optional name of the provider (smshub, herosms, smsactivate)
            base_url: Optional base URL (used to identify provider if name is missing)
            proxy: Optional proxy string
            timeout: Request timeout in seconds
            **kwargs: Additional arguments
        """
        # 1. Identify provider key
        provider_key = None
        
        if provider:
            provider_key = provider.lower().replace("-", "").replace("_", "").strip()
        elif base_url:
            # Detect provider by URL pattern
            url_lower = base_url.lower()
            for pattern, key in cls._url_patterns.items():
                if pattern in url_lower:
                    provider_key = key
                    break
            else:
                if not provider_key:
                    provider_key = "smshub"
        
        if not provider_key:
            raise ValueError(
                "Could not identify provider. Please provide 'provider' name or 'base_url'."
            )

        # 2. Get client class
        client_class = cls._providers.get(provider_key)
        
        if not client_class:
            supported = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Provider '{provider_key}' is not supported. "
                f"Available providers: {supported}"
            )
            
        # 3. Instantiate
        # If base_url was provided, we pass it to override the default if needed
        if base_url:
            kwargs["base_url"] = base_url

        return client_class(
            api_key=api_key, 
            proxy=proxy, 
            timeout=timeout, 
            **kwargs
        )


__all__ = [
    "PyHub",
    "SMSHubClient",
    "HeroSMSClient",
    "SMSActivateClient",
    "SMSBowerClient",
]
