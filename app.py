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

# --- CONFIGURACIÓN DE PÁGINA (TUYA) ---
st.set_page_config(layout="wide", page_title="Sistema Despacho - Perforación")

# --- CONEXIÓN A GOOGLE SHEETS (EL MOTOR) ---
@st.cache_resource
def init_connection():
    cred_dict = json.loads(st.secrets["GCP_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
    return gspread.authorize(credentials)

client = init_connection()
sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

# --- MEMORIA RÁPIDA PARA VELOCIDAD ---
@st.cache_data(ttl=10) # Refresca cada 10 seg.
def leer_datos():
    data = sheet.get_all_records()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    # LIMPIEZA DE LEYENDA: Borra espacios invisibles para evitar duplicados
    df['Estado'] = df['Estado'].astype(str).str.strip()
    return df

# --- TUS CONSTANTES Y CATÁLOGOS (EXACTAMENTE IGUALES) ---
ESTADOS = ["Perforación", "Stand By", "Demora Operativa", "Demora Mecánica"]
MAPEO_FLOTA = {
    **{f"PERF-{i:02d}": "KY-250" for i in range(1, 9)},
    "PERF-09": "DM-75", "PERF-10": "DM-75",
    "PERF-12": "PRECORTE", "PERF-13": "PRECORTE"
}
LISTA_EQUIPOS = list(MAPEO_FLOTA.keys())
COLORES_ESTADO = {"Perforación": "#2ca02c", "Stand By": "#fdfd33", "Demora Operativa": "#ff7f0e", "Demora Mecánica": "#d62728"}

MOTIVOS_MECANICA = ["CABINA", "SISTEMA LEVANTE", "SISTEMA MANDOS", "SISTEMA MOTOR", "SISTEMA SUSPENSIÓN", "SISTEMA TRASLACIÓN", "FALTA DE REPUESTO", "SISTEMA DE INYECCION DE AGUA", "SISTEMA AIRE ACONDICIONADO", "SISTEMA DE REFRIGERACION", "SISTEMA ROTACIÓN", "PM", "SISTEMA DE ILUMINACION", "PM-500", "CORRECTIVO", "FUGA DE AGUA", "TORRE", "CABEZAL DE ROTACIÓN", "SOLDADURA DE ACEROS", "TENSADO DE CADENAS", "CAIDA DE TENSION", "ESPERA DE MTTO MECANICO/ELECTRICO", "TRIPEO DE EQUIPO ( UNDER TRIP - OVER TRIP )", "LUBRICACIÓN/ENGRASE", "REPARACION ENCENDIDA DE MOTOR", "SISTEMA ARRANQUE", "SISTEMA TRASMISIÓN", "SISTEMA DE FRENOS", "SISTEMA DIRECCIÓN", "SISTEMA ELÉCTRICO", "SISTEMA HIDRAULICO", "SOPLETEO DE FILTROS(A/C,COMPRESOR,MOTOR)", "OTROS"]
MOTIVOS_OPERATIVA = ["TRASLADO A OTRO PROYECTO", "CAMBIO DE ACEROS Y OTROS", "CAMBIO DE BIT SUB", "CAMBIO DE TOP SUB", "ROTACION DE BARRA", "REPERFORACION", "PRUEBA DE PERFORACION", "FALTA DE CABLES", "FALTA DE AGUA", "FALTA DE COMBUSTIBLE", "FALTA DE PUNTOS DE PERFORACION", "TRASLADO EN EL MISMO PROYECTO", "ABASTECIMIENTO DE AGUA", "ABASTECIMIENTO DE COMBUSTIBLE", "CONDICIONES CLIMÁTICAS ADVERSAS", "INCIDENTE OPERATIVO", "TRASLADO POR VOLADURA", "MOVIMIENTO DE PUENTES AEREOS", "DESACOPLE DE COLUMNA DE PERFORACION", "CAMBIO DE BARRA", "CAMBIO DE BROCA", "CAMBIO DE MARTILLO", "OTROS"]

# --- LÓGICA DE TIEMPO (TUYA) ---
ahora = datetime.now()
if 7 <= ahora.hour < 19:
    inicio_turno = ahora.replace(hour=7, minute=0, second=0, microsecond=0)
    nombre_turno = "DÍA"
else:
    inicio_turno = ahora.replace(hour=19, minute=0, second=0, microsecond=0) if ahora.hour >= 19 else (ahora - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    nombre_turno = "NOCHE"

# --- TUS FUNCIONES CORE (ADAPTADAS A GOOGLE) ---
def registrar(eq, est, det="N/A"):
    st.cache_data.clear()
    all_data = sheet.get_all_records()
    df = pd.DataFrame(all_data)
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not df.empty and not df[df['Equipo'] == eq].empty:
        idx = df[df['Equipo'] == eq].index[-1]
        row_num = int(idx) + 2
        if df.at[idx, 'Fin'] == "" or pd.isna(df.at[idx, 'Fin']):
            sheet.update_cell(row_num, 6, time_now) # Columna 6 es 'Fin'
            
    sheet.append_row([eq, MAPEO_FLOTA[eq], est, det, time_now, ""])
    st.toast(f"✅ {eq}: {est}")

def deshacer_ultimo_registro(eq):
    st.cache_data.clear()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    idx_eq = df[df['Equipo'] == eq].index
    if len(idx_eq) > 0:
        sheet.delete_rows(int(idx_eq[-1]) + 2)
        if len(idx_eq) > 1:
            sheet.update_cell(int(idx_eq[-2]) + 2, 6, "")
        st.toast(f"🔄 Deshecho: {eq}")

# (Tus funciones de KPI, Gauge y Modal exactas)
def calcular_kpis(df_input):
    if df_input.empty: return 100.0, 0.0
    t_tot = df_input['Dur'].sum()
    t_mec = df_input[df_input['Estado'] == 'Demora Mecánica']['Dur'].sum()
    t_per = df_input[df_input['Estado'] == 'Perforación']['Dur'].sum()
    disp = ((t_tot - t_mec) / t_tot * 100) if t_tot > 0 else 100
    util = (t_per / (t_tot - t_mec) * 100) if (t_tot - t_mec) > 0 else 0
    return disp, util

def crear_gauge_echarts(valor, titulo):
    return {
        "series": [{
            "type": "gauge", "center": ["50%", "65%"], "startAngle": 200, "endAngle": -20,
            "min": 0, "max": 100, "itemStyle": {"color": "#C0C0C0"},
            "pointer": {"length": "65%", "width": 8},
            "axisLine": {"lineStyle": {"width": 15, "color": [[0.75, "#FF4B4B"], [0.85, "#FFA500"], [1, "#2ca02c"]]}},
            "detail": {"formatter": "{value}%", "color": "white", "fontSize": 35},
            "title": {"offsetCenter": [0, "65%"], "color": "white", "fontSize": 16},
            "data": [{"value": round(valor, 1), "name": titulo}]
        }]
    }

@st.dialog("📋 Registrar Detalle")
def modal_demora(estado_sel):
    st.write(f"Motivo para **{st.session_state.equipo_seleccionado}**")
    opciones = MOTIVOS_MECANICA if estado_sel == "Demora Mecánica" else MOTIVOS_OPERATIVA
    motivo = st.selectbox("Seleccione causa:", opciones)
    if st.button("Guardar", type="primary", use_container_width=True):
        registrar(st.session_state.equipo_seleccionado, estado_sel, motivo)
        st.rerun()

# --- CARGA Y PROCESO (TUYO) ---
df_raw = leer_datos()
if not df_raw.empty:
    df_raw['Inicio'] = pd.to_datetime(df_raw['Inicio'])
    df_raw['Fin'] = pd.to_datetime(df_raw['Fin']).fillna(datetime.now())
    df_raw['Dur'] = (df_raw['Fin'] - df_raw['Inicio']).dt.total_seconds() / 60

if 'equipo_seleccionado' not in st.session_state:
    st.session_state.equipo_seleccionado = LISTA_EQUIPOS[0]

# --- TUS PESTAÑAS (DISEÑO ORIGINAL AL 100%) ---
tab1, tab2 = st.tabs(["🟢 TURNO ACTUAL", "📊 DASHBOARD ANALÍTICO"])

with tab1:
    st.title(f"🚜 Despacho Perforación - Turno {nombre_turno}")
    filtro = st.radio("Ver KPIs de:", ["GENERAL", "KY-250", "DM-75", "PRECORTE", "EQUIPO SELECC."], horizontal=True)
    df_turno = df_raw[df_raw['Inicio'] >= inicio_turno] if not df_raw.empty else pd.DataFrame()
    cur_eq = st.session_state.equipo_seleccionado
    
    if filtro == "GENERAL": df_kpi, tit = df_turno, "GENERAL"
    elif filtro == "EQUIPO SELECC.": df_kpi, tit = df_turno[df_turno['Equipo'] == cur_eq] if not df_turno.empty else pd.DataFrame(), cur_eq
    else: df_kpi, tit = df_turno[df_turno['Flota'] == filtro] if not df_turno.empty else pd.DataFrame(), filtro
        
    d, u = calcular_kpis(df_kpi)
    c1, c2 = st.columns(2)
    with c1: st_echarts(options=crear_gauge_echarts(d, f"Disp. {tit}"), height="280px")
    with c2: st_echarts(options=crear_gauge_echarts(u, f"Util. {tit}"), height="280px")
    
    st.divider()
    col_reg, col_gantt = st.columns([1.3, 2])
    with col_reg:
        st.subheader("1. Seleccionar Equipo")
        cols_eq = st.columns(4)
        for i, eq in enumerate(LISTA_EQUIPOS):
            with cols_eq[i % 4]:
                if st.button(eq, key=f"t1_{eq}", use_container_width=True, type="primary" if cur_eq == eq else "secondary"):
                    st.session_state.equipo_seleccionado = eq
                    st.rerun()
        
        st.info(f"📍 Activo: **{cur_eq}**")
        st.subheader("2. Estado")
        b1, b2 = st.columns(2)
        if b1.button("🟢 PERFORACIÓN", use_container_width=True): registrar(cur_eq, "Perforación")
        if b2.button("🟡 STAND BY", use_container_width=True): registrar(cur_eq, "Stand By")
        b3, b4 = st.columns(2)
        if b3.button("🟠 DEMORA OP.", use_container_width=True): modal_demora("Demora Operativa")
        if b4.button("🔴 DEMORA MEC.", use_container_width=True): modal_demora("Demora Mecánica")
        if st.button("↩️ CORREGIR ERROR", use_container_width=True):
            deshacer_ultimo_registro(cur_eq)
            st.rerun()

    with col_gantt:
        if not df_turno.empty:
            fig = px.timeline(df_turno, x_start="Inicio", x_end="Fin", y="Equipo", color="Estado", color_discrete_map=COLORES_ESTADO, category_orders={"Equipo": LISTA_EQUIPOS, "Estado": ESTADOS})
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.title("📊 Análisis de Rendimiento Operativo")
    # (Aquí pegas todo el código de tu Pestaña 2: Pareto, Dona, Heatmap y Tendencia)
    # Lo he dejado preparado para que uses el df_raw que ya limpiamos arriba.
    fecha_sel = st.date_input("📅 Día Operativo:", ahora.date())
    h_ini_dia = datetime.combine(fecha_sel, datetime.min.time()).replace(hour=7)
    df_hist = df_raw[(df_raw['Inicio'] >= h_ini_dia)].copy() if not df_raw.empty else pd.DataFrame()
    
    if not df_hist.empty:
        # Tus gráficos de Pareto, Heatmap, etc. van aquí tal cual los tenías.
        st.write("Datos históricos listos para análisis.")
        st.dataframe(df_hist.tail(10))
