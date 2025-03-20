import streamlit as st
import requests
from datetime import datetime, timezone
import time
from streamlit_autorefresh import st_autorefresh

# Imports para captura de tela com Selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Imports para integração com o Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
import dateutil.parser

import logging

# =====================================================================
# Configurações Gerais
# =====================================================================

DEBUG = False
CHECK_MARKER = False       # Se True, verifica se o 'marker' aparece no HTML (em lower-case)
CAPTURE_SCREENSHOT = True  # Se False, não fará a captura de tela

# Caminho do arquivo de credenciais original e do extra
CREDENTIALS_FILE = "/home/dev/Documentos/Dashboard-Monitor/gdrive_credentials.json"
EXTRA_CREDENTIALS_FILE = r"C:\Users\leonardo.fragoso\Desktop\Projetos\Dash-ControleAplicações\service_account.json"

# Configuração da página do Streamlit com ícone de satélite
st.set_page_config(page_title="Monitor de Aplicações", page_icon="🛰️", layout="wide")
st.markdown("<h1 style='text-align: center;'>Monitor de Aplicações 🛰️</h1>", unsafe_allow_html=True)
st.markdown("---")

# Dicionário de serviços a serem monitorados (Dashboards)
services = {
    "Painel Comercial": {
        "url": "http://192.168.0.45:8501/", 
        "marker": "Dashboard Comercial"
    },
    "Painel de Multas": {
        "url": "http://192.168.0.45:8502/", 
        "marker": "Dashboard de Multas"
    },
    "Painel de Janelas": {
        "url": "http://192.168.0.45:8503/", 
        "marker": "Dashboard de Janelas"
    },
}

# Dicionário com IDs dos arquivos (planilhas) no Google Drive para a rotina original
spreadsheet_files = {
    "Planilha 1 - data.xlsx": "1fMeKSdRvZod7FkvWLKXwsZV32W6iSmbI",
    "Planilha 2 - janelas_multirio_corrigido.xlsx": "1gzqhOADx-VJstLHvM7VVm3iuGUuz3Vgu"
}

# Dicionário com as planilhas para a rotina extra (atualizadas a partir da execução às 6h)
extra_spreadsheets = {
    "Exportação.xlsx": "1wijOMirmPmhCl72xzd5HjKUfAOgX0eJd",
    "Importação.xlsx": "1Iy-kkW7uvcFEKJ3i_UBbCnFyUqa0su2G",
    "Cabotagem.xlsx": "1kvjmYigg06aEOrgFG4gRFwzCIjTrns2P"
}

# Estado para armazenar o horário de "queda" dos serviços
if "downtime" not in st.session_state:
    st.session_state.downtime = {service: None for service in services.keys()}

# Configuração do logging
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO)

# =====================================================================
# Funções Auxiliares
# =====================================================================

def capturar_screenshot(url: str, marker: str = None) -> bytes:
    """
    Abre o URL em um navegador headless (Chrome) e retorna a imagem em bytes (PNG).

    Parâmetros:
        url (str): URL da página a ser capturada.
        marker (str, opcional): Texto que deve estar presente na página para indicar que ela foi carregada.
    
    Retorna:
        bytes ou None: Imagem em formato PNG ou None em caso de erro.
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
        # Espera explícita: aguarda que o documento esteja completamente carregado (até 30 segundos)
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        # Se um marker foi informado, aguarda até que ele esteja presente na página
        if marker:
            WebDriverWait(driver, 30).until(
                lambda d: marker.lower() in d.page_source.lower()
            )
        
        screenshot = driver.get_screenshot_as_png()
        driver.quit()
        return screenshot
    except Exception as e:
        if DEBUG:
            st.write(f"DEBUG: Erro ao capturar screenshot de {url}: {e}")
        logging.exception("Erro ao capturar screenshot")
        return None

def verificar_status_servico(url: str, marker: str) -> (bool, int):
    """
    Verifica se o serviço responde com status 200.
    Se CHECK_MARKER=True, verifica se 'marker.lower()' está em 'response.text.lower()'.

    Parâmetros:
        url (str): URL do serviço.
        marker (str): Texto que deve estar presente no conteúdo do serviço, se CHECK_MARKER for True.
    
    Retorna:
        tuple(bool, int): (status, status_code)
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
        logging.exception("Erro ao verificar status do serviço")
        return False, None

