import streamlit as st
import google.generativeai as genai
import PyPDF2
from io import BytesIO
import json
import os
import re
import time  # <--- AGREGADO: Esto arregla el NameError
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

# --- FUNCIONES DE SEGURIDAD Y CONEXIÓN ---

def try_connect_model(api_key):
    """Prueba conexión. Si falla Flash, usa Pro (más compatible)."""
    genai.configure(api_key=api_key)
    try:
        # Intentamos listar modelos para ver si la key funciona
        model = genai.GenerativeModel('gemini-1.5-flash')
        model.generate_content("test")
        return 'gemini-1.5-flash'
    except:
        return 'gemini-pro' # Fallback seguro

def extract_text(path):
    """Lee PDF y BORRA el archivo si está corrupto para no romper la app."""
    try:
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            if len(reader.pages) == 0: raise Exception("PDF Vacío")
            text = "".join([p.extract_text() for p in reader.pages])
        return text
    except Exception as e:
        st.error(f"⚠️ Archivo dañado detectado: {os.path.basename(path)}. Eliminando para recuperar el sistema...")
        try:
            os.remove(path) # Auto-reparación
            time.sleep(2)
            st.rerun()
        except:
            pass
        return None

def ask_gemini(prompt, model_name):
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return ""

def safe_json_parse(text):
    """Limpiador agresivo de JSON."""
    if not text: return []
    try:
        # 1. Buscar bloque JSON puro [...]
        match_list = re.search(r'\[.*\]', text, re.DOTALL)
        if match_list: return json.loads(match_list.group(0))
        
        # 2. Buscar objeto único {...}
        match_obj = re.search(r'\{.*\}', text, re.DOTALL)
        if match_obj: 
            data = json.loads(match_obj.group(0))
            return [data] if not isinstance(data, list) else data
            
        # 3. Limpieza manual de markdown
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except:
        return []

