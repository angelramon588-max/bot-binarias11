import time
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime
import pytz

# ==========================================
# CONFIGURACIÓN DEL BOT Y TELEGRAM
# ==========================================
TELEGRAM_TOKEN = "8853627805:AAEMX2jxGFMWhda1rfZUk8-6zoNQquXrCwo"
CHAT_ID = "8686956027"

# Parámetros Estratégicos (Estructura de Mercado)
CHECK_INTERVAL = 60          # Revisa cada 60 segundos
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# Pares de divisas a monitorear
SYMBOLS = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "AUDUSD=X",
    "USDCAD=X",
    "EURJPY=X",
    "GBPJPY=X"
]

def send_telegram_message(message):
    """Envía un mensaje de texto a tu chat de Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Error enviando mensaje a Telegram: {e}")
        return False

def calculate_rsi(data, period=14):
    """Calcula el Índice de Fuerza Relativa (RSI)."""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def check_market_signals():
    """Analiza los pares y detecta oportunidades de entrada."""
    tz_py = pytz.timezone('America/Asuncion')
    now = datetime.now(tz_py)
    
    # Horario operativo: 07:00 a 17:00 (Hora Paraguay)
    if not (7 <= now.hour < 17):
        print(f"[{now.strftime('%H:%M:%S')}] Fuera de horario operativo (07:00 - 17:00). Espere...")
        return

    print(f"[{now.strftime('%H:%M:%S')}] Analizando mercado...")

    for symbol in SYMBOLS:
        try:
            clean_symbol = symbol.replace("=X", "")
            
            # Descarga datos de velas de 1 minuto
            df = yf.download(tickers=symbol, period="1d", interval="1m", progress=False)
            
            if df.empty or len(df) < RSI_PERIOD + 1:
                continue

            # Cálculo de RSI
            df['RSI'] = calculate_rsi(df, RSI_PERIOD)
            
            latest_rsi = df['RSI'].iloc[-1]
            latest_close = df['Close'].iloc[-1]
            
            # Formato de mensaje para señales
            if latest_rsi >= RSI_OVERBOUGHT:
                msg = (
                    f"🔴 **SEÑAL DE VENTA (PUT)** 🔴\n\n"
                    f"📌 **Par:** {clean_symbol}\n"
                    f"📊 **RSI:** {latest_rsi:.2f} (Sobrecompra)\n"
                    f"💵 **Precio:** {latest_close:.5f}\n"
                    f"⏱ **Temporalidad:** 1-5 Minutos\n"
                    f"🕒 **Hora:** {now.strftime('%H:%M:%S')}"
                )
                send_telegram_message(msg)
                print(f"Señal VENTA enviada para {clean_symbol}")
                
            elif latest_rsi <= RSI_OVERSOLD:
                msg = (
                    f"🟢 **SEÑAL DE COMPRA (CALL)** 🟢\n\n"
                    f"📌 **Par:** {clean_symbol}\n"
                    f"📊 **RSI:** {latest_rsi:.2f} (Sobrevenda)\n"
                    f"💵 **Precio:** {latest_close:.5f}\n"
                    f"⏱ **Temporalidad:** 1-5 Minutos\n"
                    f"🕒 **Hora:** {now.strftime('%H:%M:%S')}"
                )
                send_telegram_message(msg)
                print(f"Señal COMPRA enviada para {clean_symbol}")
                
        except Exception as e:
            print(f"Error analizando {symbol}: {e}")

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
if __name__ == "__main__":
    print("Iniciando Bot de Análisis de Mercado...")
    
    # Mensaje de prueba al encender
    send_telegram_message("🤖 **Bot iniciado exitosamente en la nube.**\nMonitoreando señales en horario 07:00 a 17:00.")
    
    while True:
        try:
            check_market_signals()
        except Exception as e:
            print(f"Error en el bucle principal: {e}")
        
        time.sleep(CHECK_INTERVAL)
