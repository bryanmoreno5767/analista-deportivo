from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
import requests
import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

app = FastAPI(title="Filtro BetMines 60-65% +EV")

# Header simulando un navegador web estándar para acceder a las respuestas públicas de BetMines
HEADERS_BETMINES = {
    "User-Agent": "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://betmines.com/"
}

# ------------------------------------------------------------------
# UTILIDADES DE FECHA (HORA MÉXICO CDMX)
# ------------------------------------------------------------------

def obtener_fecha_valida(fecha_in: str) -> str:
    """Asegura el formato YYYY-MM-DD para la fecha seleccionada en tu Atajo."""
    if not fecha_in:
        return datetime.datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    fecha_in = fecha_in.strip()
    if "/" in fecha_in:
        partes = fecha_in.split("/")
        if len(partes) == 3 and len(partes[0]) == 2:
            return f"{partes[2]}-{partes[1]}-{partes[0]}"
    return fecha_in

def formatear_hora_cdmx(hora_utc_str: str) -> str:
    """Convierte la hora del evento a la Hora Central de México."""
    try:
        if not hora_utc_str:
            return "--:--"
        dt_utc = datetime.datetime.fromisoformat(hora_utc_str.replace("Z", "+00:00"))
        dt_cdmx = dt_utc.astimezone(ZoneInfo("America/Mexico_City"))
        return dt_cdmx.strftime("%H:%M")
    except Exception:
        return hora_utc_str[11:16] if len(hora_utc_str) >= 16 else "--:--"

# ------------------------------------------------------------------
# EXTRACCIÓN Y FILTRADO DE BETMINES (60% - 65%)
# ------------------------------------------------------------------

def consultar_y_filtrar_betmines(fecha_str: str) -> List[Dict[str, Any]]:
    """
    Consulta los partidos programados en BetMines para cualquier fecha (presente o futura)
    y extrae todos los mercados cuya probabilidad esté estrictamente entre 60% y 65%.
    """
    # Endpoint público de la API web de BetMines para partidos por fecha
    url_betmines = f"https://api.betmines.com/api/v2/fixtures/date/{fecha_str}"
    
    apuestas_filtradas = []

    try:
        resp = requests.get(url_betmines, headers=HEADERS_BETMINES, timeout=12)
        if resp.status_code != 200:
            # Respaldo si el endpoint primario cambia de estructura en fechas futuras
            url_betmines_alt = f"https://betmines.com/api/fixtures?date={fecha_str}"
            resp = requests.get(url_betmines_alt, headers=HEADERS_BETMINES, timeout=12)

        data = resp.json() if resp.status_code == 200 else []
        fixtures = data if isinstance(data, list) else data.get("response", data.get("data", []))

        for fix in fixtures:
            home = fix.get("homeTeam", {}).get("name") or fix.get("home_team", "Local")
            away = fix.get("awayTeam", {}).get("name") or fix.get("away_team", "Visitante")
            liga = fix.get("league", {}).get("name") or fix.get("competition", "Liga Profesional")
            hora_raw = fix.get("matchDate") or fix.get("date", "")
            hora_cdmx = formatear_hora_cdmx(str(hora_raw))

            # Extraer probabilidades de los distintos mercados de BetMines
            probs = fix.get("predictions", fix.get("probabilities", {}))
            
            # Evaluación de Mercados
            mercados_evaluar = [
                {"mercado": "1X2 - Local", "pick": f"Victoria {home}", "prob": float(probs.get("1", probs.get("home", 0)))},
                {"mercado": "1X2 - Empate", "pick": "Empate (X)", "prob": float(probs.get("X", probs.get("draw", 0)))},
                {"mercado": "1X2 - Visitante", "pick": f"Victoria {away}", "prob": float(probs.get("2", probs.get("away", 0)))},
                {"mercado": "Doble Oportunidad", "pick": "1X (Local o Empate)", "prob": float(probs.get("1X", 0))},
                {"mercado": "Doble Oportunidad", "pick": "X2 (Empate o Visitante)", "prob": float(probs.get("X2", 0))},
                {"mercado": "Goles", "pick": "Over 1.5 Goles", "prob": float(probs.get("over15", probs.get("over_15", 0)))},
                {"mercado": "Goles", "pick": "Over 2.5 Goles", "prob": float(probs.get("over25", probs.get("over_25", 0)))},
                {"mercado": "Goles", "pick": "Under 2.5 Goles", "prob": float(probs.get("under25", probs.get("under_25", 0)))},
                {"mercado": "Ambos Anotan", "pick": "BTTS - Sí", "prob": float(probs.get("btts_yes", probs.get("btts", 0)))},
                {"mercado": "Córners", "pick": "Over 8.5 Córners", "prob": float(probs.get("corners_over85", 0))},
                {"mercado": "Córners", "pick": "Over 9.5 Córners", "prob": float(probs.get("corners_over95", 0))},
            ]

            for m in mercados_evaluar:
                prob = m["prob"]
                # Normalizar probabilidad si viene en rango 0-1 en lugar de 0-100
                if 0 < prob <= 1.0:
                    prob = prob * 100
                
                # FILTRO ESTRICTO: Entre 60% y 65%
                if 60.0 <= prob <= 65.0:
                    apuestas_filtradas.append({
                        "partido": f"{home} vs {away}",
                        "home": home,
                        "away": away,
                        "liga": liga,
                        "hora": hora_cdmx,
                        "mercado": m["mercado"],
                        "pick": m["pick"],
                        "probabilidad": round(prob, 1)
                    })

    except Exception as e:
        print(f"Error extrayendo datos de BetMines: {e}")

    # Ordenar por probabilidad descendente dentro del rango
    return sorted(apuestas_filtradas, key=lambda x: x["probabilidad"], reverse=True)

