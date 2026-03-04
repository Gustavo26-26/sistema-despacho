import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Despacho Mina - Perforadoras", layout="wide")

# --- SISTEMA DE LOGIN BÁSICO ---
def check_password():
    """Devuelve True si el usuario ingresó la contraseña correcta."""
    def password_entered():
        if st.session_state["password"] == "Mina2026": # <-- Esta es tu contraseña
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Borramos la clave por seguridad
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔑 Ingrese la contraseña de Despacho", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("🔑 Ingrese la contraseña de Despacho", type="password", on_change=password_entered, key="password")
        st.error("Contraseña incorrecta. Intente de nuevo.")
        return False
    return True

if check_password():
    # --- CONEXIÓN A GOOGLE SHEETS ---
    @st.cache_resource
    def init_connection():
        # Leer las credenciales secretas que guardaste en Streamlit
        cred_dict = json.loads(st.secrets["GCP_JSON"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        credentials = Credentials.from_service_account_info(cred_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client

    # Conectar y abrir la hoja
    try:
        client = init_connection()
        url = st.secrets["SHEET_URL"]
        sheet = client.open_by_url(url).sheet1
    except Exception as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        st.stop()

    # --- PANEL PRINCIPAL ---
    st.title("🚜 Panel de Control - Perforadoras Eléctricas")
    st.markdown("---")

    # Formulario de ingreso de datos
    with st.form("registro_tiempos"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            equipo = st.selectbox("Equipo", ["Seleccionar", "Perforadora 01", "Perforadora 02", "Perforadora 03"])
            operador = st.text_input("Nombre del Operador")
        
        with col2:
            estado = st.selectbox("Estado del Equipo", ["Operativo", "Demora Operativa", "Mantenimiento Preventivo", "Falla Mecánica/Eléctrica"])
            metros_perforados = st.number_input("Metros Perforados (m)", min_value=0.0, format="%.2f")
            
        with col3:
            comentarios = st.text_area("Comentarios / Reporte de Demoras")

        submit_button = st.form_submit_button(label="Guardar Registro")

    # Acción al presionar el botón
    if submit_button:
        if equipo == "Seleccionar":
            st.warning("⚠️ Por favor seleccione un equipo.")
        else:
            fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Fila de datos a insertar (debe coincidir con las columnas de tu Excel)
            nueva_fila = [fecha_hora, equipo, operador, estado, metros_perforados, comentarios]
            
            # Escribir en Google Sheets
            sheet.append_row(nueva_fila)
            st.success(f"✅ Registro guardado exitosamente para la {equipo}.")

    st.markdown("---")
    
    # Mostrar los datos actuales en una tabla
    st.subheader("📊 Últimos Registros")
    try:
        datos = sheet.get_all_records()
        if datos:
            df = pd.DataFrame(datos)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("La base de datos está vacía. Ingrese el primer registro.")
    except Exception as e:
        st.error("No se pudieron cargar los registros. Asegúrese de que su Google Sheets tenga la primera fila con los encabezados correspondientes (Fecha, Equipo, Operador, Estado, Metros, Comentarios).")
