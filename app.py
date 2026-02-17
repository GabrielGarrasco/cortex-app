import streamlit as st
import google.generativeai as genai
import PyPDF2
from io import BytesIO
import json
import re
from gtts import gTTS

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="CORTEX: Study Companion",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        border-radius: 10px;
    }
    .flashcard {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #4CAF50;
        margin-bottom: 10px;
        color: #333333; /* Texto oscuro para contraste */
    }
</style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/brain.png", width=100)
    st.title("CORTEX v2.0")
    st.caption("Tu Segundo Cerebro")
    
    # Gestión de API Key
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ Llave detectada")
    else:
        api_key = st.text_input("🔑 Tu API Key de Google", type="password")
    
    st.divider()
    
    # Subida de Archivos
    uploaded_file = st.file_uploader("📂 Sube tu apunte (PDF)", type="pdf")
    
    st.divider()
    
    # Configuración del Tutor
    st.subheader("⚙️ Configuración del Tutor")
    socratic_mode = st.toggle("🎓 Modo Socrático", value=False, help="Si se activa, la IA no te dará la respuesta directa, sino que te hará preguntas para que tú llegues a ella.")

    if api_key:
        genai.configure(api_key=api_key)

# --- FUNCIONES AUXILIARES ---
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def clean_json_text(text):
    """Limpia el texto para asegurar que sea un JSON válido"""
    text = text.replace("```json", "").replace("```", "")
    return text.strip()

def ask_gemini(prompt):
    model = genai.GenerativeModel('gemini-1.5-flash') # Usamos flash por velocidad
    response = model.generate_content(prompt)
    return response.text

# --- LÓGICA DE ESTADO (SESSION STATE) ---
if 'doc_text' not in st.session_state:
    st.session_state['doc_text'] = ""
if 'flashcards' not in st.session_state:
    st.session_state['flashcards'] = []
if 'current_card' not in st.session_state:
    st.session_state['current_card'] = 0
if 'messages' not in st.session_state:
    st.session_state['messages'] = []

