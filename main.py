from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
import datetime
from typing import List, Dict, Any

app = FastAPI()

# ------------------------------------------------------------------
# CONFIGURACIÓN DE TU API KEY DE RAPIDAPI
# ------------------------------------------------------------------
RAPIDAPI_KEY = "D06ff3a51emshd8c4b86c977e9c2p164dd3jsn5f2fd0a88a17"
RAPIDAPI_HOST = "football-prediction-api.p.rapidapi.com"

# ------------------------------------------------------------------
# 1. OBTENCIÓN DE PARTIDOS Y PROBABILIDADES VÍA RAPIDAPI
# ------------------------------------------------------------------

def obtener_partidos_rapidapi(fecha_str: str) -> List[Dict[str, Any]]:
    """Consulta partidos y probabilidades en tiempo real vía RapidAPI."""
    url = "https://football-prediction-api.p.rapidapi.com/api/v2/predictions"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    params = {"date": fecha_str}
    
    partidos = []
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", [])
            for item in data:
                home = item.get("home_team", "Local")
                away = item.get("away_team", "Visitante")
                liga = item.get("federation", "Liga Profesional")
                hora = item.get("start_date", "")[11:16] if item.get("start_date") else "N/A"
                
                # Extracción de probabilidades del modelo estadístico
                preds = item.get("predictions", {})
                
                # Extraer probabilidad de victoria local
                prob_home = preds.get("classic", {}).get("home", 0.50)
                if isinstance(prob_home, str):
                    prob_home = float(prob_home) / 100 if float(prob_home) > 1 else float(prob_home)
                
                # Extraer probabilidad de Over 2.5
                prob_over = preds.get("over_25", 0.50)
                if isinstance(prob_over, str):
                    prob_over = float(prob_over) / 100 if float(prob_over) > 1 else float(prob_over)

                # Extraer probabilidad de Ambos Anotan (BTTS)
                prob_btts = preds.get("btts", 0.48)
                if isinstance(prob_btts, str):
                    prob_btts = float(prob_btts) / 100 if float(prob_btts) > 1 else float(prob_btts)
                
                partidos.append({
                    "home": home,
                    "away": away,
                    "liga": liga,
                    "hora": hora,
                    "prob_home": prob_home,
                    "prob_over": prob_over,
                    "prob_btts": prob_btts,
                    "fuente": "RapidAPI Feed Directo"
                })
    except Exception as e:
        print(f"Error consultando RapidAPI: {e}")
        
    return partidos

# ------------------------------------------------------------------
# 2. MOTOR DE EVALUACIÓN MULTI-MERCADO (+EV) PLAYDOIT
# ------------------------------------------------------------------

def analizar_mercados_ev(partidos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    picks = []
    
    for p in partidos:
        prob_home = p.get("prob_home", 0.50)
        prob_over = p.get("prob_over", 0.50)
        prob_btts = p.get("prob_btts", 0.48)
        
        # Estructura de evaluación por mercado
        mercados = [
            {"mercado": "1X2 (Victoria Local)", "pick": f"Gana {p['home']}", "prob": prob_home},
            {"mercado": "Doble Oportunidad", "pick": f"{p['home']} o Empate (1X)", "prob": min(prob_home + 0.23, 0.88)},
            {"mercado": "Línea de Goles", "pick": "Over 2.5 Goles", "prob": prob_over},
            {"mercado": "Ambos Anotan", "pick": "Ambos Marcan (Sí)", "prob": prob_btts}
        ]
        
        for m in mercados:
            p_est = m["prob"]
            if p_est < 0.40:
                continue
                
            # Modelado de Cuota Playdoit (Cuota Imponible con margen comercial de la casa)
            cuota_playdoit = round((1 / p_est) * 1.05, 2)
            prob_imp = 1 / cuota_playdoit
            
            # Cálculo del Valor Esperado Positivo (+EV)
            ev = (p_est * cuota_playdoit) - 1
            
            if ev > 0.01 and 1.30 <= cuota_playdoit <= 3.80:
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
    if not fecha:
        fecha = datetime.date.today().strftime("%Y-%m-%d")

    # Consulta directa a la API autenticada
    partidos = obtener_partidos_rapidapi(fecha)
    picks = analizar_mercados_ev(partidos)

    if not partidos:
        return HTMLResponse(content=f"""
        <div style="font-family:sans-serif;background:#0f172a;color:#fff;padding:20px;text-align:center;border-radius:10px;margin:20px;">
            <h3 style="color:#f43f5e;margin-top:0;">⚠️ No se encontraron partidos registrados para la fecha {fecha}</h3>
            <p style="color:#94a3b8;font-size:9pt;">La API no devolvió encuentros para esta fecha en específico o aún no hay datos programados. Intenta probando con otra fecha en el atajo (ej. la fecha de hoy o mañana).</p>
        </div>
        """)

    cards_html = ""
    for idx, item in enumerate(picks, 1):
        cards_html += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:12px;margin-bottom:10px;">
            <div style="float:right;background:#0284c7;color:#fff;font-size:8pt;font-weight:bold;padding:2px 6px;border-radius:10px;">TOP #{idx}</div>
            <div style="color:#38bdf8;font-size:8.5pt;font-weight:bold;">{item['liga']} | 🕒 {item['hora']}</div>
            <div style="color:#fff;font-size:11pt;font-weight:bold;margin:3px 0;">{item['partido']}</div>
            <div style="color:#facc15;font-size:9.5pt;font-weight:bold;">{item['mercado']} → <span style="color:#fff;">{item['pick']}</span></div>
            <hr style="border:0;border-top:1px solid #334155;margin:6px 0;">
            <table style="width:100%;color:#f8fafc;font-size:8.5pt;">
                <tr>
                    <td><b>Cuota Playdoit:</b> {item['cuota']}</td>
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
        <title>Análisis +EV - {fecha}</title>
        <style>
            body {{ font-family:-apple-system, sans-serif; background:#0f172a; color:#fff; padding:14px; margin:0; }}
            .header {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:12px; margin-bottom:14px; text-align:center; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h3 style="color:#38bdf8;margin:0;">⚡ ANALIZADOR DE VALOR (+EV)</h3>
            <p style="color:#94a3b8;margin:4px 0 0 0;font-size:8.5pt;">Fecha: <b>{fecha}</b> | Partidos Analizados: <b>{len(partidos)}</b></p>
            <p style="color:#4ade80;font-size:8pt;margin:2px 0 0 0;">Conexión directa vía RapidAPI activa</p>
        </div>
        {cards_html}
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
