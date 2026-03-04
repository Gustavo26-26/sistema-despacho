import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión de Perforación", layout="wide")

# --- SISTEMA DE LOGIN ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "Mina2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔑 Ingrese la contraseña de Despacho", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔑 Ingrese la contraseña de Despacho", type="password", on_change=password_entered, key="password")
        st.error("Contraseña incorrecta.")
        return False
    return True

if check_password():
    # --- CONEXIÓN A GOOGLE SHEETS ---
    @st.cache_resource
    def init_connection():
        cred_dict = json.loads(st.secrets["GCP_JSON"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
        return gspread.authorize(credentials)

    try:
        client = init_connection()
        sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- DISEÑO DEL DASHBOARD ---
    st.title("🚜 Sistema de Control de Perforación")
    
    # Sidebar con información del turno
    st.sidebar.header("Configuración de Turno")
    fecha_actual = st.sidebar.date_input("Fecha", datetime.now())
    guardia = st.sidebar.selectbox("Guardia", ["Día", "Noche"])

    # --- FORMULARIO DE REGISTRO ---
    with st.expander("📝 Registrar Nuevo Evento / Estado", expanded=True):
        with st.form("registro_tiempos"):
            c1, c2, c3 = st.columns(3)
            with c1:
                equipo = st.selectbox("Equipo", ["Seleccionar", "PERF-01", "PERF-02", "PERF-03"])
                flota = st.selectbox("Flota", ["Primaria", "Secundaria", "Pre-Corte"])
            with c2:
                estado = st.selectbox("Estado", ["OPERATIVO", "DEMORA OPERATIVA", "MANTENIMIENTO", "FALLA MECÁNICA", "STANDBY"])
                detalle = st.text_input("Detalle / Comentario")
            with c3:
                hora_inicio = st.time_input("Hora Inicio", datetime.now().time())
                hora_fin = st.time_input("Hora Fin", datetime.now().time())

            submit = st.form_submit_button("Guardar en Base de Datos")

    if submit:
        if equipo == "Seleccionar":
            st.warning("Seleccione un equipo válido.")
        else:
            # ORDEN EXACTO PARA TU EXCEL: equipo, flota, estado, detalle, inicio, fin
            h_inicio = hora_inicio.strftime("%H:%M")
            h_fin = hora_fin.strftime("%H:%M")
            
            fila = [equipo, flota, estado, detalle, h_inicio, h_fin]
            
            sheet.append_row(fila)
            st.success(f"✅ Registrado: {equipo} en estado {estado}")

    st.markdown("---")

    # --- VISUALIZACIÓN DE DATOS ---
    st.subheader("📊 Resumen de Actividades")
    
    try:
        datos = sheet.get_all_records()
        if datos:
            df = pd.DataFrame(datos)
            
            # Métricas rápidas
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Registros", len(df))
            m2.metric("Equipos Activos", df['equipo'].nunique())
            
            # Tabla de datos
            st.dataframe(df.tail(10), use_container_width=True) # Muestra los últimos 10
            
            # Gráfico simple de estados
            st.bar_chart(df['estado'].value_counts())
        else:
            st.info("No hay datos registrados aún.")
    except:
        st.warning("Para ver el resumen, asegúrate de que la primera fila de tu Excel tenga estos encabezados exactos: equipo, flota, estado, detalle, inicio, fin")
