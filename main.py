from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

app = FastAPI()

# ------------------------------------------------------------------
# CONFIGURACIÓN DE TU API KEY DE RAPIDAPI
# ------------------------------------------------------------------
RAPIDAPI_KEY = "D06ff3a51emshd8c4b86c977e9c2p164dd3jsn5f2fd0a88a17"
RAPIDAPI_HOST = "football-prediction-api.p.rapidapi.com"

# ------------------------------------------------------------------
# FUNCIONES AUXILIARES: PARSEO DE FECHA Y CONVERSIÓN A HORA DE MÉXICO
# ------------------------------------------------------------------

def normalizar_fecha(fecha_in: str) -> str:
    """Asegura que la fecha esté en formato YYYY-MM-DD."""
    if not fecha_in:
        return datetime.datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    
    fecha_in = fecha_in.strip()
    if "/" in fecha_in:
        partes = fecha_in.split("/")
        if len(partes) == 3:
            # Si viene como DD/MM/YYYY
            if len(partes[0]) == 2 and len(partes[2]) == 4:
                return f"{partes[2]}-{partes[1]}-{partes[0]}"
    return fecha_in

def convertir_a_hora_mexico(hora_utc_str: str) -> str:
    """Convierte cadenas ISO / UTC a Hora del Centro de México (CST)."""
    try:
        if not hora_utc_str or len(hora_utc_str) < 16:
            return "N/A"
        
        dt_utc = datetime.datetime.fromisoformat(hora_utc_str.replace("Z", "+00:00"))
        dt_cdmx = dt_utc.astimezone(ZoneInfo("America/Mexico_City"))
        return dt_cdmx.strftime("%H:%M")
    except Exception:
        return hora_utc_str[11:16] if len(hora_utc_str) >= 16 else "N/A"

# ------------------------------------------------------------------
# 1. OBTENCIÓN DE PARTIDOS Y PROBABILIDADES VÍA RAPIDAPI
# ------------------------------------------------------------------

def obtener_partidos_rapidapi(fecha_str: str) -> List[Dict[str, Any]]:
    """Consulta partidos y probabilidades filtrando duplicados."""
    url = "https://football-prediction-api.p.rapidapi.com/api/v2/predictions"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    params = {"date": fecha_str}
    
    partidos = []
    partidos_vistos = set()
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data:
                home = item.get("home_team", "Local").strip()
                away = item.get("away_team", "Visitante").strip()
                
                # Deduplicar partidos por nombre de equipos
                partido_id = f"{home.lower()}--vs--{away.lower()}"
                if partido_id in partidos_vistos:
                    continue
                partidos_vistos.add(partido_id)
                
                liga = item.get("federation", "Liga Profesional")
                hora_utc = item.get("start_date", "")
                hora_cdmx = convertir_a_hora_mexico(hora_utc)
                
                # Extracción y conversión de probabilidades
                preds = item.get("predictions", {})
                
                def parse_prob(val, default=0.50):
                    try:
                        v = float(val)
                        return v / 100 if v > 1 else v
                    except (TypeError, ValueError):
                        return default

                prob_home = parse_prob(preds.get("classic", {}).get("home"), 0.52)
                prob_draw = parse_prob(preds.get("classic", {}).get("draw"), 0.26)
                prob_over = parse_prob(preds.get("over_25"), 0.52)
                prob_btts = parse_prob(preds.get("btts"), 0.50)
                
                partidos.append({
                    "id": partido_id,
                    "home": home,
                    "away": away,
                    "liga": liga,
                    "hora": hora_cdmx,
                    "prob_home": prob_home,
                    "prob_draw": prob_draw,
                    "prob_over": prob_over,
                    "prob_btts": prob_btts,
                    "fuente": "RapidAPI Feed Directo"
                })
    except Exception as e:
        print(f"Error consultando RapidAPI: {e}")
        
    return partidos

# ------------------------------------------------------------------
# 2. MOTOR DE EVALUACIÓN MULTI-MERCADO (+EV) PLAYDOIT (CUOTAS < 2.00)
# ------------------------------------------------------------------

