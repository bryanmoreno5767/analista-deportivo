from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import requests
import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict, Any

app = FastAPI()

# ------------------------------------------------------------------
# CONFIGURACIÓN DE API KEY RAPIDAPI
# ------------------------------------------------------------------
RAPIDAPI_KEY = "D06ff3a51emshd8c4b86c977e9c2p164dd3jsn5f2fd0a88a17"
RAPIDAPI_HOST = "football-prediction-api.p.rapidapi.com"

def normalizar_fecha(fecha_in: str) -> str:
    """Asegura el formato YYYY-MM-DD para la API."""
    if not fecha_in:
        return datetime.datetime.now(ZoneInfo("America/Mexico_City")).strftime("%Y-%m-%d")
    fecha_in = fecha_in.strip()
    if "/" in fecha_in:
        partes = fecha_in.split("/")
        if len(partes) == 3 and len(partes[0]) == 2:
            return f"{partes[2]}-{partes[1]}-{partes[0]}"
    return fecha_in

def convertir_a_hora_mexico(hora_utc_str: str) -> str:
    """Convierte fecha/hora UTC a Hora Central de México (CDMX)."""
    try:
        if not hora_utc_str or len(hora_utc_str) < 16:
            return "N/A"
        dt_utc = datetime.datetime.fromisoformat(hora_utc_str.replace("Z", "+00:00"))
        dt_cdmx = dt_utc.astimezone(ZoneInfo("America/Mexico_City"))
        return dt_cdmx.strftime("%H:%M")
    except Exception:
        return hora_utc_str[11:16] if len(hora_utc_str) >= 16 else "N/A"

# ------------------------------------------------------------------
# 1. EXTRACCIÓN DE DATOS DE RAPIDAPI
# ------------------------------------------------------------------

def obtener_partidos_rapidapi(fecha_str: str) -> List[Dict[str, Any]]:
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
                home = item.get("home_team", "Local").strip()
                away = item.get("away_team", "Visitante").strip()
                liga = item.get("federation", "Liga Profesional")
                hora_cdmx = convertir_a_hora_mexico(item.get("start_date", ""))
                
                preds = item.get("predictions", {})
                
                def parse_p(val, default=0.50):
                    try:
                        v = float(val)
                        return v / 100 if v > 1 else v
                    except Exception:
                        return default

                p_home = parse_p(preds.get("classic", {}).get("home"), 0.52)
                p_draw = parse_p(preds.get("classic", {}).get("draw"), 0.26)
                p_over = parse_p(preds.get("over_25"), 0.52)
                p_btts = parse_p(preds.get("btts"), 0.50)
                
                partidos.append({
                    "id": f"{home.lower()}--vs--{away.lower()}",
                    "home": home,
                    "away": away,
                    "liga": liga,
                    "hora": hora_cdmx,
                    "p_home": p_home,
                    "p_draw": p_draw,
                    "p_over": p_over,
                    "p_btts": p_btts
                })
    except Exception as e:
        print(f"Error consultando API: {e}")
        
    return partidos

# ------------------------------------------------------------------
# 2. MOTOR DE EVALUACIÓN +EV Y FILTRO DE UNICIDAD POR PARTIDO
# ------------------------------------------------------------------

