import streamlit as st
import google.generativeai as genai
import PyPDF2
from io import BytesIO
import json
import os
import re
from gtts import gTTS

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="CORTEX: Study OS", layout="wide", page_icon="🧠")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold;}
    .stProgress > div > div > div > div { background-color: #4CAF50; }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE BIBLIOTECA LOCAL ---
LIBRARY_FOLDER = "biblioteca"
if not os.path.exists(LIBRARY_FOLDER):
    os.makedirs(LIBRARY_FOLDER)

def get_library_files():
    return [f for f in os.listdir(LIBRARY_FOLDER) if f.endswith('.pdf')]

# --- FUNCIONES ROBUSTAS (NUEVAS) ---

def try_connect_model(api_key):
    """Prueba qué modelo está disponible para evitar el error NotFound"""
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        model.generate_content("test")
        return 'gemini-1.5-flash'
    except:
        return 'gemini-pro' # Fallback seguro

def extract_text(path):
    """Lee el PDF con protección contra archivos corruptos"""
    try:
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = "".join([p.extract_text() for p in reader.pages])
        return text
    except Exception as e:
        # Si el archivo está corrupto, lo borramos para no romper la app
        st.error(f"Archivo corrupto detectado: {path}. Eliminando...")
        try:
            os.remove(path)
            st.session_state['current_file'] = None
            st.rerun()
        except:
            pass
        return None

def ask_gemini(prompt, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Captura errores de API y devuelve un string vacío seguro
        return ""

def safe_json_parse(text):
    """Intenta extraer JSON incluso si la IA añade texto extra"""
    if not text: return []
    try:
        # Busca contenido entre corchetes
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match: return json.loads(match.group(0))
        # Busca contenido entre llaves
        match_obj = re.search(r'\{.*\}', text, re.DOTALL)
        if match_obj: 
            data = json.loads(match_obj.group(0))
            return [data] if not isinstance(data, list) else data
        # Intenta limpieza básica
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return []

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/brain.png", width=120)
    st.title("CORTEX v4.0")
    st.caption("Auto-Recovery System")
    
    # API KEY
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ API Key Secreta")
    else:
        api_key = st.text_input("🔑 API Key Google", type="password")

    # DETECCIÓN DE MODELO
    valid_model = None
    if api_key:
        valid_model = try_connect_model(api_key)
        # st.caption(f"🤖 Modelo activo: {valid_model}")

    st.divider()

    # BIBLIOTECA
    st.subheader("📚 Biblioteca")
    mode = st.radio("Menú:", ["📖 Estudiar", "📤 Subir PDF"], label_visibility="collapsed")
    
    selected_file_path = None
    
    if mode == "📖 Estudiar":
        files = get_library_files()
        if files:
            selected_file = st.selectbox("Elige un libro:", files)
            selected_file_path = os.path.join(LIBRARY_FOLDER, selected_file)
            
            # Botón de emergencia para borrar archivo actual
            if st.button("🗑️ Borrar este libro"):
                os.remove(selected_file_path)
                st.session_state['current_file'] = None
                st.rerun()
        else:
            st.info("No hay libros. Sube uno abajo.")
            
    elif mode == "📤 Subir PDF":
        uploaded_file = st.file_uploader("Arrastra aquí", type="pdf")
        if uploaded_file:
            save_path = os.path.join(LIBRARY_FOLDER, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success("Subida exitosa.")
            time.sleep(1) # Pequeña pausa para asegurar escritura
            st.rerun()

    st.divider()
    socratic_mode = st.toggle("🎓 Modo Socrático", value=False)

# --- ESTADO (SESSION STATE) ---
if 'messages' not in st.session_state: st.session_state['messages'] = []
if 'quiz_data' not in st.session_state: st.session_state['quiz_data'] = None
if 'doc_text' not in st.session_state: st.session_state['doc_text'] = ""
if 'current_file' not in st.session_state: st.session_state['current_file'] = None
if 'flashcards' not in st.session_state: st.session_state['flashcards'] = []

# --- LÓGICA PRINCIPAL ---
if selected_file_path and api_key and valid_model:
    
    # Cambio de archivo
    if st.session_state['current_file'] != selected_file_path:
        st.session_state['current_file'] = selected_file_path
        st.session_state['doc_text'] = ""
        st.session_state['messages'] = []
        st.session_state['quiz_data'] = None
        st.session_state['flashcards'] = []
        st.rerun()

    # Carga de Texto
    if st.session_state['doc_text'] == "":
        with st.spinner("🧠 Leyendo documento..."):
            extracted = extract_text(selected_file_path)
            if extracted:
                st.session_state['doc_text'] = extracted
            else:
                st.stop() # Detiene la ejecución si falló la lectura

    # PESTAÑAS
    t1, t2, t3, t4 = st.tabs(["Chat", "Examen", "Flashcards", "Recursos"])

    # 1. CHAT
    with t1:
        prompt_sys = "Eres un tutor socrático." if socratic_mode else "Eres un profesor experto."
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if p := st.chat_input("Pregunta..."):
            st.session_state.messages.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                full = f"{prompt_sys}\nContexto: {st.session_state['doc_text'][:25000]}\nPregunta: {p}"
                res = ask_gemini(full, valid_model)
                if res:
                    st.markdown(res)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                else:
                    st.error("Error de conexión con Google Gemini.")

    # 2. EXAMEN
    with t2:
        if st.button("📝 Crear Examen"):
            with st.spinner("Generando..."):
                p = f"Genera 3 preguntas multiple choice JSON válido: [{{'pregunta':'...', 'opciones':['A)..','B)..','C).. '], 'correcta':'A)..'}}] sobre: {st.session_state['doc_text'][:10000]}"
                data = safe_json_parse(ask_gemini(p, valid_model))
                if data:
                    st.session_state['quiz_data'] = data
                    st.session_state['quiz_submitted'] = False
                    st.rerun()
                else:
                    st.warning("La IA no pudo generar el examen. Intenta de nuevo (a veces pasa).")

        if st.session_state['quiz_data']:
            score = 0
            for i, q in enumerate(st.session_state['quiz_data']):
                st.markdown(f"**{i+1}. {q['pregunta']}**")
                val = st.radio(f"R:", q['opciones'], key=f"q{i}", disabled=st.session_state.get('quiz_submitted', False))
                if st.session_state.get('quiz_submitted', False):
                    if val and val.startswith(q['correcta'][0]): 
                        st.success("Correcto") 
                        score+=1
                    else: st.error(f"Era: {q['correcta']}")
            
            if not st.session_state.get('quiz_submitted', False):
                if st.button("Corregir"): 
                    st.session_state['quiz_submitted'] = True
                    st.rerun()
            else:
                st.metric("Nota", f"{score}/{len(st.session_state['quiz_data'])}")

    # 3. FLASHCARDS
    with t3:
        if st.button("⚡ Flashcards"):
            with st.spinner("Generando..."):
                p = f"Genera 5 flashcards JSON: [{{'pregunta':'...', 'respuesta':'...'}}] sobre: {st.session_state['doc_text'][:10000]}"
                data = safe_json_parse(ask_gemini(p, valid_model))
                if data:
                    st.session_state['flashcards'] = data
                    st.session_state['fc_idx'] = 0
                    st.rerun()
        
        if st.session_state['flashcards']:
            i = st.session_state.get('fc_idx', 0)
            if i >= len(st.session_state['flashcards']): i=0
            card = st.session_state['flashcards'][i]
            st.info(f"Card {i+1}/{len(st.session_state['flashcards'])}")
            with st.container(border=True):
                st.subheader(card['pregunta'])
                if st.checkbox("Respuesta", key=f"fc{i}"): st.warning(card['respuesta'])
            c1,c2 = st.columns(2)
            if c1.button("Prev") and i>0: 
                st.session_state['fc_idx'] = i-1
                st.rerun()
            if c2.button("Next") and i<len(st.session_state['flashcards'])-1: 
                st.session_state['fc_idx'] = i+1
                st.rerun()

    # 4. RECURSOS
    with t4:
        if st.button("🔍 Buscar Videos"):
            p = f"3 conceptos clave separados por comas de: {st.session_state['doc_text'][:5000]}"
            res = ask_gemini(p, valid_model)
            if res:
                for c in res.split(","):
                    st.markdown(f"**📺 {c.strip()}** -> [YouTube](https://www.youtube.com/results?search_query={c.strip().replace(' ','+')})")

elif not api_key:
    st.warning("👈 Ingresa tu API Key en la barra lateral.")
elif not selected_file_path:
    st.info("👈 Selecciona o sube un PDF.")
