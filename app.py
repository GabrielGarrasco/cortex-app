import streamlit as st
import google.generativeai as genai
import pdfplumber
import os
import json
import re

# --- CONFIGURACIÓN DE INGENIERÍA ---
st.set_page_config(
    page_title="CORTEX: Engineering OS",
    layout="wide",
    page_icon="⚙️",
    initial_sidebar_state="expanded"
)

# --- CSS PRO PARA LECTURA Y LATEX ---
st.markdown("""
<style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stButton>button { width: 100%; border-radius: 6px; border: 1px solid #30333F; }
    .stButton>button:hover { border-color: #00ADB5; color: #00ADB5; }
    .stChatMessage { background-color: #262730; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
    h1, h2, h3 { color: #00ADB5; }
    /* Ajuste para fórmulas LaTeX */
    .katex { font-size: 1.1em; }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE ESTADO (MEMORIA) ---
if 'messages' not in st.session_state: st.session_state.messages = []
if 'quiz_data' not in st.session_state: st.session_state.quiz_data = []
if 'flashcards' not in st.session_state: st.session_state.flashcards = []
if 'current_file_name' not in st.session_state: st.session_state.current_file_name = None
if 'processed_text' not in st.session_state: st.session_state.processed_text = ""

# --- FUNCIONES NUCLEARES ---

@st.cache_data(show_spinner=False)
def extract_text_from_pdf(file_bytes):
    """Extrae texto preservando estructura básica, mejor que PyPDF2."""
    try:
        text = ""
        with pdfplumber.open(file_bytes) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text
    except Exception as e:
        return f"Error leyendo PDF: {e}"

def get_gemini_response(history, prompt, context, api_key):
    genai.configure(api_key=api_key)
    # Usamos Flash por su enorme ventana de contexto (1M tokens) ideal para libros enteros
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Inyectamos el contexto del PDF en el sistema, no en cada mensaje
    system_instruction = f"""
    Eres CORTEX, un asistente avanzado para estudiantes de ingeniería.
    
    CONTEXTO DEL DOCUMENTO:
    {context}
    
    INSTRUCCIONES:
    1. Responde basándote ESTRICTAMENTE en el documento.
    2. Usa LaTeX para todas las fórmulas matemáticas. Enciérralas en signos de dólar ($ formula $).
    3. Sé preciso, técnico y directo. Si hay pasos de cálculo, muéstralos.
    """
    
    chat = model.start_chat(history=history)
    response = chat.send_message(f"Instrucción del sistema: {system_instruction}\n\nUsuario: {prompt}")
    return response.text

def generate_structure_json(prompt, context, api_key):
    """Genera JSON (Quiz/Flashcards) forzando estructura."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    full_prompt = f"""
    Actúa como un profesor de ingeniería. Basado en este texto:
    {context[:100000]}... (Texto truncado para eficiencia en generación JSON)
    
    {prompt}
    
    IMPORTANTE: Responde SOLAMENTE con un JSON válido. Sin markdown, sin ```json```, solo el array puro.
    """
    try:
        response = model.generate_content(full_prompt)
        # Limpieza agresiva del JSON
        text = response.text.strip()
        text = re.sub(r"```json|```", "", text)
        return json.loads(text)
    except Exception as e:
        st.error(f"Error generando estructura: {e}")
        return []

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://img.icons8.com/nolan/96/artificial-intelligence.png", width=80)
    st.title("CORTEX Eng.")
    
    api_key = st.text_input("🔑 Google API Key", type="password")
    
    st.divider()
    
    uploaded_file = st.file_uploader("Cargar Material (PDF)", type="pdf")
    
    if uploaded_file:
        if st.session_state.current_file_name != uploaded_file.name:
            with st.spinner("⚙️ Procesando estructura del PDF..."):
                # Procesa y guarda en caché
                text = extract_text_from_pdf(uploaded_file)
                st.session_state.processed_text = text
                st.session_state.current_file_name = uploaded_file.name
                # Resetear estados al cambiar archivo
                st.session_state.messages = []
                st.session_state.quiz_data = []
                st.session_state.flashcards = []
            st.success("PDF Indexado en RAM")

    st.info(f"Tokens aprox: {len(st.session_state.processed_text)//4}")
    
    if st.button("🗑️ Limpiar Historial"):
        st.session_state.messages = []
        st.rerun()

# --- INTERFAZ PRINCIPAL ---

if not api_key:
    st.warning("⚠️ Por favor ingresa tu API Key para activar los núcleos de IA.")
    st.stop()

if not st.session_state.processed_text:
    st.info("👈 Sube un documento técnico para comenzar el análisis.")
    st.stop()

# PESTAÑAS
tab_chat, tab_quiz, tab_flash = st.tabs(["💬 Chat Técnico", "📝 Examen", "⚡ Flashcards"])

# --- 1. CHAT TÉCNICO ---
with tab_chat:
    st.markdown("### Discusión con el Documento")
    
    # Historial visual
    for message in st.session_state.messages:
        role = "user" if message["role"] == "user" else "assistant"
        avatar = "🧑‍💻" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # Input usuario
    if prompt := st.chat_input("Pregunta sobre fórmulas, conceptos o problemas..."):
        # 1. Agregar usuario al historial
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)

        # 2. Generar respuesta
        with st.chat_message("assistant", avatar="🤖"):
            message_placeholder = st.empty()
            with st.spinner("Analizando vectores..."):
                # Convertir historial al formato Gemini
                gemini_history = [
                    {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                    for m in st.session_state.messages[:-1] # Excluir el último actual
                ]
                
                try:
                    full_response = get_gemini_response(
                        gemini_history, 
                        prompt, 
                        st.session_state.processed_text, 
                        api_key
                    )
                    message_placeholder.markdown(full_response)
                    # 3. Guardar respuesta
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    message_placeholder.error(f"Error de conexión: {e}")

# --- 2. EXAMEN (QUIZ) ---
with tab_quiz:
    c1, c2 = st.columns([1, 4])
    with c1:
        num_q = st.number_input("Preguntas", 3, 10, 5)
    with c2:
        if st.button("Generar Examen Nuevo", type="primary"):
            with st.spinner("Diseñando problemas..."):
                prompt_quiz = f"""
                Genera {num_q} preguntas de selección múltiple nivel ingeniería.
                Formato JSON: [
                    {{"pregunta": "...", "opciones": ["A) ...", "B) ..."], "correcta": "A) ..."}},
                    ...
                ]
                """
                st.session_state.quiz_data = generate_structure_json(prompt_quiz, st.session_state.processed_text, api_key)
    
    if st.session_state.quiz_data:
        # Usamos st.form para evitar recargas constantes al seleccionar
        with st.form("quiz_form"):
            score = 0
            user_answers = {}
            
            for i, q in enumerate(st.session_state.quiz_data):
                st.markdown(f"**{i+1}. {q['pregunta']}**")
                user_answers[i] = st.radio(
                    "Selecciona:", 
                    q['opciones'], 
                    key=f"q_{i}", 
                    label_visibility="collapsed"
                )
                st.divider()
            
            submitted = st.form_submit_button("Evaluar Respuestas")
            
            if submitted:
                st.success("Resultados:")
                for i, q in enumerate(st.session_state.quiz_data):
                    ans = user_answers[i]
                    correct = q['correcta']
                    
                    # Lógica simple de comparación (primer caracter A, B, C...)
                    if ans.split(")")[0] == correct.split(")")[0]:
                        st.markdown(f"✅ **P{i+1}:** Correcto")
                        score += 1
                    else:
                        st.markdown(f"❌ **P{i+1}:** Incorrecto. Respuesta correcta: *{correct}*")
                
                st.progress(score / len(st.session_state.quiz_data))
                st.metric("Calificación Final", f"{score}/{len(st.session_state.quiz_data)}")

# --- 3. FLASHCARDS ---
with tab_flash:
    if st.button("Generar Flashcards de Conceptos Clave"):
        with st.spinner("Sintetizando..."):
            prompt_fc = """
            Genera 10 flashcards de conceptos difíciles o fórmulas.
            Formato JSON: [{"front": "Término/Fórmula", "back": "Definición/Explicación"}]
            """
            st.session_state.flashcards = generate_structure_json(prompt_fc, st.session_state.processed_text, api_key)

    if st.session_state.flashcards:
        # Control de índice manual
        if "fc_index" not in st.session_state: st.session_state.fc_index = 0
        
        idx = st.session_state.fc_index
        card = st.session_state.flashcards[idx]
        
        st.progress((idx + 1) / len(st.session_state.flashcards))
        
        # Diseño de tarjeta
        with st.container():
            st.markdown(f"""
            <div style="background-color: #30333F; padding: 20px; border-radius: 10px; text-align: center; min-height: 200px; display: flex; align-items: center; justify-content: center;">
                <h2>{card['front']}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # Espaciador
            st.write("")
            
            with st.expander("👁️ Ver Respuesta"):
                st.markdown(f"### {card['back']}")
                
        # Navegación
        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.button("⬅️ Anterior") and idx > 0:
                st.session_state.fc_index -= 1
                st.rerun()
        with col_next:
            if st.button("Siguiente ➡️") and idx < len(st.session_state.flashcards) - 1:
                st.session_state.fc_index += 1
                st.rerun()
