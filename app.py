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
            sheet.update_cell(row_num, 6, time_now)
            
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

@st.dialog("📋 Registrar Detalle de Demora")
def modal_demora(estado_seleccionado):
    st.write(f"Asignando motivo para el equipo **{st.session_state.equipo_seleccionado}**")
    opciones = MOTIVOS_MECANICA if estado_seleccionado == "Demora Mecánica" else MOTIVOS_OPERATIVA
    motivo_elegido = st.selectbox("Seleccione la causa específica:", opciones)
    if st.button("Guardar Registro", type="primary", use_container_width=True):
        registrar(st.session_state.equipo_seleccionado, estado_seleccionado, motivo_elegido)
        st.rerun()

# --- CARGA DE DATOS PRINCIPAL ---
data_nube = sheet.get_all_records()
df_raw = pd.DataFrame(data_nube) if data_nube else pd.DataFrame(columns=["Equipo", "Flota", "Estado", "Detalle", "Inicio", "Fin"])
if not df_raw.empty:
    df_raw['Inicio'] = pd.to_datetime(df_raw['Inicio'])
    df_raw['Fin'] = pd.to_datetime(df_raw['Fin']).fillna(datetime.now())
    df_raw['Dur'] = (df_raw['Fin'] - df_raw['Inicio']).dt.total_seconds() / 60

if 'equipo_seleccionado' not in st.session_state:
    st.session_state.equipo_seleccionado = LISTA_EQUIPOS[0]

# --- INTERFAZ PESTAÑAS ---
tab1, tab2 = st.tabs(["🟢 TURNO ACTUAL", "📊 DASHBOARD ANALÍTICO"])

# ================= PESTAÑA 1: TURNO ACTUAL =================
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
        if b1.button("🟢 PERFORACIÓN", use_container_width=True): registrar(cur_eq, "Perforación", "N/A")
        if b2.button("🟡 STAND BY", use_container_width=True): registrar(cur_eq, "Stand By", "N/A")
        
        b3, b4 = st.columns(2)
        if b3.button("🟠 DEMORA OP.", use_container_width=True): modal_demora("Demora Operativa")
        if b4.button("🔴 DEMORA MEC.", use_container_width=True): modal_demora("Demora Mecánica")
        
        st.write("") 
        
        if st.button("↩️ CORREGIR ERROR (Deshacer último estado)", use_container_width=True):
            deshacer_ultimo_registro(cur_eq)
            st.rerun()

    with col_gantt:
        st.subheader(f"Línea de Tiempo (Turno {nombre_turno})")
        if not df_turno.empty:
            fig = px.timeline(df_turno, x_start="Inicio", x_end="Fin", y="Equipo", color="Estado", 
                              hover_data=["Detalle"], color_discrete_map=COLORES_ESTADO, category_orders={"Equipo": LISTA_EQUIPOS, "Estado": ESTADOS})
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=450, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)

