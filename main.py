from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
import datetime

app = FastAPI()

def analizar_apuestas(fecha):
    # Simulador de análisis: aquí cruzamos probabilidades vs Playdoit
    partidos = [
        {"partido": "Real Madrid vs Barcelona", "liga": "LaLiga", "mercado": "Gana Real Madrid", "cuota": 2.10, "prob": "52.4%", "ev": "+10.04%", "tags": ["Sofascore: 8/10 Form", "Opta: xG +1.8"]},
        {"partido": "Arsenal vs Chelsea", "liga": "Premier League", "mercado": "Over 2.5 Goles", "cuota": 1.95, "prob": "57.8%", "ev": "+12.71%", "tags": ["BetMines: Trend Over", "Opta: Remates > 12.5"]},
        {"partido": "Bayern vs Dortmund", "liga": "Bundesliga", "mercado": "Ambos Anotan - SÍ", "cuota": 1.80, "prob": "61.0%", "ev": "+9.80%", "tags": ["Sofascore: 90% BTTS", "Opta: Defense Flaws"]},
        {"partido": "Inter vs AC Milan", "liga": "Serie A", "mercado": "Gana Inter Milan", "cuota": 2.05, "prob": "51.2%", "ev": "+4.96%", "tags": ["BetMines: Favorito", "Sofascore: Home Win"]}
    ]
    return partidos

@app.get("/analizar")
def obtener_reporte(fecha: str = None):
    if not fecha:
        fecha = datetime.date.today().strftime("%Y-%m-%d")
        
    partidos = analizar_apuestas(fecha)
    
    cards = ""
    for p in partidos:
        tags_html = "".join([f'<span style="background:#0c4a6e;color:#38bdf8;padding:2px 6px;border-radius:4px;font-size:8pt;margin-right:4px;">{t}</span>' for t in p["tags"]])
        cards += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px;margin-bottom:12px;">
            <div style="color:#38bdf8;font-size:9pt;font-weight:bold;">{p['liga']}</div>
            <div style="color:#fff;font-size:12pt;font-weight:bold;">{p['partido']}</div>
            <hr style="border:0;border-top:1px solid #334155;margin:8px 0;">
            <table style="width:100%;color:#f8fafc;font-size:10pt;">
                <tr>
                    <td><b>Mercado:</b> {p['mercado']}</td>
                    <td><b>Cuota:</b> {p['cuota']}</td>
                </tr>
                <tr>
                    <td><b>Prob. Real:</b> {p['prob']}</td>
                    <td style="color:#4ade80;"><b>EV:</b> {p['ev']}</td>
                </tr>
            </table>
            <div style="margin-top:8px;">{tags_html}</div>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Reporte +EV</title>
        <style>
            body {{ font-family:-apple-system, sans-serif; background:#0f172a; color:#fff; padding:16px; margin:0; }}
            .header {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:16px; margin-bottom:16px; text-align:center; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2 style="color:#38bdf8;margin:0;">⚡ APUESTAS CON VALOR (+EV)</h2>
            <p style="color:#94a3b8;margin:4px 0 0 0;font-size:10pt;">Fecha: {fecha} | Fuentes: Sofascore, Opta, BetMines</p>
        </div>
        {cards}
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
