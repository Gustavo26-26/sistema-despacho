import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import os
from streamlit_echarts import st_echarts

st.set_page_config(layout="wide", page_title="Sistema Despacho - Perforación")

DB_FILE = "datos_perforadoras.csv"
ESTADOS = ["Perforación", "Stand By", "Demora Operativa", "Demora Mecánica"]
MAPEO_FLOTA = {
    **{f"PERF-{i:02d}": "KY-250" for i in range(1, 9)},
    "PERF-09": "DM-75", "PERF-10": "DM-75",
    "PERF-12": "PRECORTE", "PERF-13": "PRECORTE"
}
LISTA_EQUIPOS = list(MAPEO_FLOTA.keys())
COLORES_ESTADO = {"Perforación": "#2ca02c", "Stand By": "#fdfd33", "Demora Operativa": "#ff7f0e", "Demora Mecánica": "#d62728"}

# --- CATÁLOGOS DE DEMORAS ---
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

# --- INICIALIZACIÓN ---
if not os.path.exists(DB_FILE):
    pd.DataFrame(columns=["Equipo", "Flota", "Estado", "Detalle", "Inicio", "Fin"]).to_csv(DB_FILE, index=False)
else:
    df_temp = pd.read_csv(DB_FILE)
    if 'Detalle' not in df_temp.columns:
        df_temp['Detalle'] = "N/A"
        df_temp.to_csv(DB_FILE, index=False)

if 'equipo_seleccionado' not in st.session_state:
    st.session_state.equipo_seleccionado = LISTA_EQUIPOS[0]

def verificar_y_aplicar_cambio_turno():
    df_check = pd.read_csv(DB_FILE)
    if df_check.empty: return
    hubo_cambios = False
    nuevos_registros = []
    
    for eq in LISTA_EQUIPOS:
        df_eq = df_check[df_check['Equipo'] == eq]
        if not df_eq.empty:
            idx_ultimo = df_eq.index[-1]
            ultimo_inicio = pd.to_datetime(df_check.at[idx_ultimo, 'Inicio'])
            if ultimo_inicio < inicio_turno:
                if pd.isna(df_check.at[idx_ultimo, 'Fin']):
                    df_check.at[idx_ultimo, 'Fin'] = inicio_turno.strftime("%Y-%m-%d %H:%M:%S")
                
                ultimo_estado = df_check.at[idx_ultimo, 'Estado']
                nuevo_estado = "Demora Mecánica" if ultimo_estado == "Demora Mecánica" else "Stand By"
                nuevo_detalle = df_check.at[idx_ultimo, 'Detalle'] if nuevo_estado == "Demora Mecánica" else "N/A"
                
                nuevos_registros.append({
                    "Equipo": eq, "Flota": MAPEO_FLOTA[eq], "Estado": nuevo_estado, "Detalle": nuevo_detalle,
                    "Inicio": inicio_turno.strftime("%Y-%m-%d %H:%M:%S"), "Fin": None
                })
                hubo_cambios = True

    if hubo_cambios and nuevos_registros:
        pd.concat([df_check, pd.DataFrame(nuevos_registros)], ignore_index=True).to_csv(DB_FILE, index=False)

verificar_y_aplicar_cambio_turno()

# --- FUNCIONES CORE ---
def registrar(eq, est, det="N/A"):
    df = pd.read_csv(DB_FILE)
    time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not df[df['Equipo'] == eq].empty:
        idx = df[df['Equipo'] == eq].index[-1]
        if pd.isna(df.at[idx, 'Fin']): df.at[idx, 'Fin'] = time_now
    nuevo = pd.DataFrame([{"Equipo": eq, "Flota": MAPEO_FLOTA[eq], "Estado": est, "Detalle": det, "Inicio": time_now, "Fin": None}])
    pd.concat([df, nuevo], ignore_index=True).to_csv(DB_FILE, index=False)
    st.toast(f"✅ {eq} actualizado: {est} ({det})")

# --- NUEVA FUNCIÓN: DESHACER ÚLTIMO REGISTRO ---
def deshacer_ultimo_registro(eq):
    df = pd.read_csv(DB_FILE)
    idx_eq = df[df['Equipo'] == eq].index
    if len(idx_eq) > 1:
        # Borramos la última fila de ese equipo
        df = df.drop(idx_eq[-1])
        # Al nuevo "último" registro, le quitamos la hora de Fin para que vuelva a estar en curso
        nuevo_ultimo_idx = df[df['Equipo'] == eq].index[-1]
        df.at[nuevo_ultimo_idx, 'Fin'] = None
        df.to_csv(DB_FILE, index=False)
        st.toast(f"🔄 Corrección: Último estado de {eq} deshecho.")
    elif len(idx_eq) == 1:
        st.warning(f"No puedes borrar el registro inicial de {eq}.")
    else:
        st.warning(f"No hay registros para {eq}.")

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
    if estado_seleccionado == "Demora Mecánica": opciones = MOTIVOS_MECANICA
    else: opciones = MOTIVOS_OPERATIVA
    motivo_elegido = st.selectbox("Seleccione la causa específica:", opciones)
    if st.button("Guardar Registro", type="primary", use_container_width=True):
        registrar(st.session_state.equipo_seleccionado, estado_seleccionado, motivo_elegido)
        st.rerun()