def renderizar_status_card(name: str, url: str, status: bool, status_code: int, downtime: str = None) -> None:
    """
    Renderiza um cartão de status utilizando markdown.

    Parâmetros:
        name (str): Nome do serviço.
        url (str): URL do serviço.
        status (bool): True se disponível, False se não.
        status_code (int): Código HTTP retornado.
        downtime (str): Timestamp de quando o serviço ficou indisponível.
    """
    if status:
        card_html = f"""
            <div style='padding:10px; border: 1px solid #d4edda; border-radius: 5px; background-color: #d4edda;'>
                <h3 style='color: green;'>{name} ✅</h3>
                <p><strong>URL:</strong> <a href='{url}' target='_blank'>{url}</a></p>
                <p><strong>Status:</strong> 
                    <span style='font-weight:bold; color:green;'>Disponível (HTTP {status_code})</span>
                </p>
            </div>
        """
    else:
        card_html = f"""
            <div style='padding:10px; border: 1px solid #f5c6cb; border-radius: 5px; background-color: #f8d7da;'>
                <h3 style='color: red;'>{name} ❌</h3>
                <p><strong>URL:</strong> <a href='{url}' target='_blank'>{url}</a></p>
                <p><strong>Status:</strong> 
                    <span style='font-weight:bold; color:red;'>Não disponível ou com erro (HTTP {status_code})</span>
                </p>
                <p><strong>Registrado em:</strong> {downtime}</p>
            </div>
        """
    st.markdown(card_html, unsafe_allow_html=True)

# =====================================================================
# Funções Principais
# =====================================================================

def monitorar_servicos() -> None:
    """
    Monitora os serviços definidos no dicionário 'services' e exibe o status na interface do Streamlit.
    """
    st.header("Status dos Dashboards")
    for name, details in services.items():
        url = details["url"]
        marker = details["marker"]
        
        status, status_code = verificar_status_servico(url, marker)
        
        if status:
            # Reseta o downtime se o serviço estiver disponível
            st.session_state.downtime[name] = None
            renderizar_status_card(name, url, status, status_code)
            
            # Captura de tela, aguardando que o marcador esteja presente
            if CAPTURE_SCREENSHOT:
                screenshot = capturar_screenshot(url, marker)
                if screenshot:
                    st.image(screenshot, caption=f"Visualização atual de {name}", use_container_width=True)
        else:
            if st.session_state.downtime[name] is None:
                st.session_state.downtime[name] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            renderizar_status_card(name, url, status, status_code, downtime=st.session_state.downtime[name])
        st.markdown("<br>", unsafe_allow_html=True)

