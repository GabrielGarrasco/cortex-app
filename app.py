import streamlit as st
import google.generativeai as genai
import PyPDF2
from io import BytesIO
import json
import os
import re  # <--- IMPORTANTE: Necesario para que no falle el JSON
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
    st.title("CORTEX v3.2")
    st.caption("Sistema Blindado")
    
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
    # Usamos gemini-pro que es el más estable
    model = genai.GenerativeModel('gemini-pro') 
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "" # Devuelve vacío si falla para no romper el JSON

def safe_json_parse(text):
    """
    Intenta encontrar y limpiar JSON dentro de la respuesta de la IA.
    Evita el error 'JSONDecodeError'.
    """
    if not text: return None
    try:
        # 1. Buscar el primer corchete '[' y el último ']'
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        else:
            # Si no encuentra corchetes, intenta limpiar markdown básico
            cleaned = text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
    except Exception as e:
        return None # Indica que falló la conversión sin explotar

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
        prompt_sys = "Eres un tutor socrático. Ayuda a pensar, no des la respuesta directa." if socratic_mode else "Eres un profesor experto, claro y conciso."
        
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
                    st.error("Error de conexión con la IA. Verifica tu API Key o intenta más tarde.")

    # 2. EXAMEN
    with t2:
        st.header("Simulacro de Examen")
        col_btn, col_res = st.columns([1, 4])
        
        with col_btn:
            if st.button("📝 Generar Examen"):
                with st.spinner("Diseñando preguntas..."):
                    p = f"""
                    Crea 3 preguntas de opción múltiple (A, B, C) sobre el texto.
                    Devuelve SOLO una lista JSON válida. Sin texto extra.
                    Formato:
                    [
                        {{"pregunta": "...", "opciones": ["A) ..", "B) ..", "C) .."], "correcta": "A) .."}},
                        ...
                    ]
                    Texto: {st.session_state['doc_text'][:15000]}
                    """
                    response_text = ask_gemini(p)
                    data = safe_json_parse(response_text)
                    
                    if data:
                        st.session_state['quiz_data'] = data
                        st.session_state['quiz_submitted'] = False
                        st.rerun()
                    else:
                        st.error("La IA no pudo generar el formato correcto. Intenta de nuevo.")

        if st.session_state['quiz_data']:
            score = 0
            for i, q in enumerate(st.session_state['quiz_data']):
                st.markdown(f"**{i+1}. {q['pregunta']}**")
                val = st.radio(f"Opciones {i}", q['opciones'], key=f"q_{i}", index=None, disabled=st.session_state.get('quiz_submitted', False))
                
                if st.session_state.get('quiz_submitted', False):
                    if val and val.startswith(q['correcta'][0]):
                         st.success(f"✅ Correcto!")
                         score += 1
                    elif val == q['correcta']:
                         st.success(f"✅ Correcto!")
                         score += 1
                    else:
                        st.error(f"❌ La correcta era: {q['correcta']}")
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
            with st.spinner("Generando tarjetas..."):
                p = f"""
                Genera 5 flashcards sobre conceptos clave del texto.
                Devuelve SOLO una lista JSON válida.
                Formato: [{{'pregunta':'...', 'respuesta':'...'}}] 
                Texto: {st.session_state['doc_text'][:15000]}
                """
                response_text = ask_gemini(p)
                data = safe_json_parse(response_text)
                
                if data:
                    st.session_state['flashcards'] = data
                    st.session_state['fc_idx'] = 0
                    st.rerun()
                else:
                    st.error("Error al generar formato JSON. Prueba otra vez.")
        
        if st.session_state['flashcards']:
            idx = st.session_state.get('fc_idx', 0)
            if idx >= len(st.session_state['flashcards']): idx = 0
            
            card = st.session_state['flashcards'][idx]
            st.info(f"Tarjeta {idx+1} de {len(st.session_state['flashcards'])}")
            
            with st.container(border=True):
                st.subheader(card['pregunta'])
                if st.checkbox("Mostrar respuesta", key=f"f_{idx}"): 
                    st.warning(card['respuesta'])
            
            c1,c2 = st.columns(2)
            if c1.button("⬅️ Anterior") and idx > 0: 
                st.session_state['fc_idx'] = idx - 1
                st.rerun()
            if c2.button("Siguiente ➡️") and idx < len(st.session_state['flashcards']) - 1: 
                st.session_state['fc_idx'] = idx + 1
                st.rerun()

    # 4. MAPA
    with t4:
        if st.button("🗺️ Ver Estructura"):
            with st.spinner("Analizando..."):
                p = f"Genera código Graphviz DOT simple para un mapa mental de: {st.session_state['doc_text'][:15000]}. Devuelve SOLO el código dentro de las llaves."
                res = ask_gemini(p)
                clean_dot = res.replace("```dot", "").replace("```", "").strip()
                try:
                    st.graphviz_chart(clean_dot)
                except:
                    st.error("No se pudo visualizar el gráfico. Intenta de nuevo.")

    # 5. RECURSOS
    with t5:
        st.header("Expandir Conocimiento")
        if st.button("🔍 Analizar Conceptos Clave"):
            with st.spinner("Buscando conceptos..."):
                p = f"""
                Identifica los 3 términos técnicos más importantes de este texto.
                Devuélvelos separados solo por comas.
                Texto: {st.session_state['doc_text'][:10000]}
                """
                res = ask_gemini(p)
                if res:
                    conceptos = res.split(",")
                    for concepto in conceptos:
                        clean_c = concepto.strip()
                        if clean_c:
                            st.markdown(f"### 📺 {clean_c}")
                            yt_url = f"https://www.youtube.com/results?search_query={clean_c.replace(' ', '+')}+curso"
                            st.markdown(f"[Buscar tutoriales en YouTube]({yt_url})")

else:
    st.info("👈 Selecciona un documento para empezar.")
