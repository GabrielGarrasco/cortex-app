import streamlit as st
import google.generativeai as genai
import PyPDF2
from io import BytesIO
import pandas as pd

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="CORTEX: Deep Learning", layout="wide", page_icon="🧠")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/brain.png", width=100)
    st.title("CORTEX v1.1")
    st.caption("Tu Segundo Cerebro")
    
    # --- CAMBIO IMPORTANTE AQUÍ ---
    # Intentamos buscar la clave en los Secretos de Streamlit
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ Llave de seguridad detectada automáticamente.")
    else:
        # Si no está en secretos, la pedimos manual (Plan B)
        api_key = st.text_input("🔑 Tu API Key de Google", type="password")
    
    st.divider()
    
    # Subida de Archivos
    uploaded_file = st.file_uploader("📂 Sube tu apunte (PDF)", type="pdf")
    
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.warning("Configura tu API Key en los 'Secrets' de Streamlit.")

# --- FUNCIONES DEL CEREBRO ---
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def ask_gemini(prompt):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    return response.text

# --- INTERFAZ PRINCIPAL ---
if uploaded_file and api_key:
    # Procesar PDF solo una vez
    if 'doc_text' not in st.session_state:
        with st.spinner("🧠 Leyendo y analizando documento..."):
            text = extract_text_from_pdf(uploaded_file)
            st.session_state['doc_text'] = text
            st.success("¡Documento cargado en la memoria!")

    # Pestañas de funciones
    tab1, tab2, tab3 = st.tabs(["👨‍🏫 Tutoría IA", "📝 Examen Generativo", "📊 Progreso"])

    # --- PESTAÑA 1: TUTOR ---
    with tab1:
        st.header("Entendimiento Profundo")
        st.write("Chatea con tu documento. Pregunta dudas específicas.")
        
        # Historial de chat
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ej: Explícame el concepto principal de la página 3"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                full_prompt = f"""
                Actúa como un profesor experto. Usa SOLO el siguiente contexto para responder.
                Si la respuesta no está en el texto, dilo.
                
                CONTEXTO: {st.session_state['doc_text'][:20000]}
                
                PREGUNTA: {prompt}
                """
                try:
                    response = ask_gemini(full_prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- PESTAÑA 2: EXAMEN ---
    with tab2:
        st.header("Autoevaluación")
        nivel = st.select_slider("Nivel", ["Fácil", "Medio", "Difícil", "Pesadilla"])
        
        if st.button("Generar Preguntas"):
            with st.spinner("Creando examen único..."):
                prompt_quiz = f"""
                Genera 3 preguntas de opción múltiple (A, B, C) sobre el texto.
                Nivel de dificultad: {nivel}.
                Al final, pon las respuestas correctas ocultas.
                
                TEXTO: {st.session_state['doc_text'][:15000]}
                """
                try:
                    quiz = ask_gemini(prompt_quiz)
                    st.session_state['last_quiz'] = quiz
                except Exception as e:
                    st.error("Error generando examen. Intenta de nuevo.")
        
        if 'last_quiz' in st.session_state:
            st.markdown(st.session_state['last_quiz'])
            st.info("Anota tus respuestas en un papel y verifica.")

    # --- PESTAÑA 3: PROGRESO ---
    with tab3:
        st.write("Aquí guardaremos tus notas (Próximamente conectaremos la Base de Datos).")

else:
    # Pantalla de bienvenida
    st.title("Bienvenido a CORTEX 🧠")
    st.markdown("""
    Esta herramienta usa Inteligencia Artificial para ayudarte a estudiar tus propios apuntes.
    
    1. **Sube tu PDF**.
    2. **Empieza a estudiar**.
    """)