def verificar_rotina_processamento() -> None:
    """
    Verifica o status da rotina de processamento baseada na atualização dos arquivos do Google Drive
    (rotina original) e exibe o status na interface do Streamlit.
    """
    st.header("Status da Rotina de Processamento")
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/drive.metadata.readonly']
        )
        drive_service = build('drive', 'v3', credentials=creds)

        operational = True
        messages = []

        for name, file_id in spreadsheet_files.items():
            file_metadata = drive_service.files().get(fileId=file_id, fields="modifiedTime").execute()
            modified_time_str = file_metadata.get("modifiedTime")
            modified_time = dateutil.parser.isoparse(modified_time_str)
            time_diff = (datetime.now(timezone.utc) - modified_time).total_seconds()

            if time_diff <= 300:
                messages.append(f"{name} foi atualizado há menos de 5 minutos.")
            else:
                messages.append(f"{name} não foi atualizado nos últimos 5 minutos.")
                operational = False

        if operational:
            card_html = f"""
            <div style='padding:10px; border: 1px solid #d4edda; border-radius: 5px; background-color: #d4edda;'>
                <h3 style='color: green;'>Rotina de Processamento Operante ✅</h3>
                {''.join([f"<p>{msg}</p>" for msg in messages])}
            </div>
            """
        else:
            card_html = f"""
            <div style='padding:10px; border: 1px solid #f5c6cb; border-radius: 5px; background-color: #f8d7da;'>
                <h3 style='color: red;'>Rotina de Processamento NÃO Operante ❌</h3>
                {''.join([f"<p>{msg}</p>" for msg in messages])}
            </div>
            """
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e:
        error_html = f"""
        <div style='padding:10px; border: 1px solid #f5c6cb; border-radius: 5px; background-color: #f8d7da;'>
            <h3 style='color: red;'>Erro ao verificar a Rotina de Processamento ❌</h3>
            <p>{str(e)}</p>
        </div>
        """
        st.markdown(error_html, unsafe_allow_html=True)
        logging.exception("Erro ao verificar rotina de processamento")

def verificar_rotina_processamento_extra() -> None:
    """
    Verifica se a execução que começou às 6h de cada dia atualizou corretamente as planilhas
    (Exportação.xlsx, Importação.xlsx e Cabotagem.xlsx) utilizando as credenciais extra.
    Para cada planilha, o horário de modificação deve ser igual ou posterior a 6h do dia corrente.
    """
    st.header("Status da Rotina de Processamento - Extra")
    try:
        extra_creds = service_account.Credentials.from_service_account_file(
            EXTRA_CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/drive.metadata.readonly']
        )
        extra_drive_service = build('drive', 'v3', credentials=extra_creds)

        operational = True
        messages = []

        for name, file_id in extra_spreadsheets.items():
            file_metadata = extra_drive_service.files().get(fileId=file_id, fields="modifiedTime").execute()
            modified_time_str = file_metadata.get("modifiedTime")
            modified_time = dateutil.parser.isoparse(modified_time_str)
            # Calcula as 6h do dia corrente na mesma timezone do modified_time
            today_6am = datetime.now(modified_time.tzinfo).replace(hour=6, minute=0, second=0, microsecond=0)
            
            if modified_time >= today_6am:
                messages.append(f"{name} foi atualizado após as 6h.")
            else:
                messages.append(f"{name} NÃO foi atualizado após as 6h.")
                operational = False

        if operational:
            card_html = f"""
            <div style='padding:10px; border: 1px solid #d4edda; border-radius: 5px; background-color: #d4edda;'>
                <h3 style='color: green;'>Rotina de Processamento Extra Operante ✅</h3>
                {''.join([f"<p>{msg}</p>" for msg in messages])}
            </div>
            """
        else:
            card_html = f"""
            <div style='padding:10px; border: 1px solid #f5c6cb; border-radius: 5px; background-color: #f8d7da;'>
                <h3 style='color: red;'>Rotina de Processamento Extra NÃO Operante ❌</h3>
                {''.join([f"<p>{msg}</p>" for msg in messages])}
            </div>
            """
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e:
        error_html = f"""
        <div style='padding:10px; border: 1px solid #f5c6cb; border-radius: 5px; background-color: #f8d7da;'>
            <h3 style='color: red;'>Erro ao verificar a Rotina de Processamento Extra ❌</h3>
            <p>{str(e)}</p>
        </div>
        """
        st.markdown(error_html, unsafe_allow_html=True)
        logging.exception("Erro ao verificar rotina de processamento extra")

def main():
    """
    Função principal que orquestra o monitoramento dos serviços e a verificação das rotinas de processamento.
    """
    st_autorefresh(interval=120000, limit=100, key="monitor")
    monitorar_servicos()
    verificar_rotina_processamento()
    verificar_rotina_processamento_extra()

if __name__ == "__main__":
    main()