# ================= PESTAÑA 2: DASHBOARD =================
with tab2:
    st.title("📊 Análisis de Rendimiento Operativo")
    c_fecha, c_vacio = st.columns([1, 3])
    with c_fecha:
        fecha_sel = st.date_input("📅 Día Operativo:", ahora.date())
    
    h_ini_dia = datetime.combine(fecha_sel, datetime.min.time()).replace(hour=7)
    h_fin_dia = h_ini_dia + timedelta(hours=24)
    df_hist = df_raw[(df_raw['Inicio'] >= h_ini_dia) & (df_raw['Inicio'] < h_fin_dia)].copy() if not df_raw.empty else pd.DataFrame()
    
    if df_hist.empty:
        st.warning("No hay datos operativos registrados para la fecha seleccionada.")
    else:
        df_hist['Fin_Seguro'] = pd.to_datetime(df_hist['Fin']).fillna(datetime.now())
        df_hist['Fin_Seguro'] = df_hist['Fin_Seguro'].clip(upper=h_fin_dia)
        df_hist['Dur'] = (df_hist['Fin_Seguro'] - df_hist['Inicio']).dt.total_seconds() / 60

        dh, uh = calcular_kpis(df_hist)
        k1, k2, k3, k4 = st.columns(4)
        with k1: st_echarts(options=crear_gauge_echarts(dh, "Disp. Día"), height="220px")
        with k2: st_echarts(options=crear_gauge_echarts(uh, "Util. Día"), height="220px")
        with k3:
            st.metric("Total Horas Monitoreadas", f"{df_hist['Dur'].sum()/60:.1f} hrs")
            st.metric("Equipos Activos", len(df_hist['Equipo'].unique()))
        
        st.divider()
        
        col_pareto, col_dona = st.columns([1.5, 1.2]) 
        
        with col_pareto:
            st.subheader("📊 PARETO DE DEMORAS")
            df_demoras = df_hist[df_hist['Estado'].isin(['Demora Mecánica', 'Demora Operativa'])]
            df_demoras = df_demoras[df_demoras['Detalle'] != "N/A"]
            
            if not df_demoras.empty:
                df_pareto = df_demoras.groupby('Detalle')['Dur'].sum().reset_index()
                df_pareto = df_pareto.sort_values(by='Dur', ascending=False)
                df_pareto['Acumulado'] = df_pareto['Dur'].cumsum() / df_pareto['Dur'].sum() * 100

                fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
                fig_pareto.add_trace(go.Bar(x=df_pareto['Detalle'], y=df_pareto['Dur'], name="Minutos", marker_color='#4682B4'), secondary_y=False)
                fig_pareto.add_trace(go.Scatter(x=df_pareto['Detalle'], y=df_pareto['Acumulado'], name="% Acumulado", mode='lines+markers', line=dict(color='#d62728')), secondary_y=True)
                fig_pareto.update_layout(margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                st.plotly_chart(fig_pareto, use_container_width=True)

        with col_dona:
            st.subheader("🍩 Radiografía por Flota")
            flotas = ["KY-250", "DM-75", "PRECORTE"]
            fig_pie = make_subplots(rows=1, cols=3, specs=[[{'type':'domain'}, {'type':'domain'}, {'type':'domain'}]], subplot_titles=flotas)
            for i, flota in enumerate(flotas):
                df_flota = df_hist[df_hist['Flota'] == flota]
                if not df_flota.empty:
                    df_grp = df_flota.groupby('Estado')['Dur'].sum().reset_index()
                    fig_pie.add_trace(go.Pie(labels=df_grp['Estado'], values=df_grp['Dur'], hole=0.6, marker_colors=[COLORES_ESTADO[est] for est in df_grp['Estado']]), 1, i+1)
            st.plotly_chart(fig_pie, use_container_width=True)
                
        st.divider()

        st.subheader("🔥 Matriz de Cuellos de Botella")
        horas_ordenadas = [f"{h:02d}:00" for h in range(7, 24)] + [f"{h:02d}:00" for h in range(0, 7)]
        df_heat = df_hist[df_hist['Estado'] != 'Perforación'].copy()
        
        if not df_heat.empty:
            df_heat['Hora_Format'] = df_heat['Inicio'].dt.hour.apply(lambda x: f"{x:02d}:00")
            df_hm = df_heat.groupby(['Equipo', 'Hora_Format'])['Dur'].sum().reset_index()
            pivot_hm = df_hm.pivot(index='Equipo', columns='Hora_Format', values='Dur').reindex(index=LISTA_EQUIPOS, columns=horas_ordenadas).fillna(0)
            fig_heat = go.Figure(data=go.Heatmap(z=pivot_hm.values, x=pivot_hm.columns, y=pivot_hm.index, colorscale='YlOrRd'))
            st.plotly_chart(fig_heat, use_container_width=True)

        st.divider()
        
        st.subheader("📈 Tendencia Histórica")
        df_raw['Fecha_Op'] = (df_raw['Inicio'] - timedelta(hours=7)).dt.date
        ultimos_7 = df_raw.groupby('Fecha_Op').apply(lambda x: pd.Series(calcular_kpis(x), index=['Disp', 'Util'])).reset_index().tail(7)
        if not ultimos_7.empty:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=ultimos_7['Fecha_Op'], y=ultimos_7['Disp'], name='Disponibilidad'))
            fig_trend.add_trace(go.Scatter(x=ultimos_7['Fecha_Op'], y=ultimos_7['Util'], name='Utilización'))
            st.plotly_chart(fig_trend, use_container_width=True)