# --- CARGA DE DATOS PRINCIPAL ---
df_raw = pd.read_csv(DB_FILE)
df_raw['Inicio'] = pd.to_datetime(df_raw['Inicio'])
df_raw['Fin'] = pd.to_datetime(df_raw['Fin']).fillna(datetime.now())
df_raw['Dur'] = (df_raw['Fin'] - df_raw['Inicio']).dt.total_seconds() / 60

# --- INTERFAZ PESTAÑAS ---
tab1, tab2 = st.tabs(["🟢 TURNO ACTUAL", "📊 DASHBOARD ANALÍTICO"])

# ================= PESTAÑA 1: TURNO ACTUAL =================
with tab1:
    st.title(f"🚜 Despacho Perforación - Turno {nombre_turno}")
    filtro = st.radio("Ver KPIs de:", ["GENERAL", "KY-250", "DM-75", "PRECORTE", "EQUIPO SELECC."], horizontal=True)
    
    df_turno = df_raw[df_raw['Inicio'] >= inicio_turno]
    cur_eq = st.session_state.equipo_seleccionado
    
    if filtro == "GENERAL": df_kpi, tit = df_turno, "GENERAL"
    elif filtro == "EQUIPO SELECC.": df_kpi, tit = df_turno[df_turno['Equipo'] == cur_eq], cur_eq
    else: df_kpi, tit = df_turno[df_turno['Flota'] == filtro], filtro
        
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
        
        # Botones de Estados
        b1, b2 = st.columns(2)
        if b1.button("🟢 PERFORACIÓN", use_container_width=True): registrar(cur_eq, "Perforación", "N/A")
        if b2.button("🟡 STAND BY", use_container_width=True): registrar(cur_eq, "Stand By", "N/A")
        
        b3, b4 = st.columns(2)
        if b3.button("🟠 DEMORA OP.", use_container_width=True): modal_demora("Demora Operativa")
        if b4.button("🔴 DEMORA MEC.", use_container_width=True): modal_demora("Demora Mecánica")
        
        st.write("") # Espaciador
        
        # --- EL BOTÓN DE CORRECCIÓN ---
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
    df_hist = df_raw[(df_raw['Inicio'] >= h_ini_dia) & (df_raw['Inicio'] < h_fin_dia)].copy()
    
    if df_hist.empty:
        st.warning("No hay datos operativos registrados para la fecha seleccionada.")
    else:
        df_hist['Fin_Seguro'] = pd.to_datetime(df_hist['Fin']).fillna(datetime.now())
        df_hist['Fin_Seguro'] = df_hist['Fin_Seguro'].clip(upper=h_fin_dia)
        df_hist['Dur'] = (df_hist['Fin_Seguro'] - df_hist['Inicio']).dt.total_seconds() / 60

        # --- FILA 1: KPIs DIARIOS ---
        dh, uh = calcular_kpis(df_hist)
        k1, k2, k3, k4 = st.columns(4)
        with k1: st_echarts(options=crear_gauge_echarts(dh, "Disp. Día"), height="220px")
        with k2: st_echarts(options=crear_gauge_echarts(uh, "Util. Día"), height="220px")
        with k3:
            st.metric("Total Horas Monitoreadas", f"{df_hist['Dur'].sum()/60:.1f} hrs")
            st.metric("Equipos Activos", len(df_hist['Equipo'].unique()))
        
        st.divider()
        
        # --- FILA 2: PARETO Y RADIOGRAFÍA ---
        col_pareto, col_dona = st.columns([1.5, 1.2]) 
        
        with col_pareto:
            st.subheader("📊 PARETO DE DEMORAS (Por Causa Exacta)")
            df_demoras = df_hist[df_hist['Estado'].isin(['Demora Mecánica', 'Demora Operativa'])]
            df_demoras = df_demoras[df_demoras['Detalle'] != "N/A"]
            
            if not df_demoras.empty:
                df_pareto = df_demoras.groupby('Detalle')['Dur'].sum().reset_index()
                df_pareto = df_pareto.sort_values(by='Dur', ascending=False)
                df_pareto['Acumulado'] = df_pareto['Dur'].cumsum() / df_pareto['Dur'].sum() * 100

                colores_sobrios = ['#4682B4', '#708090', '#6B8E23', '#CD853F', '#5F9EA0', '#D2B48C', '#8FBC8F', '#B0C4DE', '#F4A460', '#95A5A6', '#7F8C8D', '#BDC3C7']
                fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
                fig_pareto.add_trace(go.Bar(x=df_pareto['Detalle'], y=df_pareto['Dur'], name="Minutos Perdidos", marker_color=colores_sobrios[:len(df_pareto)]), secondary_y=False)
                fig_pareto.add_trace(go.Scatter(x=df_pareto['Detalle'], y=df_pareto['Acumulado'], name="% Acumulado", mode='lines+markers', line=dict(color='#d62728', width=3), marker=dict(symbol='diamond', size=8)), secondary_y=True)
                fig_pareto.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                fig_pareto.update_xaxes(tickangle=-25)
                fig_pareto.update_yaxes(title_text="Minutos", secondary_y=False, showgrid=False)
                fig_pareto.update_yaxes(title_text="% Acumulado", secondary_y=True, range=[0, 105], showgrid=False)
                st.plotly_chart(fig_pareto, use_container_width=True)
            else:
                st.success("¡Excelente! No hay causas de demoras registradas hoy.")

        with col_dona:
            st.subheader("🍩 Radiografía por Flota")
            flotas = ["KY-250", "DM-75", "PRECORTE"]
            fig_pie = make_subplots(rows=1, cols=3, specs=[[{'type':'domain'}, {'type':'domain'}, {'type':'domain'}]], subplot_titles=flotas)
            hay_datos_donas = False
            for i, flota in enumerate(flotas):
                df_flota = df_hist[df_hist['Flota'] == flota]
                if not df_flota.empty:
                    hay_datos_donas = True
                    df_grp = df_flota.groupby('Estado')['Dur'].sum().reset_index()
                    df_grp['Horas'] = df_grp['Dur'] / 60.0
                    df_no_perf = df_grp[df_grp['Estado'] != 'Perforación']
                    peor_estado = df_no_perf.loc[df_no_perf['Dur'].idxmax()]['Estado'] if not df_no_perf.empty and df_no_perf['Dur'].sum() > 0 else None
                    pulls = [0.15 if est == peor_estado else 0 for est in df_grp['Estado']]
                    d, u = calcular_kpis(df_flota)
                    fig_pie.add_trace(go.Pie(
                        labels=df_grp['Estado'], values=df_grp['Dur'], customdata=df_grp['Horas'],
                        hovertemplate="<b>%{label}</b><br>%{customdata:.1f} hrs<br>%{percent}<extra></extra>",
                        hole=0.65, pull=pulls, marker_colors=[COLORES_ESTADO[est] for est in df_grp['Estado']],
                        textposition='inside', textinfo='percent',
                        title=dict(text=f"{u:.0f}%<br>Util", font=dict(size=12, color="white"))
                    ), 1, i+1)

            if hay_datos_donas:
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=30, b=0), showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5, font=dict(size=11)))
                fig_pie.update_annotations(font_size=13, font_color="white") 
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Sin registros operativos para graficar.")
                
        st.divider()

        # --- FILA 3: HEATMAP MATRIZ DE CUELLOS DE BOTELLA ---
        st.subheader("🔥 Matriz de Cuellos de Botella (Demoras por Hora)")
        horas_ordenadas = [f"{h:02d}:00" for h in range(7, 24)] + [f"{h:02d}:00" for h in range(0, 7)]
        df_heat = df_hist[df_hist['Estado'] != 'Perforación'].copy()
        
        if not df_heat.empty:
            df_heat['Hora_Format'] = df_heat['Inicio'].dt.hour.apply(lambda x: f"{x:02d}:00")
            df_hm = df_heat.groupby(['Equipo', 'Hora_Format'])['Dur'].sum().reset_index()
            pivot_hm = df_hm.pivot(index='Equipo', columns='Hora_Format', values='Dur').reindex(index=LISTA_EQUIPOS, columns=horas_ordenadas).fillna(0)
            
            fig_heat = go.Figure(data=go.Heatmap(
                z=pivot_hm.values, x=pivot_hm.columns, y=pivot_hm.index,
                colorscale='YlOrRd', hoverongaps=False,
                hovertemplate="<b>Máquina:</b> %{y}<br><b>Hora:</b> %{x}<br><b>Minutos Perdidos:</b> %{z:.1f}<extra></extra>"
            ))
            fig_heat.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0), height=450, xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.success("Toda la flota se mantuvo perforando. No hay demoras en esta fecha.")

        st.divider()
        
        # --- FILA 4: TENDENCIA HISTÓRICA ---
        st.subheader("📈 Tendencia Histórica (Últimos 7 Días)")
        df_raw['Fecha_Op'] = (df_raw['Inicio'] - timedelta(hours=7)).dt.date
        ultimos_7 = df_raw.groupby('Fecha_Op').apply(lambda x: pd.Series(calcular_kpis(x), index=['Disp', 'Util'])).reset_index()
        ultimos_7 = ultimos_7.tail(7)
        
        if len(ultimos_7) > 0:
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=ultimos_7['Fecha_Op'], y=ultimos_7['Disp'], mode='lines+markers', name='Disponibilidad', line=dict(color='#d62728', width=3)))
            fig_trend.add_trace(go.Scatter(x=ultimos_7['Fecha_Op'], y=ultimos_7['Util'], mode='lines+markers', name='Utilización', line=dict(color='#2ca02c', width=3)))
            fig_trend.update_layout(yaxis=dict(range=[0, 105], title="Porcentaje (%)"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_trend, use_container_width=True)
