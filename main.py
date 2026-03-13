import json
import math
import statistics
from datetime import datetime
from typing import Any
import requests
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = ('https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=IBM&apikey=demo')

TRADING_DAY_YEAR = 252 #Dias úteis por ano
VOLATILITY_WINDOW = 21 #Janela de 21 dias úteis no mês

# fetch_data responsável pela requisição da API
def fetch_data() -> dict[str, Any]:
    """
    Realiza GET na API Alpha Vantage e retorna o dicionário
    'Time Series (Daily)'
    Raises:
        requests.HTTPError: se o status code não for 200.
        KeyError: Se a chave esperada não existir na resposta
    """
    try:
        response = requests.get(API_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "Time Series (Daily)" not in data:
            raise KeyError(
                "Chave 'Time Series (Daily)' não encontrada na resposta da API"
                f"Reposta recebida {json.dumps(data, indent=2)[:500]}"
            )
        return data["Time Series (Daily)"]
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar dados: {e}")
        raise
    
# Uma função responsável pela extração e processamento dos dados da API
def extract_sorted_closes(raw_series: dict[str, Any]) -> list[tuple[str, float]]:
    """
    Extração do fechamento do valor de (4.close) e retorna em uma
lista de tuplas(data_iso, close) ordenada cronológicamente (mais antigo - mais recente)
    """
    closes = [
        (date_str, float(values["4. close"]))
        for date_str, values in raw_series.items()
    ]

    closes.sort(key=lambda x: x[0]) #Ordenação por data
    return closes

# Cálculo percentual dos retornos diários
def compute_daily_returns(closes: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """
    Cálculo de variação percentual dos retornos diários
    retorno_diário = (preco-hoje - preco_ontem) / preco_ontem

    Retorna uma lista (data, retorno) a partir do segundo dia
    """
    returns = []
    for i in range(1, len(closes)):
        date_str = closes[i][0]
        prev_close = closes[i -1][1]
        curr_close = closes[i][1]
        daily_return = (curr_close - prev_close) / prev_close
        returns.append((date_str, daily_return))
    return returns

# Soma cumulativa dos retornos diários
def compute_cumulative_returns(daily_return: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """
    Cálculo cumulativos dos percentuais de retorno diário
    runnig_sum recebe o valor zerado dos percentuais diários e vai somando com
    daily_return como percentual cumulativo
    """
    cumulative = []
    running_sum = 0.0

    for date_str, ret in daily_return:
        running_sum += ret
        cumulative.append((date_str, round(running_sum, 6)))
    return cumulative

# Médias dos devios padrões
def compute_annualized_volatily(daily_returns: list[tuple[str, float]], window: int = VOLATILITY_WINDOW,) -> list[tuple[str, float]]:
    """
    Calcula a volatilidade anual em uma janela móvel (window)
    anual = diario x 252 (dias úteis anuais)
    """

    volatilities = []
    annualization_factor = math.sqrt(TRADING_DAY_YEAR)

    for i in range(window, len(daily_returns) + 1):
        window_return = [r for _, r in daily_returns[i - window: i]]
        date_str = daily_returns[i - 1][0]

        daily_std = statistics.stdev(window_return)
        annualization_vol = daily_std * annualization_factor
        volatilities.append((date_str, round(annualization_vol, 6)))

    return volatilities

def save_to_json(data: list[tuple[str, float]], filepath: str, value_key: str) -> None:
    """
    Serializa a lista de (data, valor) em JSON no formato:
    [{"date": "2024-01-02", "<value_key>": 0.0123}, ...]
    """

    records = [{"date": d, value_key: v} for d, v in data]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"[OK] {filepath} salvo com {len(records)} registros!")

def main() -> None:
    print("=" * 60)
    print("Case Técnico - IBM (Alpha Vantage)")
    print("=" * 60)

    # Resultados fetch
    print("\n[1/4] Buscando dados da API Alpha Vantage")
    raw_series = fetch_data()
    print(f"    Recebidos {len(raw_series)} registros diários...")

    # Extraindo dados da API
    print("[2/4] Extraindo e ordenando preços do fechamento...")
    closes = extract_sorted_closes(raw_series)
    print(f"    Período: {closes[0][0]} -> {closes[-1][0]}")

    # Cálculos
    print("[3/4] Calculando retornos e volatilidade...")
    daily_returns = compute_daily_returns(closes)
    cumulative = compute_cumulative_returns(daily_returns)
    volatility = compute_annualized_volatily(daily_returns)

    print(f"    Retornos diários: {len(daily_returns)} pontos")
    print(f"    Retorno acumulado: {len(cumulative)} pontos")
    print(f"    Volatilidade 21d: {len(volatility)} pontos")

    # Persistências dos dados
    print("[4/4] Salvando arquivos JSON...")
    save_to_json(cumulative, "retorno_acumulado.json", "retorno_acumulado")
    save_to_json(volatility, "volatilidade.json", "volatilidade_anualizada")
    print("\nPipeline concluída com sucesso!")
    print(" Abra index.html no navegador para visualizar os gráficos")

if __name__ == "__main__":
    main()