import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN INTEGRADA ---
st.set_page_config(page_title="Gestor de Perforación v3.1", layout="wide")

# Mantenemos tu sistema de Login que ya conoces
def check_password():
    def password_entered():
        if st.session_state["password"] == "Mina2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.text_input("🔑 Credencial de Acceso", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if check_password():
    # --- CONEXIÓN AUTOMÁTICA (NUEVA MEJORA) ---
    @st.cache_resource
    def init_connection():
        cred_dict = json.loads(st.secrets["GCP_JSON"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
        return gspread.authorize(credentials)

    client = init_connection()
    sheet = client.open_by_url(st.secrets["SHEET_URL"]).sheet1

    # --- TU LÓGICA DE NEGOCIO (EL CÓDIGO QUE YA USABAS) ---
    st.title("🚜 Sistema de Control de Perforación - Despacho")
    
    # Aquí es donde recuperamos tus columnas originales
    with st.expander("📝 Registro de Actividad", expanded=True):
        with st.form("form_mina"):
            col1, col2, col3 = st.columns(3)
            with col1:
                equipo = st.selectbox("Perforadora", ["PERF-01", "PERF-02", "PERF-03", "PERF-04"])
                flota = st.selectbox("Flota", ["Primaria", "Secundaria", "Pre-Corte"])
            with col2:
                estado = st.selectbox("Estado", ["OPERATIVO", "DEMORA OPERATIVA", "MANTENIMIENTO", "FALLA"])
                detalle = st.text_input("Detalle")
            with col3:
                inicio = st.time_input("Hora Inicio", datetime.now())
                fin = st.time_input("Hora Fin", datetime.now())
            
            submit = st.form_submit_button("Guardar en Nube")

    if submit:
        # Formateamos exactamente como tu base de datos espera
        nueva_fila = [
            equipo, 
            flota, 
            estado, 
            detalle, 
            inicio.strftime("%H:%M"), 
            fin.strftime("%H:%M")
        ]
        sheet.append_row(nueva_fila)
        st.success("¡Datos sincronizados con Google Sheets!")

    st.markdown("---")

    # --- DASHBOARD AVANZADO (TUS GRÁFICOS) ---
    st.subheader("📊 Análisis de Rendimiento")
    
    try:
        # Traemos los datos de la nube para procesar tus KPIs
        datos = sheet.get_all_records()
        if datos:
            df = pd.DataFrame(datos)
            
            # Tus indicadores de siempre
            c1, c2, c3 = st.columns(3)
            c1.metric("Registros Totales", len(df))
            c2.metric("Equipos Reportando", df['equipo'].nunique())
            
            # Tu gráfico de barras por estado que tanto nos costó pulir
            fig = px.bar(df, x="equipo", color="estado", title="Distribución de Estados por Equipo")
            st.plotly_chart(fig, use_container_width=True)
            
            # Tu tabla de auditoría final
            st.write("### Tabla de Auditoría")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Esperando datos para generar estadísticas...")
    except Exception as e:
        st.error("Revisa que los encabezados del Excel coincidan con el código.")
