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

st.set_page_config(layout="wide", page_title="Sistema Despacho - Perforación")

# --- CONEXIÓN OPTIMIZADA ---
@st.cache_resource
def init_connection():
    cred_dict = json.loads(st.secrets["GCP_JSON"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
    return gspread.authorize(credentials)

client = init_connection()
sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

# --- MEMORIA RÁPIDA (CACHÉ) PARA VELOCIDAD ---
@st.cache_data(ttl=60) # Actualiza cada 60 segundos automáticamente
def leer_datos_nube():
    data = sheet.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame(columns=["Equipo", "Flota", "Estado", "Detalle", "Inicio", "Fin"])

# --- CONSTANTES ---
ESTADOS = ["Perforación", "Stand By", "Demora Operativa", "Demora Mecánica"]
MAPEO_FLOTA = {
    **{f"PERF-{i:02d}": "KY-250" for i in range(1, 9)},
    "PERF-09": "DM-75", "PERF-10": "DM-75",
    "PERF-12": "PRECORTE", "PERF-13": "PRECORTE"
}
LISTA_EQUIPOS = list(MAPEO_FLOTA.keys())
COLORES_ESTADO = {"Perforación": "#2ca02c", "Stand By": "#fdfd33", "Demora Operativa": "#ff7f0e", "Demora Mecánica": "#d62728"}

# (Mantén tus listas de MOTIVOS_MECANICA y MOTIVOS_OPERATIVA aquí igual que antes)
MOTIVOS_MECANICA = ["CABINA", "SISTEMA LEVANTE", "SISTEMA MANDOS", "SISTEMA MOTOR", "SISTEMA SUSPENSIÓN", "SISTEMA TRASLACIÓN", "FALTA DE REPUESTO", "SISTEMA DE INYECCION DE AGUA", "SISTEMA AIRE ACONDICIONADO", "SISTEMA DE REFRIGERACION", "SISTEMA ROTACIÓN", "PM", "SISTEMA DE ILUMINACION", "PM-500", "CORRECTIVO", "FUGA DE AGUA", "TORRE", "CABEZAL DE ROTACIÓN", "SOLDADURA DE ACEROS", "TENSADO DE CADENAS", "CAIDA DE TENSION", "ESPERA DE MTTO MECANICO/ELECTRICO", "TRIPEO DE EQUIPO ( UNDER TRIP - OVER TRIP )", "LUBRICACIÓN/ENGRASE", "REPARACION ENCENDIDA DE MOTOR", "SISTEMA ARRANQUE", "SISTEMA TRASMISIÓN", "SISTEMA DE FRENOS", "SISTEMA DIRECCIÓN", "SISTEMA ELÉCTRICO", "SISTEMA HIDRAULICO", "SOPLETEO DE FILTROS(A/C,COMPRESOR,MOTOR)", "OTROS"]
MOTIVOS_OPERATIVA = ["TRASLADO A OTRO PROYECTO", "CAMBIO DE ACEROS Y OTROS", "CAMBIO DE BIT SUB", "CAMBIO DE TOP SUB", "ROTACION DE BARRA", "REPERFORACION", "PRUEBA DE PERFORACION", "FALTA DE CABLES", "FALTA DE AGUA", "FALTA DE COMBUSTIBLE", "FALTA DE PUNTOS DE PERFORACION", "TRASLADO EN EL MISMO PROYECTO", "ABASTECIMIENTO DE AGUA", "ABASTECIMIENTO DE COMBUSTIBLE", "CONDICIONES CLIMÁTICAS ADVERSAS", "INCIDENTE OPERATIVO", "TRASLADO POR VOLADURA", "MOVIMIENTO DE PUENTES AEREOS", "DESACOPLE DE COLUMNA DE PERFORACION", "CAMBIO DE BARRA", "CAMBIO DE BROCA", "CAMBIO DE MARTILLO", "OTROS"]

# --- LÓGICA DE TIEMPO ---
ahora = datetime.now()
if 7 <= ahora.hour < 19:
    inicio_turno = ahora.replace(hour=7, minute=0, second=0, microsecond=0)
    nombre_turno = "DÍA"
else:
    inicio_turno = ahora.replace(hour=19, minute=0, second=0, microsecond=0) if ahora.hour >= 19 else (ahora - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    nombre_turno = "NOCHE"

# --- REGISTRO DIRECTO (SIN CACHÉ PARA QUE SEA INSTANTÁNEO) ---
def registrar(eq, est, det="N/A"):
    # Limpiamos caché para que el cambio se vea de inmediato
    st.cache_data.clear()
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not df.empty and not df[df['Equipo'] == eq].empty:
        idx_lista = df[df['Equipo'] == eq].index[-1]
        row_num = int(idx_lista) + 2
        if df.at[idx_lista, 'Fin'] == "" or pd.isna(df.at[idx_lista, 'Fin']):
            sheet.update_cell(row_num, 6, time_now)
            
    nueva_fila = [eq, MAPEO_FLOTA[eq], est, det, time_now, ""]
    sheet.append_row(nueva_fila)
    st.toast(f"✅ {eq}: {est}")

# (Mantén tus funciones calcular_kpis y crear_gauge_echarts igual)
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
            "min": 0, "max": 100, "itemStyle": {"color": "#C0C0C0"}, "progress": {"show": False},
            "pointer": {"icon": "path://M12.8,0.7l12,40.1H0.7L12.8,0.7z", "length": "65%", "width": 8, "offsetCenter": [0, "-5%"], "itemStyle": {"color": "auto"}},
            "axisLine": {"lineStyle": {"width": 15, "color": [[0.75, "#FF4B4B"], [0.85, "#FFA500"], [1, "#2ca02c"]]}},
            "axisTick": {"show": False}, "splitLine": {"show": False}, "axisLabel": {"show": False},
            "detail": {"valueAnimation": True, "formatter": "{value}%", "color": "white", "fontSize": 35, "offsetCenter": [0, "30%"]},
            "title": {"offsetCenter": [0, "65%"], "color": "white", "fontSize": 16},
            "data": [{"value": round(valor, 1), "name": titulo}]
        }]
    }