# --- PROCESAMIENTO INICIAL ---
if uploaded_file and api_key:
    if st.session_state['doc_text'] == "":
        with st.spinner("🧠 Leyendo y analizando documento..."):
            text = extract_text_from_pdf(uploaded_file)
            st.session_state['doc_text'] = text
            st.toast("¡Documento cargado en la memoria!", icon="✅")

    # --- INTERFAZ PRINCIPAL CON PESTAÑAS ---
    tab1, tab2, tab3, tab4 = st.tabs([
        "👨‍🏫 Chat Tutor", 
        "📇 Flashcards", 
        "🗺️ Mapa Mental", 
        "🎧 Audio Resumen"
    ])

    # --- PESTAÑA 1: CHAT TUTOR (SOCRÁTICO O DIRECTO) ---
    with tab1:
        st.header("Entendimiento Profundo")
        
        # Definir la personalidad según el modo
        if socratic_mode:
            system_prompt = """
            Eres un tutor socrático experto. TU OBJETIVO ES QUE EL ALUMNO PIENSE.
            1. NO des respuestas directas ni largas explicaciones.
            2. Haz una pregunta guía basada en el texto para ayudar al usuario a encontrar la respuesta.
            3. Sé amable pero firme en tu metodología de enseñanza.
            """
            st.info("💡 Modo Socrático Activado: La IA te guiará con preguntas.")
        else:
            system_prompt = """
            Eres un profesor experto y claro.
            1. Responde de forma directa, estructurada y fácil de entender.
            2. Usa ejemplos y analogías si es necesario.
            """

        # Mostrar historial
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Input del usuario
        if prompt := st.chat_input("Pregunta algo sobre tu documento..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                full_prompt = f"""
                {system_prompt}
                
                CONTEXTO DEL DOCUMENTO: 
                {st.session_state['doc_text'][:25000]} 
                
                PREGUNTA DEL ESTUDIANTE: {prompt}
                """
                with st.spinner("Pensando..."):
                    try:
                        response = ask_gemini(full_prompt)
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        st.error(f"Error: {e}")

    # --- PESTAÑA 2: FLASHCARDS (ACTIVE RECALL) ---
    with tab2:
        st.header("Repaso Activo (Flashcards)")
        
        col_gen, col_info = st.columns([1, 3])
        
        with col_gen:
            if st.button("⚡ Generar Nuevas Flashcards"):
                with st.spinner("Creando tarjetas de estudio..."):
                    prompt_fc = f"""
                    Crea 5 flashcards educativas basadas en el texto.
                    FORMATO OBLIGATORIO JSON:
                    [
                        {{"pregunta": "Pregunta 1", "respuesta": "Respuesta breve 1"}},
                        {{"pregunta": "Pregunta 2", "respuesta": "Respuesta breve 2"}}
                    ]
                    No añadas nada más fuera del JSON.
                    
                    TEXTO: {st.session_state['doc_text'][:15000]}
                    """
                    try:
                        response_text = ask_gemini(prompt_fc)
                        cleaned_json = clean_json_text(response_text)
                        st.session_state['flashcards'] = json.loads(cleaned_json)
                        st.session_state['current_card'] = 0
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generando flashcards: {e}")

        # Visualización de Tarjetas
        if st.session_state['flashcards']:
            current = st.session_state['current_card']
            total = len(st.session_state['flashcards'])
            card = st.session_state['flashcards'][current]
            
            st.progress((current + 1) / total)
            st.caption(f"Tarjeta {current + 1} de {total}")
            
            # Tarjeta visual
            with st.container(border=True):
                st.markdown(f"### ❓ {card['pregunta']}")
                st.write("---")
                if st.checkbox("Mostrar Respuesta", key=f"reveal_{current}"):
                    st.markdown(f"#### ✅ {card['respuesta']}")
            
            # Controles de navegación
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if st.button("⬅️ Anterior") and current > 0:
                    st.session_state['current_card'] -= 1
                    st.rerun()
            with c3:
                if st.button("Siguiente ➡️") and current < total - 1:
                    st.session_state['current_card'] += 1
                    st.rerun()
        else:
            st.info("Presiona el botón para generar tarjetas basadas en tu PDF.")

    # --- PESTAÑA 3: MAPA MENTAL (DUAL CODING) ---
    with tab3:
        st.header("Visualización de Conceptos")
        st.write("Genera un grafo visual para entender las conexiones entre temas.")
        
        if st.button("🗺️ Generar Mapa Mental"):
            with st.spinner("Analizando estructuras del texto..."):
                prompt_graph = f"""
                Crea un código de Graphviz (DOT) simple para un mapa mental de los conceptos CLAVE de este texto.
                - Usa formas simples.
                - No uses etiquetas complejas.
                - Devuelve SOLO el código dentro de las llaves, sin bloques de código markdown.
                
                TEXTO: {st.session_state['doc_text'][:15000]}
                """
                try:
                    dot_code = ask_gemini(prompt_graph)
                    clean_dot = clean_json_text(dot_code) # Reusamos la limpieza
                    st.graphviz_chart(clean_dot)
                except Exception as e:
                    st.error(f"No se pudo generar el gráfico: {e}")

    # --- PESTAÑA 4: AUDIO PODCAST ---
    with tab4:
        st.header("Aprendizaje Auditivo")
        st.write("Convierte tus apuntes en un podcast resumen para escuchar mientras haces otras cosas.")
        
        if st.button("🎧 Generar Podcast"):
            with st.spinner("Escribiendo guion y sintetizando voz..."):
                # 1. Generar resumen texto
                prompt_audio = f"""
                Escribe un guion de podcast muy ameno, explicativo y fácil de escuchar sobre este texto.
                Que parezca que un profesor le habla a un alumno. Máximo 200 palabras.
                
                TEXTO: {st.session_state['doc_text'][:15000]}
                """
                guion = ask_gemini(prompt_audio)
                st.markdown(f"**Guion generado:** *{guion}*")
                
                # 2. Convertir a Audio (gTTS)
                try:
                    tts = gTTS(text=guion, lang='es')
                    audio_bytes = BytesIO()
                    tts.write_to_fp(audio_bytes)
                    st.audio(audio_bytes, format='audio/mp3')
                except Exception as e:
                    st.error(f"Error de audio: {e}")

else:
    # Pantalla de bienvenida sin archivo cargado
    st.markdown("""
    <div style='text-align: center;'>
        <h1>Bienvenido a CORTEX 🧠</h1>
        <h3>Tu sistema operativo de estudio potenciado por IA</h3>
        <p>Sube un PDF en la barra lateral para desbloquear:</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tutor IA", "Socrático", "Preguntas Guía")
    col2.metric("Flashcards", "Auto-generadas", "Repaso Activo")
    col3.metric("Mapas", "Visuales", "Graphviz")
    col4.metric("Podcast", "Audio MP3", "On-the-go")