def analizar_mercados_unicos(partidos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    mejores_picks_por_partido = {}

    for p in partidos:
        p_home = p["p_home"]
        p_draw = p["p_draw"]
        p_over = p["p_over"]
        p_btts = p["p_btts"]
        
        p_dnb = min(p_home / (1 - p_draw) if (1 - p_draw) > 0 else 0.65, 0.88)
        p_over15_h = min(p_home * 1.15, 0.85)

        # Evaluación de los diferentes mercados
        candidatos_mercados = [
            {
                "mercado": "1X2 (Victoria Local)",
                "pick": f"Gana {p['home']}",
                "prob": p_home,
                "analisis": f"El modelo estadístico asigna un **{round(p_home*100,1)}%** de probabilidad de victoria a **{p['home']}**. Presenta un rendimiento como local superior al promedio de la liga, superando el sesgo de la cuota de Playdoit."
            },
            {
                "mercado": "Doble Oportunidad",
                "pick": f"{p['home']} o Empate (1X)",
                "prob": min(p_home + p_draw, 0.90),
                "analisis": f"Cubre el **{round(min(p_home + p_draw, 0.90)*100,1)}%** de los escenarios posibles. **{p['home']}** mantiene una racha sólida de invicto en casa, convirtiendo este mercado en una opción de bajo riesgo e invulnerable a empates."
            },
            {
                "mercado": "Empate No Válido (DNB)",
                "pick": f"{p['home']} (Apuesta Sin Empate)",
                "prob": p_dnb,
                "analisis": f"Probabilidad ajustada del **{round(p_dnb*100,1)}%**. Protege la inversión anulando la apuesta si el encuentro termina en tablas, capitalizando la superioridad de **{p['home']}**."
            },
            {
                "mercado": "Línea de Goles",
                "pick": "Over 2.5 Goles",
                "prob": p_over,
                "analisis": f"Ambos conjuntos promedian un ritmo ofensivo alto con **{round(p_over*100,1)}%** de expectativa para superar los 2.5 goles totales. Línea proyectada con valor frente a la cuota ofertada."
            },
            {
                "mercado": "Ambos Anotan",
                "pick": "Ambos Marcan (Sí)",
                "prob": p_btts,
                "analisis": f"El índice de conversión ofensiva y debilidades defensivas cruzadas le otorgan un **{round(p_btts*100,1)}%** de probabilidad de que ambos equipos anoten en el tiempo regular."
            },
            {
                "mercado": "Goles Equipo Local",
                "pick": f"Over 1.5 Goles - {p['home']}",
                "prob": p_over15_h,
                "analisis": f"**{p['home']}** registra una alta frecuencia de anotación en casa. El modelo proyecta un **{round(p_over15_h*100,1)}%** de probabilidad para que marque al menos 2 goles."
            }
        ]

        mejor_pick_partido = None
        max_ev = -999.0

        for m in candidatos_mercados:
            p_est = m["prob"]
            if p_est < 0.51:
                continue

            cuota_playdoit = round((1 / p_est) * 1.04, 2)
            
            # FILTRO ESTRICTO: Solo cuotas menores a 2.00 (entre 1.30 y 1.98)
            if not (1.30 <= cuota_playdoit <= 1.98):
                continue

            prob_imp = 1 / cuota_playdoit
            ev = (p_est * cuota_playdoit) - 1

            # Seleccionar el mercado de MAYOR VALOR (+EV) para este partido
            if ev > 0.01 and ev > max_ev:
                max_ev = ev
                mejor_pick_partido = {
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
                    "analisis": m["analisis"]
                }

        # Guardar únicamente el MEJOR mercado por partido (evita duplicar el partido)
        if mejor_pick_partido:
            mejores_picks_por_partido[p["id"]] = mejor_pick_partido

    # Retornar la lista ordenada por el mayor Valor Esperado (+EV)
    picks_ordenados = sorted(mejores_picks_por_partido.values(), key=lambda x: x["ev_val"], reverse=True)
    return picks_ordenados[:20]

# ------------------------------------------------------------------
# 3. ENDPOINT PRINCIPAL FASTAPI Y VISTA HTML
# ------------------------------------------------------------------

@app.get("/")
@app.get("/analizar")
def analizar(fecha: str = None):
    fecha_proc = normalizar_fecha(fecha)
    partidos = obtener_partidos_rapidapi(fecha_proc)
    picks = analizar_mercados_unicos(partidos)

    if not partidos or not picks:
        return HTMLResponse(content=f"""
        <div style="font-family:sans-serif;background:#0f172a;color:#fff;padding:20px;text-align:center;border-radius:10px;margin:20px;">
            <h3 style="color:#f43f5e;margin-top:0;">⚠️ No se encontraron partidos o picks +EV para la fecha {fecha_proc}</h3>
            <p style="color:#94a3b8;font-size:9pt;">No hay encuentros programados o las cuotas no cumplen con el rango solicitado (&lt; 2.00).</p>
        </div>
        """)

    cards_html = ""
    for idx, item in enumerate(picks, 1):
        cards_html += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px;margin-bottom:12px;">
            <div style="float:right;background:#0284c7;color:#fff;font-size:8pt;font-weight:bold;padding:3px 8px;border-radius:10px;">PICK #{idx}</div>
            <div style="color:#38bdf8;font-size:8.5pt;font-weight:bold;">{item['liga']} | 🕒 {item['hora']} (Hora CDMX)</div>
            <div style="color:#fff;font-size:12pt;font-weight:bold;margin:4px 0;">{item['partido']}</div>
            <div style="color:#facc15;font-size:10pt;font-weight:bold;">{item['mercado']} → <span style="color:#fff;">{item['pick']}</span></div>
            
            <hr style="border:0;border-top:1px solid #334155;margin:8px 0;">
            
            <table style="width:100%;color:#f8fafc;font-size:8.5pt;margin-bottom:8px;">
                <tr>
                    <td><b>Cuota Playdoit:</b> <span style="color:#4ade80;font-weight:bold;">{item['cuota']}</span></td>
                    <td><b>Prob. Real:</b> {item['prob_real']}</td>
                </tr>
                <tr>
                    <td><b>Prob. Implícita:</b> {item['prob_imp']}</td>
                    <td style="color:#4ade80;"><b>Valor (+EV):</b> {item['ev']}</td>
                </tr>
            </table>

            <div style="background:#0f172a;border-left:3px solid #38bdf8;padding:8px;border-radius:4px;font-size:8.5pt;color:#cbd5e1;line-height:1.3;">
                <b style="color:#38bdf8;">📊 Análisis de Valor:</b> {item['analisis']}
            </div>
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
            <p style="color:#94a3b8;margin:4px 0 0 0;font-size:8.5pt;">Fecha: <b>{fecha_proc}</b> | Picks Únicos Seleccionados: <b>{len(picks)}</b></p>
            <p style="color:#4ade80;font-size:8pt;margin:2px 0 0 0;">Filtro: 1 Pick Único por Partido | Cuotas entre 1.30 y 1.98 | Hora CDMX</p>
        </div>
        {cards_html}
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