@st.dialog("📋 Registrar Detalle")
def modal_demora(estado_sel):
    st.write(f"Equipo: **{st.session_state.equipo_seleccionado}**")
    opciones = MOTIVOS_MECANICA if estado_sel == "Demora Mecánica" else MOTIVOS_OPERATIVA
    motivo = st.selectbox("Causa:", opciones)
    if st.button("Guardar", type="primary", use_container_width=True):
        registrar(st.session_state.equipo_seleccionado, estado_sel, motivo)
        st.rerun()

# --- CARGA DE DATOS ---
df_raw = leer_datos_nube()
if not df_raw.empty:
    df_raw['Inicio'] = pd.to_datetime(df_raw['Inicio'])
    df_raw['Fin'] = pd.to_datetime(df_raw['Fin']).fillna(datetime.now())
    df_raw['Dur'] = (df_raw['Fin'] - df_raw['Inicio']).dt.total_seconds() / 60

if 'equipo_seleccionado' not in st.session_state:
    st.session_state.equipo_seleccionado = LISTA_EQUIPOS[0]

tab1, tab2 = st.tabs(["🟢 TURNO ACTUAL", "📊 DASHBOARD ANALÍTICO"])

with tab1:
    st.title(f"🚜 Despacho Perforación - {nombre_turno}")
    df_turno = df_raw[df_raw['Inicio'] >= inicio_turno] if not df_raw.empty else pd.DataFrame()
    
    cur_eq = st.session_state.equipo_seleccionado
    d, u = calcular_kpis(df_turno)
    
    c1, c2 = st.columns(2)
    with c1: st_echarts(options=crear_gauge_echarts(d, "Disp. Turno"), height="260px")
    with c2: st_echarts(options=crear_gauge_echarts(u, "Util. Turno"), height="260px")

    col_reg, col_gantt = st.columns([1.3, 2])
    with col_reg:
        st.subheader("Seleccionar Equipo")
        cols_eq = st.columns(4)
        for i, eq in enumerate(LISTA_EQUIPOS):
            with cols_eq[i % 4]:
                if st.button(eq, key=f"t1_{eq}", use_container_width=True, type="primary" if cur_eq == eq else "secondary"):
                    st.session_state.equipo_seleccionado = eq
                    st.rerun()
        
        st.info(f"📍 Activo: **{cur_eq}**")
        b1, b2 = st.columns(2)
        if b1.button("🟢 PERFORACIÓN", use_container_width=True): registrar(cur_eq, "Perforación")
        if b2.button("🟡 STAND BY", use_container_width=True): registrar(cur_eq, "Stand By")
        b3, b4 = st.columns(2)
        if b3.button("🟠 DEMORA OP.", use_container_width=True): modal_demora("Demora Operativa")
        if b4.button("🔴 DEMORA MEC.", use_container_width=True): modal_demora("Demora Mecánica")

    with col_gantt:
        st.subheader("Línea de Tiempo")
        if not df_turno.empty:
            # RESET DE LEYENDA: Forzamos el orden y eliminamos duplicados
            fig = px.timeline(df_turno, x_start="Inicio", x_end="Fin", y="Equipo", color="Estado", 
                              color_discrete_map=COLORES_ESTADO, 
                              category_orders={"Equipo": LISTA_EQUIPOS, "Estado": ESTADOS}) # <-- Esto arregla la leyenda
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.title("📊 Análisis Operativo")
    # (Mantén aquí tus gráficos de Pareto y Heatmap, solo asegúrate de usar df_raw)
