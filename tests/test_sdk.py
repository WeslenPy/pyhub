import pytest
from unittest.mock import MagicMock, patch
from pyhub.sdk.api import PyHub
from pyhub.sdk.base.schemas import Balance, NumberActivation, ActivationStatus, CountryPrices

@pytest.fixture
def mock_httpx():
    with patch("httpx.Client") as mock:
        client_instance = mock.return_value.__enter__.return_value
        yield client_instance

def test_pyhub_factory():
    client = PyHub.get_client(provider="smshub", api_key="test_key")
    from pyhub.sdk.smshub import SMSHubClient
    assert isinstance(client, SMSHubClient)
    
    client = PyHub.get_client(base_url="https://hero-sms.com/stubs/handler_api.php", api_key="test_key")
    from pyhub.sdk.herosms import HeroSMSClient
    assert isinstance(client, HeroSMSClient)

def test_get_balance(mock_httpx):
    mock_httpx.get.return_value.text = "ACCESS_BALANCE:100.50"
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smshub", api_key="test_key")
    balance = client.get_balance()
    
    assert isinstance(balance, Balance)
    assert balance.amount == 100.50
    mock_httpx.get.assert_called_once()

def test_get_number(mock_httpx):
    mock_httpx.get.return_value.text = "ACCESS_NUMBER:12345:79991234567"
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smshub", api_key="test_key")
    activation = client.get_number(service="tg", country=0)
    
    assert isinstance(activation, NumberActivation)
    assert activation.activation_id == "12345"
    assert activation.phone_number == "79991234567"

def test_get_status(mock_httpx):
    mock_httpx.get.return_value.text = "STATUS_OK:123456"
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smshub", api_key="test_key")
    status = client.get_status("12345")
    
    assert isinstance(status, ActivationStatus)
    assert status.status == "STATUS_OK"
    assert status.code == "123456"

def test_reactivation_number(mock_httpx):
    # Mock for getExtraActivation
    mock_httpx.get.return_value.text = "ACCESS_NUMBER:67890:79990000000"
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smshub", api_key="test_key")
    # We also need to mock the set_status call inside reactivation_number (via active_status)
    # Since we are mocking httpx.get, it will be called twice
    
    activation = client.reactivation_number("12345")
    
    assert activation.activation_id == "67890"
    assert mock_httpx.get.call_count == 2 # 1 for getExtraActivation, 1 for setStatus

def test_sms_bower_v2(mock_httpx):
    mock_httpx.get.return_value.text = '{"0": {"tg": {"10.5": 100, "15.0": 50}}}'
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smsbower", api_key="test_key")
    prices = client.get_prices_v2(service="tg")
    
    assert len(prices) == 1
    assert prices[0].country_id == 0
    service_price = prices[0].services["tg"]
    assert service_price.min_price == 10.5
    assert service_price.max_price == 15.0
    assert service_price.count == 150
    assert isinstance(service_price.cost, list)

def test_get_prices_standard(mock_httpx):
    mock_httpx.get.return_value.text = '{"0": {"tg": {"cost": 10.5, "count": 100}}}'
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smshub", api_key="test_key")
    prices = client.get_prices(service="tg")
    
    assert len(prices) == 1
    assert prices[0].country_id == 0
    assert prices[0].services["tg"].cost == 10.5
    assert prices[0].services["tg"].min_price == 10.5

def test_sms_bower_v3(mock_httpx):
    mock_httpx.get.return_value.text = '{"0": {"tg": {"prov1": {"price": 12.0, "count": 10}, "prov2": {"price": 15.0, "count": 5}}}}'
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smsbower", api_key="test_key")
    prices = client.get_prices_v3(service="tg")
    
    assert len(prices) == 1
    tg_data = prices[0].services["tg"]
    assert tg_data.min_price == 12.0
    assert tg_data.max_price == 15.0
    assert tg_data.count == 15
    assert tg_data.cost == [12.0, 15.0]

def test_get_top_countries_by_service_hero(mock_httpx):
    # Format according to get_free_prices.json
    mock_httpx.get.return_value.text = '{"tg": {"0": {"country": 0, "price": 10.0, "count": 100}}}'
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="herosms", api_key="test_key")
    # herosms get_prices uses get_top_countries_by_service internally
    prices = client.get_prices(service="tg")
    
    assert len(prices) == 1
    assert prices[0].country_id == 0
    assert prices[0].services["tg"].cost == 10.0

def test_api_error_handling(mock_httpx):
    mock_httpx.get.return_value.text = "BAD_KEY"
    mock_httpx.get.return_value.raise_for_status = MagicMock()
    
    client = PyHub.get_client(provider="smshub", api_key="wrong_key")
    with pytest.raises(ValueError, match="API Error: BAD_KEY"):
        client.get_balance()
