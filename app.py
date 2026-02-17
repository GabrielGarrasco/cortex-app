import streamlit as st
import google.generativeai as genai
import PyPDF2
from io import BytesIO
import json
import os
import time
from gtts import gTTS

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="CORTEX: Study OS",
    layout="wide",
    page_icon="🧠",
    initial_sidebar_state="expanded"
)

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold;}
    .exam-box { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #ddd; margin-bottom: 15px; color: #333;}
    .stProgress > div > div > div > div { background-color: #4CAF50; }
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
    st.title("CORTEX v3.0")
    st.caption("Sistema Operativo de Estudio")
    
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

def clean_json(text):
    return text.replace("```json", "").replace("```", "").strip()

def ask_gemini(prompt):
    # CAMBIO IMPORTANTE: Usamos 'gemini-pro' que es el modelo más compatible
    model = genai.GenerativeModel('gemini-pro') 
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        # Esto evitará que la app se rompa si hay un error, mostrando un mensaje
        return f"Error de IA: {str(e)}"

# --- ESTADO ---
if 'messages' not in st.session_state: st.session_state['messages'] = []
if 'quiz_data' not in st.session_state: st.session_state['quiz_data'] = None
if 'doc_text' not in st.session_state: st.session_state['doc_text'] = ""
if 'current_file' not in st.session_state: st.session_state['current_file'] = None

# --- APP PRINCIPAL ---
if selected_file_path and api_key:
    # Reset si cambia archivo
    if st.session_state['current_file'] != selected_file_path:
        st.session_state['current_file'] = selected_file_path
        st.session_state['doc_text'] = ""
        st.session_state['messages'] = []
        st.session_state['quiz_data'] = None
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
                st.markdown(res)
                st.session_state.messages.append({"role": "assistant", "content": res})

    # 2. EXAMEN (NUEVO)
    with t2:
        st.header("Simulacro de Examen")
        col_btn, col_res = st.columns([1, 4])
        
        with col_btn:
            if st.button("📝 Generar Examen"):
                with st.spinner("Diseñando preguntas..."):
                    p = f"""
                    Genera 3 preguntas de selección múltiple sobre el texto.
                    Formato JSON estricto:
                    [
                        {{"pregunta": "...", "opciones": ["A) ..", "B) ..", "C) .."], "correcta": "A) .."}},
                        ...
                    ]
                    Texto: {st.session_state['doc_text'][:15000]}
                    """
                    try:
                        q_text = ask_gemini(p)
                        st.session_state['quiz_data'] = json.loads(clean_json(q_text))
                        # Inicializar respuestas del usuario
                        st.session_state['user_answers'] = [None] * len(st.session_state['quiz_data'])
                        st.session_state['quiz_submitted'] = False
                        st.rerun()
                    except: st.error("Error generando examen.")

        if st.session_state['quiz_data']:
            score = 0
            for i, q in enumerate(st.session_state['quiz_data']):
                st.markdown(f"**{i+1}. {q['pregunta']}**")
                
                # Widget de radio buttons
                # Usamos key única por pregunta y deshabilitamos si ya se envió
                val = st.radio(f"Opciones {i}", q['opciones'], key=f"q_{i}", index=None, disabled=st.session_state.get('quiz_submitted', False))
                
                # Si se envió, mostrar corrección
                if st.session_state.get('quiz_submitted', False):
                    if val == q['correcta']:
                        st.success(f"✅ Correcto! ({val})")
                        score += 1
                    else:
                        st.error(f"❌ Incorrecto. Era: {q['correcta']}")
                st.write("---")

            if not st.session_state.get('quiz_submitted', False):
                if st.button("Corregir Examen"):
                    st.session_state['quiz_submitted'] = True
                    st.rerun()
            else:
                final_score = (score / len(st.session_state['quiz_data'])) * 100
                st.metric("Calificación Final", f"{final_score:.0f}/100")
                if final_score == 100: st.balloons()

    # 3. FLASHCARDS
    with t3:
        if st.button("⚡ Crear Flashcards"):
            p = f"5 flashcards JSON [{{'pregunta':'...', 'respuesta':'...'}}] de: {st.session_state['doc_text'][:15000]}"
            st.session_state['flashcards'] = json.loads(clean_json(ask_gemini(p)))
        
        if 'flashcards' in st.session_state and st.session_state['flashcards']:
            idx = st.session_state.get('fc_idx', 0)
            card = st.session_state['flashcards'][idx]
            st.info(f"Tarjeta {idx+1}")
            with st.container(border=True):
                st.subheader(card['pregunta'])
                if st.checkbox("Ver respuesta", key=f"f_{idx}"): st.warning(card['respuesta'])
            c1,c2 = st.columns(2)
            if c1.button("Prev") and idx>0: 
                st.session_state['fc_idx'] = idx-1
                st.rerun()
            if c2.button("Next") and idx<len(st.session_state['flashcards'])-1: 
                st.session_state['fc_idx'] = idx+1
                st.rerun()

    # 4. MAPA
    with t4:
        if st.button("🗺️ Ver Estructura"):
            p = f"Graphviz DOT code simple del texto: {st.session_state['doc_text'][:15000]}"
            st.graphviz_chart(clean_json(ask_gemini(p)))

    # 5. RECURSOS (NUEVO)
    with t5:
        st.header("Expandir Conocimiento")
        st.write("La IA busca los mejores términos para complementar este PDF en YouTube.")
        if st.button("🔍 Analizar Conceptos Clave"):
            with st.spinner("Buscando conceptos..."):
                p = f"""
                Dime los 3 conceptos técnicos MÁS difíciles o importantes de este texto.
                Solo dame los nombres, separados por comas.
                Texto: {st.session_state['doc_text'][:10000]}
                """
                conceptos = ask_gemini(p).split(",")
                
                for concepto in conceptos:
                    clean_c = concepto.strip()
                    st.markdown(f"### 📺 {clean_c}")
                    # Generar link de búsqueda de YouTube
                    yt_url = f"https://www.youtube.com/results?search_query={clean_c.replace(' ', '+')}+tutorial"
                    st.markdown(f"[Ver videos relacionados en YouTube]({yt_url})")

else:
    st.info("👈 Selecciona un documento para empezar.")
