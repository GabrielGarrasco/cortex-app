import streamlit as st
import google.generativeai as genai
import PyPDF2
from io import BytesIO
import json
import os # <--- NUEVO: Para manejar archivos del sistema
from gtts import gTTS

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="CORTEX: Study Companion",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 10px; }
    .flashcard { background-color: #f0f2f6; padding: 20px; border-radius: 15px; border-left: 5px solid #4CAF50; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE BIBLIOTECA LOCAL (NUEVO) ---
LIBRARY_FOLDER = "biblioteca"

if not os.path.exists(LIBRARY_FOLDER):
    os.makedirs(LIBRARY_FOLDER)

def get_library_files():
    return [f for f in os.listdir(LIBRARY_FOLDER) if f.endswith('.pdf')]

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/brain.png", width=100)
    st.title("CORTEX v2.1")
    st.caption("Memoria Persistente")
    
    # API Key
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ Llave detectada")
    else:
        api_key = st.text_input("🔑 Tu API Key de Google", type="password")
    
    st.divider()

    # --- NUEVO SISTEMA DE ARCHIVOS ---
    st.subheader("📚 Tu Biblioteca")
    
    # 1. Selector de Modo (Subir o Elegir)
    mode = st.radio("Opción:", ["📂 Abrir Existente", "⬆️ Subir Nuevo"])
    
    selected_file_path = None
    
    if mode == "📂 Abrir Existente":
        files = get_library_files()
        if files:
            selected_file = st.selectbox("Selecciona un libro:", files)
            selected_file_path = os.path.join(LIBRARY_FOLDER, selected_file)
            st.info(f"📖 Leyendo: {selected_file}")
        else:
            st.warning("La biblioteca está vacía. Sube un archivo primero.")
            
    elif mode == "⬆️ Subir Nuevo":
        uploaded_file = st.file_uploader("Arrastra tu PDF aquí", type="pdf")
        if uploaded_file:
            # Guardar el archivo en la carpeta biblioteca
            save_path = os.path.join(LIBRARY_FOLDER, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✅ Guardado en biblioteca: {uploaded_file.name}")
            selected_file_path = save_path
            # Forzar recarga para actualizar la lista
            st.rerun()

    st.divider()
    
    # Configuración del Tutor
    st.subheader("⚙️ Configuración")
    socratic_mode = st.toggle("🎓 Modo Socrático", value=False)

    if api_key:
        genai.configure(api_key=api_key)

# --- FUNCIONES ---
def extract_text_from_pdf(file_path):
    # Modificado para leer desde ruta de archivo, no objeto Streamlit
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text

def clean_json_text(text):
    text = text.replace("```json", "").replace("```", "")
    return text.strip()

def ask_gemini(prompt):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text

# --- LÓGICA DE ESTADO ---
# Inicializamos variables si no existen
if 'current_file' not in st.session_state: st.session_state['current_file'] = None
if 'doc_text' not in st.session_state: st.session_state['doc_text'] = ""
if 'flashcards' not in st.session_state: st.session_state['flashcards'] = []
if 'current_card' not in st.session_state: st.session_state['current_card'] = 0
if 'messages' not in st.session_state: st.session_state['messages'] = []

# --- PROCESAMIENTO ---
if selected_file_path and api_key:
    
    # Detectar si cambiamos de libro para limpiar la memoria
    if st.session_state['current_file'] != selected_file_path:
        st.session_state['current_file'] = selected_file_path
        st.session_state['messages'] = [] # Limpiar chat anterior
        st.session_state['flashcards'] = [] # Limpiar flashcards anteriores
        st.session_state['doc_text'] = "" # Limpiar texto
        st.rerun()

    # Cargar texto si es necesario
    if st.session_state['doc_text'] == "":
        with st.spinner("🧠 Indexando conocimiento..."):
            text = extract_text_from_pdf(selected_file_path)
            st.session_state['doc_text'] = text
            # st.toast("¡Libro cargado!", icon="📚")

    # --- TABS (IGUAL QUE ANTES) ---
    tab1, tab2, tab3, tab4 = st.tabs(["👨‍🏫 Chat", "📇 Flashcards", "🗺️ Mapa", "🎧 Audio"])

    # 1. CHAT
    with tab1:
        st.header("Chat con tu Biblioteca")
        if socratic_mode:
            system_prompt = "Eres un tutor socrático. NO des respuestas directas. Haz preguntas guía."
        else:
            system_prompt = "Eres un profesor experto y directo."

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if prompt := st.chat_input("Pregunta al libro..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                full_prompt = f"{system_prompt}\nCONTEXTO: {st.session_state['doc_text'][:25000]}\nPREGUNTA: {prompt}"
                try:
                    res = ask_gemini(full_prompt)
                    st.markdown(res)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                except Exception as e: st.error(str(e))

    # 2. FLASHCARDS
    with tab2:
        col_gen, col_info = st.columns([1, 3])
        with col_gen:
            if st.button("⚡ Generar Flashcards"):
                with st.spinner("Creando..."):
                    p = f"Genera 5 flashcards JSON: [{{'pregunta':'...', 'respuesta':'...'}}] sobre: {st.session_state['doc_text'][:15000]}"
                    try:
                        r = ask_gemini(p)
                        st.session_state['flashcards'] = json.loads(clean_json_text(r))
                        st.rerun()
                    except: st.error("Error al generar.")

        if st.session_state['flashcards']:
            i = st.session_state['current_card']
            card = st.session_state['flashcards'][i]
            st.progress((i+1)/len(st.session_state['flashcards']))
            with st.container(border=True):
                st.markdown(f"### {card['pregunta']}")
                if st.checkbox("Ver respuesta", key=f"rev_{i}"): st.success(card['respuesta'])
            c1, c2, c3 = st.columns([1,2,1])
            if c1.button("⬅️") and i>0: 
                st.session_state['current_card'] -= 1
                st.rerun()
            if c3.button("➡️") and i<len(st.session_state['flashcards'])-1: 
                st.session_state['current_card'] += 1
                st.rerun()

    # 3. MAPA MENTAL
    with tab3:
        if st.button("🗺️ Ver Mapa"):
            p = f"Crea código Graphviz DOT simple del texto: {st.session_state['doc_text'][:15000]}"
            try: st.graphviz_chart(clean_json_text(ask_gemini(p)))
            except: st.error("Error visualizando.")

    # 4. AUDIO
    with tab4:
        if st.button("🎧 Crear Podcast"):
            p = f"Resumen estilo podcast de 150 palabras de: {st.session_state['doc_text'][:15000]}"
            txt = ask_gemini(p)
            st.write(txt)
            tts = gTTS(txt, lang='es')
            bio = BytesIO()
            tts.write_to_fp(bio)
            st.audio(bio, format='audio/mp3')

else:
    st.info("👈 Selecciona o sube un libro en la barra lateral para comenzar.")
