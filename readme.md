# PyHub SDK

Um SDK Python padronizado para integração com múltiplas APIs de SMS (SMSHub, HeroSMS, SMS-Activate, SMSBower).


## 🚀 Tecnologias

- **Python 3.11+**
- **HTTPX**: Cliente HTTP moderno e assíncrono.
- **Pydantic**: Validação de dados e modelos padronizados.
- **Pytest**: Suíte de testes automatizados.

## 📦 Instalação

```bash
poetry install
```

## 🛠️ Como Usar

O SDK utiliza uma Factory (`PyHub`) para instanciar automaticamente o cliente correto com base no nome do provedor ou na URL da API.

### Inicialização

```python
from pyhub.sdk.api import PyHub

# Por nome do provedor
client = PyHub.get_client(provider="smshub", api_key="SUA_KEY")

# Ou automaticamente pela URL
client = PyHub.get_client(
    api_key="SUA_KEY", 
    base_url="https://hero-sms.com/stubs/handler_api.php"
)
```

### Operações Comuns

```python
# Verificar Saldo
balance = client.get_balance()
print(f"Saldo: {balance.amount} {balance.currency}")

# Consultar Preços (Padronizado)
prices = client.get_prices(service="tg")
for country in prices:
    print(f"País {country.country_id}: Min {country.services['tg'].min_price}")

# Comprar Número
activation = client.get_number(service="tg", country=0)
print(f"Número: {activation.phone_number} (ID: {activation.activation_id})")

# Buscar SMS
code = client.get_sms(activation.activation_id)
if code:
    print(f"Código recebido: {code}")

# Reativar Número Antigo
reactivation = client.reactivation_number("ID_ANTIGO")
```

## 🧪 Testes

```bash
poetry run pytest tests/test_sdk.py
```
