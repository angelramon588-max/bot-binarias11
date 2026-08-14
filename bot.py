import time
from datetime import datetime
import pandas as pd
import pytz
import requests
import yfinance as yf

# ==========================================
# CONFIGURACIÓN DEL BOT
# ==========================================
TELEGRAM_TOKEN = "TU_TELEGRAM_TOKEN_AQUI"  # Poner tu token aquí
CHAT_ID = "TU_CHAT_ID_AQUI"  # Poner tu ID de chat aquí

PARES = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "AUDUSD=X",
    "USDCAD=X",
    "USDBRL=X",
    "GC=F",
]

ZONA_PARAGUAY = pytz.timezone("America/Asuncion")
INVERSION_POR_OPERACION = 1.0  # $1 USD por operación
PAGO_RETORNO = 0.85  # 85% promedio de pago

# Control y Seguridad
ultimas_alertas = {p: None for p in PARES}
historial_operaciones = []
historial_señales_hora = []
resumen_enviado_hoy = False
LIMITE_SEÑALES_POR_HORA = 5  # Máximo 5 alertas por hora


def enviar_alerta(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando mensaje: {e}")


def verificar_seguridad():
    ahora = datetime.now()
    global historial_señales_hora
    historial_señales_hora = [
        t for t in historial_señales_hora if (ahora - t).total_seconds() < 3600
    ]
    return len(historial_señales_hora) < LIMITE_SEÑALES_POR_HORA


def calcular_indicadores(df):
    df["EMA_200"] = df["Close"].ewm(span=200, adjust=False).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def verificar_6_velas(df):
    velas = df.iloc[-7:-1]
    verdes = (velas["Close"] > velas["Open"]).all()
    rojas = (velas["Close"] < velas["Open"]).all()
    if verdes:
        return "6_VERDES"
    if rojas:
        return "6_ROJAS"
    return "NINGUNO"


def evaluar_resultado_operacion(df, tipo_operacion):
    vela_resultado = df.iloc[-1]
    cierre = vela_resultado["Close"]
    apertura = vela_resultado["Open"]
    if tipo_operacion == "CALL":
        return "WIN" if cierre > apertura else "LOSS"
    elif tipo_operacion == "PUT":
        return "WIN" if cierre < apertura else "LOSS"
    return "LOSS"


def enviar_resumen_diario(ahora_py):
    global resumen_enviado_hoy, historial_operaciones
    if resumen_enviado_hoy or len(historial_operaciones) == 0:
        return

    wins = sum(1 for op in historial_operaciones if op["resultado"] == "WIN")
    losses = sum(1 for op in historial_operaciones if op["resultado"] == "LOSS")
    total_ops = wins + losses

    ganancia_bruta = wins * (INVERSION_POR_OPERACION * PAGO_RETORNO)
    pérdida_total = losses * INVERSION_POR_OPERACION
    beneficio_neto = ganancia_bruta - pérdida_total
    winrate = (wins / total_ops * 100) if total_ops > 0 else 0
    signo = "+" if beneficio_neto >= 0 else ""

    mensaje_resumen = (
        f"📊 *RESUMEN DIARIO DE OPERACIONES* 📊\n"
        f"📅 *Fecha:* `{ahora_py.strftime('%Y-%m-%d')}`\n"
        f"⏰ *Horario:* 07:00 AM - 17:00 PM (Paraguay)\n\n"
        f"📈 *Total Operaciones:* `{total_ops}`\n"
        f"✅ *Ganadas (WIN):* `{wins}`\n"
        f"❌ *Perdidas (LOSS):* `{losses}`\n"
        f"🎯 *Efectividad:* `{winrate:.1f}%`\n\n"
        f"💵 *Inversión por Op:* `${INVERSION_POR_OPERACION:.2f} USD`\n"
        f"💰 *BENEFICIO NETO TOTAL:* `{signo}${beneficio_neto:.2f} USD`\n\n"
        f"🤖 _Bot finalizado por el día de hoy._"
    )
    enviar_alerta(mensaje_resumen)
    resumen_enviado_hoy = True


def escanear_mercado():
    global resumen_enviado_hoy, historial_operaciones, historial_señales_hora

    ahora_py = datetime.now(ZONA_PARAGUAY)
    hora_actual = ahora_py.hour

    if hora_actual == 0:
        resumen_enviado_hoy = False
        historial_operaciones = []

    if hora_actual >= 17:
        if not resumen_enviado_hoy and len(historial_operaciones) > 0:
            enviar_resumen_diario(ahora_py)
        return

    if hora_actual < 7:
        return

    for par in PARES:
        try:
            df = yf.download(tickers=par, period="1d", interval="1m", progress=False)
            if df.empty or len(df) < 200:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = calcular_indicadores(df)
            patron_velas = verificar_6_velas(df)

            vela_cerrada = df.iloc[-2]
            timestamp_vela = df.index[-2]

            if ultimas_alertas[par] == timestamp_vela:
                continue

            precio = float(vela_cerrada["Close"])
            rsi = float(vela_cerrada["RSI"])
            nombre_par = par.replace("=X", "").replace("=F", "")

            tipo_entrada = None
            if patron_velas == "6_ROJAS" and rsi < 35:
                tipo_entrada = "CALL"
            elif patron_velas == "6_VERDES" and rsi > 65:
                tipo_entrada = "PUT"

            if tipo_entrada:
                if not verificar_seguridad():
                    if len(historial_señales_hora) == LIMITE_SEÑALES_POR_HORA:
                        enviar_alerta(
                            "⚠️ *¡LÍMITE DE SEGURIDAD ALCANZADO!* ⚠️\n"
                            "Se han detectado más de 5 señales en 1 hora. Mercado muy volátil. Pausando alertas."
                        )
                    continue

                resultado = evaluar_resultado_operacion(df, tipo_entrada)
                historial_operaciones.append(
                    {"par": nombre_par, "tipo": tipo_entrada, "resultado": resultado}
                )
                historial_señales_hora.append(datetime.now())

                emoji = "🟢" if tipo_entrada == "CALL" else "🔴"
                texto_tipo = (
                    "COMPRA (CALL / ARRIBA)"
                    if tipo_entrada == "CALL"
                    else "VENTA (PUT / ABAJO)"
                )

                msg = (
                    f"{emoji} *SEÑAL DE {texto_tipo}* {emoji}\n"
                    f"📱 *Plataformas:* Quotex / IQ Option\n\n"
                    f"🔤 *Activo:* `{nombre_par}`\n"
                    f"📊 *Patrón:* 6 Velas Consecutivas\n"
                    f"📈 *RSI:* `{rsi:.2f}`\n"
                    f"💵 *Precio Cierre:* `{precio:.5f}`\n"
                    f"⏱ *Expiración:* 1 Minuto (M1)\n"
                    f"⏰ *Hora PY:* `{ahora_py.strftime('%H:%M:%S')}`\n\n"
                    f"💵 *Apuesta:* $1.00 USD | *Resultado Eval:* `{resultado}`"
                )
                enviar_alerta(msg)
                ultimas_alertas[par] = timestamp_vela

        except Exception as e:
            print(f"Error procesando {par}: {e}")


if __name__ == "__main__":
    print("Bot de Binarias iniciado.")
    enviar_alerta("🤖 Bot iniciado y monitoreando en la nube (07:00 AM - 17:00 PM PY).")
    while True:
        escanear_mercado()
        time.sleep(30)