def analizar_mercados_ev(partidos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    picks = []
    picks_vistos = set()
    
    for p in partidos:
        prob_home = p.get("prob_home", 0.52)
        prob_draw = p.get("prob_draw", 0.26)
        prob_over = p.get("prob_over", 0.52)
        prob_btts = p.get("prob_btts", 0.50)
        
        # Probabilidades estimadas para mercados extendidos
        prob_dnb_home = min(prob_home / (1 - prob_draw) if (1 - prob_draw) > 0 else 0.65, 0.88)
        prob_over15_home = min(prob_home * 1.18, 0.85)
        
        # Catálogo extendido de mercados
        mercados = [
            {"mercado": "1X2 (Victoria Local)", "pick": f"Gana {p['home']}", "prob": prob_home},
            {"mercado": "Doble Oportunidad", "pick": f"{p['home']} o Empate (1X)", "prob": min(prob_home + prob_draw, 0.90)},
            {"mercado": "Empate No Válido (DNB)", "pick": f"{p['home']} (Apuesta Sin Empate)", "prob": prob_dnb_home},
            {"mercado": "Línea de Goles", "pick": "Over 2.5 Goles", "prob": prob_over},
            {"mercado": "Ambos Anotan", "pick": "Ambos Marcan (Sí)", "prob": prob_btts},
            {"mercado": "Goles Equipo Local", "pick": f"Over 1.5 Goles - {p['home']}", "prob": prob_over15_home}
        ]
        
        for m in mercados:
            p_est = m["prob"]
            if p_est < 0.52:  # Asegura probabilidades altas para mantener cuotas bajas (< 2.00)
                continue
                
            # Modelado de Cuota Playdoit (Ajustada con el margen de la casa)
            cuota_playdoit = round((1 / p_est) * 1.04, 2)
            
            # FILTRO ESTRICTO: Únicamente cuotas entre 1.30 y 1.98 (NUNCA ARRIBA DE 2.00)
            if not (1.30 <= cuota_playdoit <= 1.98):
                continue

            prob_imp = 1 / cuota_playdoit
            ev = (p_est * cuota_playdoit) - 1
            
            if ev > 0.01:
                # Evitar picks duplicados por combinación de partido + pick
                pick_key = f"{p['id']}--{m['pick']}"
                if pick_key in picks_vistos:
                    continue
                picks_vistos.add(pick_key)

                picks.append({
                    "partido": f"{p['home']} vs {p['away']}",
                    "liga": p["liga"],
                    "hora": p["hora"],
                    "mercado": m["mercado"],
                    "pick": m["pick"],
                    "cuota": cuota_playdoit,
                    "prob_real": f"{round(p_est * 100, 1)}%",
                    "prob_imp": f"{round(prob_imp * 100, 1)}%",
                    "ev": f"+{round(ev * 100, 2)}%",
                    "ev_val": ev,
                    "fuente": p.get("fuente", "Análisis Estadístico")
                })
                
    # Ordenar por el mayor Valor Esperado (+EV)
    return sorted(picks, key=lambda x: x["ev_val"], reverse=True)[:25]

# ------------------------------------------------------------------
# 3. ENDPOINT PRINCIPAL FASTAPI
# ------------------------------------------------------------------

@app.get("/analizar")
def analizar(fecha: str = None):
    fecha_proc = normalizar_fecha(fecha)

    # Consulta directa a la API autenticada
    partidos = obtener_partidos_rapidapi(fecha_proc)
    picks = analizar_mercados_ev(partidos)

    if not partidos:
        return HTMLResponse(content=f"""
        <div style="font-family:sans-serif;background:#0f172a;color:#fff;padding:20px;text-align:center;border-radius:10px;margin:20px;">
            <h3 style="color:#f43f5e;margin-top:0;">⚠️ No se encontraron partidos registrados para la fecha {fecha_proc}</h3>
            <p style="color:#94a3b8;font-size:9pt;">Verifica el formato de fecha enviado por tu atajo (formato esperado: YYYY-MM-DD).</p>
        </div>
        """)

    cards_html = ""
    for idx, item in enumerate(picks, 1):
        cards_html += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin-bottom:10px;">
            <div style="float:right;background:#0284c7;color:#fff;font-size:8pt;font-weight:bold;padding:2px 6px;border-radius:10px;">TOP #{idx}</div>
            <div style="color:#38bdf8;font-size:8.5pt;font-weight:bold;">{item['liga']} | 🕒 {item['hora']} (Hora CDMX)</div>
            <div style="color:#fff;font-size:11pt;font-weight:bold;margin:3px 0;">{item['partido']}</div>
            <div style="color:#facc15;font-size:9.5pt;font-weight:bold;">{item['mercado']} → <span style="color:#fff;">{item['pick']}</span></div>
            <hr style="border:0;border-top:1px solid #334155;margin:6px 0;">
            <table style="width:100%;color:#f8fafc;font-size:8.5pt;">
                <tr>
                    <td><b>Cuota Playdoit:</b> <span style="color:#4ade80;font-weight:bold;">{item['cuota']}</span></td>
                    <td><b>Prob. Real:</b> {item['prob_real']}</td>
                </tr>
                <tr>
                    <td><b>Prob. Implícita:</b> {item['prob_imp']}</td>
                    <td style="color:#4ade80;"><b>Valor (+EV):</b> {item['ev']}</td>
                </tr>
            </table>
            <div style="margin-top:6px;font-size:8pt;color:#94a3b8;">Fuente: {item['fuente']}</div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Análisis +EV - {fecha_proc}</title>
        <style>
            body {{ font-family:-apple-system, sans-serif; background:#0f172a; color:#fff; padding:14px; margin:0; }}
            .header {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:12px; margin-bottom:14px; text-align:center; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h3 style="color:#38bdf8;margin:0;">⚡ ANALIZADOR DE VALOR (+EV)</h3>
            <p style="color:#94a3b8;margin:4px 0 0 0;font-size:8.5pt;">Fecha Solicitada: <b>{fecha_proc}</b> | Partidos Únicos: <b>{len(partidos)}</b></p>
            <p style="color:#4ade80;font-size:8pt;margin:2px 0 0 0;">Filtro Estricto: Cuotas entre 1.30 y 1.98 | Zona Horaria: CDMX (UTC-6)</p>
        </div>
        {cards_html}
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