# --- INTERFAZ BARRA LATERAL ---
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/brain.png", width=120)
    st.title("CORTEX v4.1")
    
    # API KEY
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ Online")
    else:
        api_key = st.text_input("🔑 API Key", type="password")

    # DETECTOR DE MODELO
    valid_model = None
    if api_key:
        valid_model = try_connect_model(api_key)

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
            
            if st.button("🗑️ Eliminar Archivo"):
                os.remove(selected_file_path)
                st.session_state['current_file'] = None
                st.rerun()
        else:
            st.info("Biblioteca vacía.")
            
    elif mode == "📤 Subir PDF":
        uploaded_file = st.file_uploader("Arrastra aquí", type="pdf")
        if uploaded_file:
            save_path = os.path.join(LIBRARY_FOLDER, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success("Subido correctamente.")
            time.sleep(1) # Espera segura
            st.rerun()

    st.divider()
    socratic_mode = st.toggle("🎓 Modo Socrático", value=False)

# --- ESTADO ---
if 'messages' not in st.session_state: st.session_state['messages'] = []
if 'quiz_data' not in st.session_state: st.session_state['quiz_data'] = None
if 'doc_text' not in st.session_state: st.session_state['doc_text'] = ""
if 'current_file' not in st.session_state: st.session_state['current_file'] = None
if 'flashcards' not in st.session_state: st.session_state['flashcards'] = []

# --- APP PRINCIPAL ---
if selected_file_path and api_key and valid_model:
    
    # Detectar cambio de archivo
    if st.session_state['current_file'] != selected_file_path:
        st.session_state['current_file'] = selected_file_path
        st.session_state['doc_text'] = ""
        st.session_state['messages'] = []
        st.session_state['quiz_data'] = None
        st.session_state['flashcards'] = []
        st.rerun()

    # Cargar Texto (Con manejo de errores)
    if st.session_state['doc_text'] == "":
        with st.spinner("🧠 Leyendo documento..."):
            extracted = extract_text(selected_file_path)
            if extracted:
                st.session_state['doc_text'] = extracted
            else:
                st.stop() # Detiene la app si el PDF falló (ya se borró)

    # PESTAÑAS
    t1, t2, t3, t4 = st.tabs(["Chat", "Examen", "Flashcards", "Recursos"])

    # 1. CHAT
    with t1:
        st.header("Chat Docente")
        prompt_sys = "Eres un tutor socrático. Guía al alumno con preguntas." if socratic_mode else "Eres un profesor experto y directo."
        
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
        
        if p := st.chat_input("Pregunta al profesor..."):
            st.session_state.messages.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                full = f"{prompt_sys}\nContexto: {st.session_state['doc_text'][:25000]}\nPregunta: {p}"
                res = ask_gemini(full, valid_model)
                if res:
                    st.markdown(res)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                else:
                    st.error("Error de conexión. Intenta de nuevo.")

    # 2. EXAMEN
    with t2:
        st.header("Simulacro")
        if st.button("📝 Generar Examen"):
            with st.spinner("Creando preguntas..."):
                # Prompt reforzado para JSON
                p = f"""
                Genera 3 preguntas multiple choice.
                FORMATO JSON PURO OBLIGATORIO:
                [
                  {{"pregunta": "¿Qué es X?", "opciones": ["A) Y", "B) Z", "C) W"], "correcta": "A) Y"}}
                ]
                Texto: {st.session_state['doc_text'][:10000]}
                """
                data = safe_json_parse(ask_gemini(p, valid_model))
                if data:
                    st.session_state['quiz_data'] = data
                    st.session_state['quiz_submitted'] = False
                    st.rerun()
                else:
                    st.warning("La IA no pudo generar el examen correctamente. Prueba otra vez.")

        if st.session_state['quiz_data']:
            score = 0
            for i, q in enumerate(st.session_state['quiz_data']):
                st.markdown(f"**{i+1}. {q['pregunta']}**")
                val = st.radio(f"Respuesta {i+1}", q['opciones'], key=f"q{i}", disabled=st.session_state.get('quiz_submitted', False))
                
                if st.session_state.get('quiz_submitted', False):
                    # Verificación flexible (por letra o contenido)
                    correcta = q['correcta']
                    if val == correcta or (val and val.startswith(correcta[0])):
                        st.success("✅ Correcto")
                        score += 1
                    else:
                        st.error(f"❌ Incorrecto. Era: {correcta}")
                st.write("---")
            
            if not st.session_state.get('quiz_submitted', False):
                if st.button("Corregir Todo"): 
                    st.session_state['quiz_submitted'] = True
                    st.rerun()
            else:
                st.metric("Nota Final", f"{score}/{len(st.session_state['quiz_data'])}")

    # 3. FLASHCARDS
    with t3:
        st.header("Tarjetas de Memoria")
        if st.button("⚡ Generar Flashcards"):
            with st.spinner("Sintetizando conceptos..."):
                p = f"""
                Genera 5 flashcards clave.
                FORMATO JSON PURO:
                [
                  {{"pregunta": "Concepto", "respuesta": "Definición breve"}}
                ]
                Texto: {st.session_state['doc_text'][:10000]}
                """
                data = safe_json_parse(ask_gemini(p, valid_model))
                if data:
                    st.session_state['flashcards'] = data
                    st.session_state['fc_idx'] = 0
                    st.rerun()
                else:
                    st.warning("Error de formato IA. Intenta de nuevo.")
        
        if st.session_state['flashcards']:
            i = st.session_state.get('fc_idx', 0)
            if i >= len(st.session_state['flashcards']): i=0
            card = st.session_state['flashcards'][i]
            
            st.markdown(f"**Tarjeta {i+1} / {len(st.session_state['flashcards'])}**")
            with st.container(border=True):
                st.subheader(card['pregunta'])
                if st.checkbox("Mostrar Reverso", key=f"fc{i}"): st.info(card['respuesta'])
            
            c1,c2 = st.columns(2)
            if c1.button("⬅️ Anterior") and i>0: 
                st.session_state['fc_idx'] = i-1
                st.rerun()
            if c2.button("Siguiente ➡️") and i<len(st.session_state['flashcards'])-1: 
                st.session_state['fc_idx'] = i+1
                st.rerun()

    # 4. RECURSOS
    with t4:
        st.header("Recursos Externos")
        if st.button("🔍 Buscar Videos Recomendados"):
            p = f"Lista los 3 conceptos técnicos más difíciles de: {st.session_state['doc_text'][:5000]}. Solo nombres separados por coma."
            res = ask_gemini(p, valid_model)
            if res:
                for c in res.split(","):
                    tag = c.strip()
                    st.markdown(f"**📺 {tag}**")
                    st.markdown(f"[Ver en YouTube](https://www.youtube.com/results?search_query={tag.replace(' ','+')}+tutorial)")

elif not api_key:
    st.warning("👈 Ingresa tu API Key para comenzar.")
elif not selected_file_path:
    st.info("👈 Sube un PDF en la barra lateral.")
