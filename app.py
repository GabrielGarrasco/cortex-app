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
    .exam-box { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 15px; color: #333;}
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE BIBLIOTECA LOCAL ---
LIBRARY_FOLDER = "biblioteca"
if not os.path.exists(LIBRARY_FOLDER):
    os.makedirs(LIBRARY_FOLDER)

def get_library_files():
    return [f for f in os.listdir(LIBRARY_FOLDER) if f.endswith('.pdf')]

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://img.icons8.com/clouds/200/brain.png", width=120)
    st.title("CORTEX v3.3 (Stable)")
    
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ Sistema Online")
    else:
        api_key = st.text_input("🔑 API Key", type="password")
    
    st.divider()

    # Selector de Biblioteca
    st.subheader("📚 Biblioteca")
    mode = st.radio("Acción:", ["📂 Estudiar", "⬆️ Importar"], label_visibility="collapsed")
    
    selected_file_path = None
    
    if mode == "📂 Estudiar":
        files = get_library_files()
        if files:
            selected_file = st.selectbox("Selecciona libro:", files)
            selected_file_path = os.path.join(LIBRARY_FOLDER, selected_file)
        else:
            st.warning("Biblioteca vacía.")
            
    elif mode == "⬆️ Importar":
        uploaded_file = st.file_uploader("PDF", type="pdf", label_visibility="collapsed")
        if uploaded_file:
            save_path = os.path.join(LIBRARY_FOLDER, uploaded_file.name)
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"Guardado: {uploaded_file.name}")
            selected_file_path = save_path
            st.rerun()

    st.divider()
    socratic_mode = st.toggle("🎓 Modo Tutor Socrático", value=False)
    if api_key: genai.configure(api_key=api_key)

# --- FUNCIONES ---
def extract_text(path):
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        return "".join([p.extract_text() for p in reader.pages])

def ask_gemini(prompt):
    # Usamos gemini-1.5-flash que es más rápido y suele fallar menos en JSON
    # Si falla, prueba cambiar a 'gemini-pro'
    model = genai.GenerativeModel('gemini-1.5-flash') 
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return ""

def safe_json_parse(text):
    """
    Versión BLINDADA: Si falla, devuelve una lista vacía en lugar de crashear.
    """
    if not text: return []
    
    try:
        # Intenta encontrar contenido entre corchetes [...]
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        
        # Intenta encontrar contenido entre llaves {...} si es un solo objeto
        match_obj = re.search(r'\{.*\}', text, re.DOTALL)
        if match_obj:
            json_str = match_obj.group(0)
            data = json.loads(json_str)
            if isinstance(data, list): return data
            return [data] # Lo convierte en lista si era un solo objeto
            
    except Exception:
        pass # Si falla cualquier cosa, simplemente no hacemos nada
        
    return [] # Devuelve lista vacía por seguridad

# --- ESTADO ---
if 'messages' not in st.session_state: st.session_state['messages'] = []
if 'quiz_data' not in st.session_state: st.session_state['quiz_data'] = None
if 'doc_text' not in st.session_state: st.session_state['doc_text'] = ""
if 'current_file' not in st.session_state: st.session_state['current_file'] = None
if 'flashcards' not in st.session_state: st.session_state['flashcards'] = []