# ------------------------------------------------------------------
# VISTA WEB OPTIMIZADA PARA TU ATAJO EN IPAD
# ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
@app.get("/analizar", response_class=HTMLResponse)
def analizar(fecha: str = Query(None)):
    fecha_proc = obtener_fecha_valida(fecha)
    picks = consultar_y_filtrar_betmines(fecha_proc)

    if not picks:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: -apple-system, sans-serif; background: #121212; color: #fff; padding: 20px; text-align: center; }}
                .box {{ background: #1e1e1e; border-radius: 12px; padding: 24px; border: 1px solid #333; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="box">
                <h3 style="color: #ffab00; margin-top: 0;">⚠️ Sin coincidencias en el rango 60% - 65%</h3>
                <p style="color: #bbb; font-size: 10pt;">
                    No se encontraron pronósticos de BetMines que caigan dentro del rango objetivo (60.0% a 65.0%) para la fecha <b>{fecha_proc}</b>.
                </p>
            </div>
        </body>
        </html>
        """

    # Generar tarjetas html de los partidos/mercados filtrados
    cards_html = ""
    for idx, item in enumerate(picks, 1):
        cards_html += f"""
        <div class="card">
            <div class="card-header">
                <span class="league">{item['liga']}</span>
                <span class="time">🕒 {item['hora']} CDMX</span>
            </div>
            
            <div class="match-title">{item['partido']}</div>
            
            <div class="pick-box">
                <div>
                    <div class="market-label">{item['mercado']}</div>
                    <div class="pick-name">{item['pick']}</div>
                </div>
                <div class="prob-badge">{item['probabilidad']}%</div>
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>BetMines 60%-65% Filter</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: #121212;
                color: #ffffff;
                margin: 0;
                padding: 14px;
            }}
            .header-box {{
                background: #1e1e1e;
                border: 1px solid #2e7d32;
                border-radius: 12px;
                padding: 14px;
                text-align: center;
                margin-bottom: 16px;
            }}
            .title {{
                color: #00e676;
                font-size: 13pt;
                font-weight: 800;
                margin: 0;
            }}
            .subtitle {{
                color: #b0bec5;
                font-size: 8.5pt;
                margin-top: 4px;
            }}
            .filter-info {{
                background: #263238;
                color: #ffab00;
                font-size: 8pt;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 20px;
                display: inline-block;
                margin-top: 8px;
            }}
            .card {{
                background: #1e1e1e;
                border-radius: 10px;
                padding: 12px;
                margin-bottom: 10px;
                border: 1px solid #2c2c2c;
            }}
            .card-header {{
                display: flex;
                justify-content: space-between;
                font-size: 8pt;
                margin-bottom: 6px;
            }}
            .league {{ color: #40c4ff; font-weight: bold; }}
            .time {{ color: #9e9e9e; }}
            .match-title {{
                font-size: 10.5pt;
                font-weight: 700;
                color: #fff;
                margin-bottom: 8px;
            }}
            .pick-box {{
                background: #181818;
                border-left: 4px solid #00e676;
                padding: 8px 12px;
                border-radius: 6px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .market-label {{ font-size: 7.5pt; color: #9e9e9e; text-transform: uppercase; }}
            .pick-name {{ font-size: 9.5pt; color: #00e676; font-weight: bold; }}
            .prob-badge {{
                background: #00e676;
                color: #000;
                font-weight: 800;
                font-size: 9.5pt;
                padding: 4px 8px;
                border-radius: 6px;
            }}
        </style>
    </head>
    <body>
        <div class="header-box">
            <div class="title">🎯 FILTRO BETMINES (+EV)</div>
            <div class="subtitle">FECHA: <b>{fecha_proc}</b> | HORA MÉXICO (CDMX)</div>
            <div class="filter-info">RANGO ACTIVO: 60.0% A 65.0% PROBABILIDAD</div>
        </div>

        {cards_html}
    </body>
    </html>
    """
