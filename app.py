import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import json
from streamlit_echarts import st_echarts

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(layout="wide", page_title="Sistema Despacho - Perforación")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def init_connection():
    cred_dict = json.loads(st.secrets["GCP_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
    return gspread.authorize(credentials)

client = init_connection()
sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

# --- TUS CATÁLOGOS Y CONSTANTES ---
ESTADOS = ["Perforación", "Stand By", "Demora Operativa", "Demora Mecánica"]
MAPEO_FLOTA = {
    **{f"PERF-{i:02d}": "KY-250" for i in range(1, 9)},
    "PERF-09": "DM-75", "PERF-10": "DM-75",
    "PERF-12": "PRECORTE", "PERF-13": "PRECORTE"
}
LISTA_EQUIPOS = list(MAPEO_FLOTA.keys())
COLORES_ESTADO = {"Perforación": "#2ca02c", "Stand By": "#fdfd33", "Demora Operativa": "#ff7f0e", "Demora Mecánica": "#d62728"}

MOTIVOS_MECANICA = [
    "CABINA", "SISTEMA LEVANTE", "SISTEMA MANDOS", "SISTEMA MOTOR",
    "SISTEMA SUSPENSIÓN", "SISTEMA TRASLACIÓN", "FALTA DE REPUESTO",
    "SISTEMA DE INYECCION DE AGUA", "SISTEMA AIRE ACONDICIONADO",
    "SISTEMA DE REFRIGERACION", "SISTEMA ROTACIÓN", "PM",
    "SISTEMA DE ILUMINACION", "PM-500", "CORRECTIVO", "FUGA DE AGUA",
    "TORRE", "CABEZAL DE ROTACIÓN", "SOLDADURA DE ACEROS",
    "TENSADO DE CADENAS", "CAIDA DE TENSION", "ESPERA DE MTTO MECANICO/ELECTRICO",
    "TRIPEO DE EQUIPO ( UNDER TRIP - OVER TRIP )", "LUBRICACIÓN/ENGRASE",
    "REPARACION ENCENDIDA DE MOTOR", "SISTEMA ARRANQUE", "SISTEMA TRASMISIÓN",
    "SISTEMA DE FRENOS", "SISTEMA DIRECCIÓN", "SISTEMA ELÉCTRICO",
    "SISTEMA HIDRAULICO", "SOPLETEO DE FILTROS(A/C,COMPRESOR,MOTOR)", "OTROS"
]

MOTIVOS_OPERATIVA = [
    "TRASLADO A OTRO PROYECTO", "CAMBIO DE ACEROS Y OTROS", "CAMBIO DE BIT SUB",
    "CAMBIO DE TOP SUB", "ROTACION DE BARRA", "REPERFORACION", "PRUEBA DE PERFORACION",
    "FALTA DE CABLES", "FALTA DE AGUA", "FALTA DE COMBUSTIBLE", "FALTA DE PUNTOS DE PERFORACION",
    "TRASLADO EN EL MISMO PROYECTO", "ABASTECIMIENTO DE AGUA", "ABASTECIMIENTO DE COMBUSTIBLE",
    "CONDICIONES CLIMÁTICAS ADVERSAS", "INCIDENTE OPERATIVO", "TRASLADO POR VOLADURA",
    "MOVIMIENTO DE PUENTES AEREOS", "DESACOPLE DE COLUMNA DE PERFORACION", "CAMBIO DE BARRA",
    "CAMBIO DE BROCA", "CAMBIO DE MARTILLO", "OTROS"
]

# --- LÓGICA DE TIEMPO Y TURNOS ---
ahora = datetime.now()
if 7 <= ahora.hour < 19:
    inicio_turno = ahora.replace(hour=7, minute=0, second=0, microsecond=0)
    nombre_turno = "DÍA"
elif ahora.hour >= 19:
    inicio_turno = ahora.replace(hour=19, minute=0, second=0, microsecond=0)
    nombre_turno = "NOCHE"
else:
    inicio_turno = (ahora - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    nombre_turno = "NOCHE (Cont.)"

# --- FUNCIONES CORE ADAPTADAS A NUBE ---
def registrar(eq, est, det="N/A"):
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not df.empty and not df[df['Equipo'] == eq].empty:
        idx_lista = df[df['Equipo'] == eq].index[-1]
        row_num = int(idx_lista) + 2
        if df.at[idx_lista, 'Fin'] == "" or pd.isna(df.at[idx_lista, 'Fin']):
            sheet.update_cell(row_num, 6, time_now) # Columna 6 es 'Fin'
            
    nueva_fila = [eq, MAPEO_FLOTA[eq], est, det, time_now, ""]
    sheet.append_row(nueva_fila)
    st.toast(f"✅ {eq} actualizado: {est}")

def deshacer_ultimo_registro(eq):
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    idx_eq = df[df['Equipo'] == eq].index
    if len(idx_eq) > 0:
        row_to_delete = int(idx_eq[-1]) + 2
        sheet.delete_rows(row_to_delete)
        if len(idx_eq) > 1:
            new_last_row = int(idx_eq[-2]) + 2
            sheet.update_cell(new_last_row, 6, "")
        st.toast(f"🔄 Corrección: Último estado de {eq} deshecho.")

def calcular_kpis(df_input):
    if df_input.empty: return 100.0, 0.0
    t_tot = df_input['Dur'].sum()
    t_mec = df_input[df_input['Estado'] == 'Demora Mecánica']['Dur'].sum()
    t_per = df_input[df_input['Estado'] == 'Perforación']['