# --- APP PRINCIPAL ---
if selected_file_path and api_key:
    # Reset si cambia archivo
    if st.session_state['current_file'] != selected_file_path:
        st.session_state['current_file'] = selected_file_path
        st.session_state['doc_text'] = ""
        st.session_state['messages'] = []
        st.session_state['quiz_data'] = None
        st.session_state['flashcards'] = []
        st.rerun()

    if st.session_state['doc_text'] == "":
        with st.spinner("🧠 Cargando en memoria..."):
            st.session_state['doc_text'] = extract_text(selected_file_path)

    # --- PESTAÑAS ---
    t1, t2, t3, t4, t5 = st.tabs(["💬 Chat", "📝 Examen", "📇 Flashcards", "🗺️ Mapa", "▶️ Recursos"])

    # 1. CHAT
    with t1:
        st.header("Tutor Inteligente")
        prompt_sys = "Eres un tutor socrático." if socratic_mode else "Eres un profesor experto."
        
        for m in st.session_state.messages:
            with st.chat_message(m["role"]): st.markdown(m["content"])
            
        if p := st.chat_input("Duda sobre el texto..."):
            st.session_state.messages.append({"role": "user", "content": p})
            with st.chat_message("user"): st.markdown(p)
            with st.chat_message("assistant"):
                full = f"{prompt_sys}\nContexto: {st.session_state['doc_text'][:25000]}\nPregunta: {p}"
                res = ask_gemini(full)
                if res:
                    st.markdown(res)
                    st.session_state.messages.append({"role": "assistant", "content": res})
                else:
                    st.error("Error conectando con la IA. Intenta de nuevo.")

    # 2. EXAMEN
    with t2:
        col_btn, _ = st.columns([1, 4])
        with col_btn:
            if st.button("📝 Generar Examen"):
                with st.spinner("Diseñando preguntas..."):
                    p = f"""
                    Genera 3 preguntas multiple choice JSON:
                    [
                        {{"pregunta": "...", "opciones": ["A) ..", "B) ..", "C) .."], "correcta": "A) .."}}
                    ]
                    Texto: {st.session_state['doc_text'][:15000]}
                    """
                    data = safe_json_parse(ask_gemini(p))
                    if data:
                        st.session_state['quiz_data'] = data
                        st.session_state['quiz_submitted'] = False
                        st.rerun()
                    else:
                        st.warning("La IA no generó el examen correctamente. Por favor intenta de nuevo.")

        if st.session_state['quiz_data']:
            score = 0
            for i, q in enumerate(st.session_state['quiz_data']):
                st.markdown(f"**{i+1}. {q['pregunta']}**")
                val = st.radio(f"Opción:", q['opciones'], key=f"q_{i}", index=None, disabled=st.session_state.get('quiz_submitted', False))
                if st.session_state.get('quiz_submitted', False):
                    if val and val.startswith(q['correcta'][0]):
                         st.success("✅ Correcto")
                         score += 1
                    elif val: st.error(f"❌ Era: {q['correcta']}")
                st.write("---")

            if not st.session_state.get('quiz_submitted', False):
                if st.button("Corregir Examen"):
                    st.session_state['quiz_submitted'] = True
                    st.rerun()
            else:
                st.metric("Nota", f"{(score/len(st.session_state['quiz_data']))*100:.0f}/100")

    # 3. FLASHCARDS
    with t3:
        if st.button("⚡ Crear Flashcards"):
            with st.spinner("Creando..."):
                p = f"""
                Genera 5 flashcards JSON: [{{'pregunta':'...', 'respuesta':'...'}}] 
                Texto: {st.session_state['doc_text'][:15000]}
                """
                data = safe_json_parse(ask_gemini(p))
                if data:
                    st.session_state['flashcards'] = data
                    st.session_state['fc_idx'] = 0
                    st.rerun()
                else:
                    st.warning("Intenta de nuevo, la IA no generó las tarjetas correctamente.")
        
        if st.session_state['flashcards']:
            idx = st.session_state.get('fc_idx', 0)
            if idx >= len(st.session_state['flashcards']): idx = 0
            card = st.session_state['flashcards'][idx]
            
            st.info(f"Tarjeta {idx+1}/{len(st.session_state['flashcards'])}")
            with st.container(border=True):
                st.subheader(card['pregunta'])
                if st.checkbox("Ver respuesta", key=f"f_{idx}"): st.warning(card['respuesta'])
            
            c1,c2 = st.columns(2)
            if c1.button("⬅️") and idx > 0: 
                st.session_state['fc_idx'] = idx - 1
                st.rerun()
            if c2.button("➡️") and idx < len(st.session_state['flashcards']) - 1: 
                st.session_state['fc_idx'] = idx + 1
                st.rerun()

    # 4. MAPA
    with t4:
        if st.button("🗺️ Ver Mapa"):
            with st.spinner("Dibujando..."):
                p = f"Graphviz DOT code simple del texto: {st.session_state['doc_text'][:15000]}"
                res = ask_gemini(p)
                clean_dot = res.replace("```dot", "").replace("```", "").strip()
                if "digraph" in clean_dot:
                    st.graphviz_chart(clean_dot)
                else:
                    st.warning("No se pudo generar el gráfico.")

    # 5. RECURSOS
    with t5:
        if st.button("🔍 Buscar Recursos"):
            p = f"3 conceptos técnicos clave de: {st.session_state['doc_text'][:10000]}. Separados por comas."
            res = ask_gemini(p)
            if res:
                for c in res.split(","):
                    st.markdown(f"### 📺 {c.strip()}")
                    st.markdown(f"[Ver en YouTube](https://www.youtube.com/results?search_query={c.strip().replace(' ', '+')}+tutorial)")

else:
    st.info("👈 Selecciona un PDF para empezar.")
