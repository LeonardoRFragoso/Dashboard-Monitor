import streamlit as st
import requests
from datetime import datetime
import os
import time
from streamlit_autorefresh import st_autorefresh

# Imports adicionais para captura de tela
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Configurações
DEBUG = False
CHECK_MARKER = False  # Se True, verifica se o 'marker' aparece no HTML (em lower-case)
CAPTURE_SCREENSHOT = True  # Se False, não fará a captura de tela

# Configuração da página
st.set_page_config(page_title="Monitor de Aplicações", page_icon="🛰️", layout="wide")
st.markdown("<h1 style='text-align: center;'>Monitor de Aplicações 🛰️</h1>", unsafe_allow_html=True)
st.markdown("---")

services = {
    "Painel Comercial e Financeiro": {
        "url": "http://192.168.0.45:8501/", 
        "marker": "Dashboard Comercial"
    },
    "Painel de Infrações": {
        "url": "http://192.168.0.45:8502/", 
        "marker": "Dashboard de Multas"
    },
    "Painel de Janelas": {
        "url": "http://192.168.0.45:8503/", 
        "marker": "Dashboard de Janelas"
    },
}

# Estado para armazenar horário de "queda" dos serviços
if "downtime" not in st.session_state:
    st.session_state.downtime = {service: None for service in services.keys()}

def capture_screenshot(url):
    """
    Abre o URL em um navegador headless (Chrome) e retorna a imagem em bytes (PNG).
    """
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1280,720")

        service_obj = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service_obj, options=chrome_options)
        
        driver.get(url)
        # Aguarda até 5 segundos para o site carregar completamente
        time.sleep(5)

        screenshot = driver.get_screenshot_as_png()
        driver.quit()
        return screenshot
    except Exception as e:
        if DEBUG:
            st.write(f"DEBUG: Erro ao capturar screenshot de {url}: {e}")
        return None

def check_service(url, marker):
    """
    Verifica se o serviço responde com status 200.
    Se CHECK_MARKER=True, verifica se 'marker.lower()' está em 'response.text.lower()'.
    Retorna (status_boolean, status_code).
    """
    try:
        response = requests.get(url, timeout=5, allow_redirects=True)
        if DEBUG:
            st.write(f"DEBUG: URL: {url} - Status Code: {response.status_code}")
            st.write("DEBUG: Conteúdo (primeiros 500 caracteres):", response.text[:500])
        
        if response.status_code == 200:
            if CHECK_MARKER:
                if marker.lower() in response.text.lower():
                    return True, response.status_code
                else:
                    return False, response.status_code
            else:
                return True, response.status_code
        else:
            return False, response.status_code
    except Exception as e:
        if DEBUG:
            st.write(f"DEBUG: URL: {url} - Erro: {e}")
        return False, None

def read_cron_log(log_path):
    """
    Lê o arquivo de log do cron e extrai os horários de início e fim da última execução.
    O arquivo deve conter linhas iniciadas com "Start:" e "End:".
    Retorna (start_time, end_time) ou None se não achar.
    """
    if not os.path.exists(log_path):
        return None

    with open(log_path, "r") as f:
        lines = f.readlines()

    start_time = None
    end_time = None
    for line in lines:
        if "Start:" in line:
            start_time = line.split("Start:")[1].strip()
        if "End:" in line:
            end_time = line.split("End:")[1].strip()
    if start_time and end_time:
        return start_time, end_time
    return None

# Atualiza a página automaticamente a cada 2 minutos (120000 milissegundos)
st_autorefresh(interval=120000, limit=100, key="monitor")

# Seção: Status dos Dashboards
st.header("Status dos Dashboards")

for name, details in services.items():
    url = details["url"]
    marker = details["marker"]
    
    status, status_code = check_service(url, marker)
    
    if status:
        st.markdown(
            f"""
            <div style='padding:10px; border: 1px solid #d4edda; border-radius: 5px; background-color: #d4edda;'>
                <h3 style='color: green;'>{name} ✅</h3>
                <p><strong>URL:</strong> <a href='{url}' target='_blank'>{url}</a></p>
                <p><strong>Status:</strong> 
                    <span style='font-weight:bold; color:green;'>Disponível (HTTP {status_code})</span>
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Captura de tela, se habilitado
        if CAPTURE_SCREENSHOT:
            screenshot = capture_screenshot(url)
            if screenshot:
                st.image(screenshot, caption=f"Visualização atual de {name}", use_container_width=True)
        
        st.session_state.downtime[name] = None
    else:
        if st.session_state.downtime[name] is None:
            st.session_state.downtime[name] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(
            f"""
            <div style='padding:10px; border: 1px solid #f5c6cb; border-radius: 5px; background-color: #f8d7da;'>
                <h3 style='color: red;'>{name} ❌</h3>
                <p><strong>URL:</strong> <a href='{url}' target='_blank'>{url}</a></p>
                <p><strong>Status:</strong> 
                    <span style='font-weight:bold; color:red;'>Não disponível ou com erro (HTTP {status_code})</span>
                </p>
                <p><strong>Registrado em:</strong> {st.session_state.downtime[name]}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.markdown("<br>", unsafe_allow_html=True)

# Seção: Status da Rotina de Processamento
st.header("Status da Rotina de Processamento")

cron_log_path = "/home/dev/Documentos/Projeto-Comercial/cron_job.log"
cron_status = read_cron_log(cron_log_path)

if cron_status is not None:
    start_time, end_time = cron_status
    try:
        last_start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        time_elapsed = datetime.now() - last_start
        time_elapsed_str = str(time_elapsed).split('.')[0]  # Remove microsegundos
    except Exception as e:
        time_elapsed_str = "Formato de data inválido"
    
    st.markdown(
        f"""
        <div style='padding:10px; border: 1px solid #d4edda; border-radius: 5px; background-color: #d4edda;'>
            <h3 style='color: green;'>Rotina do Projeto Comercial ✅</h3>
            <p><strong>Último Início:</strong> {start_time}</p>
            <p><strong>Último Fim:</strong> {end_time}</p>
            <p><strong>Tempo decorrido desde o início:</strong> {time_elapsed_str}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.markdown(
        """
        <div style='padding:10px; border: 1px solid #f5c6cb; border-radius: 5px; background-color: #f8d7da;'>
            <h3 style='color: red;'>Rotina do Projeto Comercial ❌</h3>
            <p><strong>Aviso:</strong> Não foi possível encontrar informações sobre a última execução da rotina.</p>
            <p>Verifique se o arquivo de log existe e se o formato das linhas está correto (deve conter 'Start:' e 'End:').</p>
        </div>
        """,
        unsafe_allow_html=True
    )
