import streamlit as st
import requests
from datetime import datetime, timezone, timedelta
import time
import pytz
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
import pandas as pd
import base64
from io import BytesIO

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

# Timezone local para Brasil
BR_TZ = pytz.timezone('America/Sao_Paulo')

# Caminho do arquivo de credenciais original e do extra
CREDENTIALS_FILE = r"C:\Users\leonardo.fragoso\Desktop\Projetos\Dash-ControleAplicações\gdrive_credentials.json"
EXTRA_CREDENTIALS_FILE = r"C:\Users\leonardo.fragoso\Desktop\Projetos\Dash-ControleAplicações\service_account.json"

# Configuração da página do Streamlit com tema e layout aprimorado
st.set_page_config(
    page_title="Torre de Controle - Monitor de Aplicações", 
    page_icon="🛰️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aplicando CSS personalizado para melhorar a aparência
st.markdown("""
<style>
    .main {
        background-color: #f5f7fa;
    }
    .stApp {
        max-width: auto;
        margin: 0 auto;
    }
    h1, h2, h3 {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .status-card {
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s;
        margin-bottom: 1rem;
    }
    .status-card:hover {
        transform: translateY(-5px);
    }
    .header-container {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 20px;
    }
    .header-logo {
        height: 60px;
        margin-right: 15px;
    }
    .refresh-info {
        font-size: 12px;
        color: #666;
        text-align: center;
        margin-top: -15px;
        margin-bottom: 20px;
    }
    .divider {
        border: 1px solid #e0e0e0;
        margin: 25px 0;
        border-radius: 5px;
    }
    .footer {
        text-align: center;
        padding: 20px;
        font-size: 12px;
        color: #666;
        margin-top: 30px;
    }
    .success-pulse {
        animation: pulse-green 2s infinite;
    }
    .error-pulse {
        animation: pulse-red 2s infinite;
    }
    @keyframes pulse-green {
        0% {
            box-shadow: 0 0 0 0 rgba(0, 128, 0, 0.4);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(0, 128, 0, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(0, 128, 0, 0);
        }
    }
    @keyframes pulse-red {
        0% {
            box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(255, 0, 0, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(255, 0, 0, 0);
        }
    }
    .metric-container {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: center;
    }
    .metric-title {
        font-size: 14px;
        color: #555;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
    }
    .good {
        color: #28a745;
    }
    .warning {
        color: #ffc107;
    }
    .bad {
        color: #dc3545;
    }
    .tab-content {
        padding: 20px;
        border: 1px solid #e0e0e0;
        border-radius: 0 0 10px 10px;
        background-color: white;
    }
</style>
""", unsafe_allow_html=True)

# Cabeçalho com logo e título
st.markdown("""
    <style>
        .titulo-dashboard-container {
            position: relative;
            padding: 35px 30px;
            border-radius: 15px;
            background: linear-gradient(to right, #F37021, #ffffff);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            text-align: center;
        }

        .titulo-dashboard {
            font-size: 38px;
            font-weight: 800;
            color: #212529;
            margin: 0;
        }

        .subtitulo-dashboard {
            position: absolute;
            bottom: 15px;
            right: 30px;
            font-size: 13px;
            font-style: italic;
            font-weight: 400;
            color: #8A8A8A;
            margin: 0;
        }

        @media (max-width: 768px) {
            .titulo-dashboard {
                font-size: 28px;
            }

            .subtitulo-dashboard {
                position: static;
                margin-top: 10px;
                text-align: center;
                display: block;
            }

            .titulo-dashboard-container {
                padding-bottom: 50px;
            }
        }
    </style>

    <div class="titulo-dashboard-container">
        <h1 class="titulo-dashboard">Torre de Controle - Monitor de Aplicações</h1>
        <p class="subtitulo-dashboard">Monitoramento em tempo real dos serviços e rotinas</p>
    </div>
    <hr style="border-top: 3px solid #F37021; margin: 20px 0;">
""", unsafe_allow_html=True)


# Dicionário de serviços a serem monitorados (Dashboards)
services = {
    "Painel Comercial": {
        "url": "http://192.168.0.45:8501/", 
        "marker": "Dashboard Comercial",
        "description": "Dashboard com indicadores de vendas e performance comercial"
    },
    "Painel de Multas": {
        "url": "http://192.168.0.45:8502/", 
        "marker": "Dashboard de Multas",
        "description": "Dashboard para gestão e acompanhamento de multas"
    },
    "Painel de Janelas": {
        "url": "http://192.168.0.45:8503/", 
        "marker": "Dashboard de Janelas",
        "description": "Dashboard para monitoramento de janelas de operação"
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

# Dicionário com as planilhas para a nova rotina dos DETRAN (semanais - dados com menos de 7 dias)
weekly_spreadsheets = {
    "Detran-RJ": "1vrpJmvfOviNeE1yTMv4ikdcOPceGidYg",
    "Detran-SP": "18ZacAr6WI7pfXrQ8AIVFfiJUuNl0UPwY",
    "Detran-ES": "1xPTVAHv80Pe0lD-8yPWgRm9yblN7s39I"
}

# Estado para armazenar o horário de "queda" dos serviços e histórico de status
if "downtime" not in st.session_state:
    st.session_state.downtime = {service: None for service in services.keys()}

if "history" not in st.session_state:
    st.session_state.history = {service: [] for service in services.keys()}

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now(BR_TZ)

if "service_uptime" not in st.session_state:
    st.session_state.service_uptime = {service: 100.0 for service in services.keys()}

if "rotina_status" not in st.session_state:
    st.session_state.rotina_status = {
        "janelas": {"status": None, "messages": []},
        "logcomex": {"status": None, "messages": []},
        "detran": {"status": None, "messages": []}
    }

# Configuração do logging com rotação de arquivos
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("monitor_dashboard.log"),
        logging.StreamHandler()
    ]
)

# =====================================================================
# Funções Auxiliares
# =====================================================================

def get_uptime_color(uptime_percentage):
    """Retorna a cor com base na porcentagem de uptime"""
    if uptime_percentage >= 98:
        return "good"
    elif uptime_percentage >= 90:
        return "warning"
    else:
        return "bad"

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
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: marker.lower() in d.page_source.lower()
                )
            except:
                logging.warning(f"Marker '{marker}' não encontrado no conteúdo da página {url}")
        
        # Aguarda um pouco mais para garantir que tudo está carregado
        time.sleep(2)
        
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
        response = requests.get(url, timeout=10, allow_redirects=True)
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
        logging.exception(f"Erro ao verificar status do serviço {url}: {e}")
        return False, None

def renderizar_status_card(name: str, url: str, status: bool, status_code: int, 
                          downtime: str = None, description: str = "", uptime: float = 100.0) -> None:
    """
    Renderiza um cartão de status utilizando markdown com design aprimorado.

    Parâmetros:
        name (str): Nome do serviço.
        url (str): URL do serviço.
        status (bool): True se disponível, False se não.
        status_code (int): Código HTTP retornado.
        downtime (str): Timestamp de quando o serviço ficou indisponível.
        description (str): Descrição do serviço.
        uptime (float): Porcentagem de uptime do serviço.
    """
    pulse_class = "success-pulse" if status else "error-pulse"
    status_text = "ONLINE" if status else "OFFLINE"
    status_color = "green" if status else "red"
    
    uptime_class = get_uptime_color(uptime)
    
    if status:
        card_html = f"""
            <div class="status-card {pulse_class}" style='padding:15px; border: 1px solid #d4edda; border-radius: 10px; background-color: #f8f9fa;'>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h3 style='color: {status_color}; margin: 0;'>{name}</h3>
                    <span style='font-weight:bold; color:{status_color}; background-color:{"rgba(40,167,69,0.2)" if status else "rgba(220,53,69,0.2)"}; padding: 5px 10px; border-radius: 20px;'>
                        {status_text}
                    </span>
                </div>
                <p style="color: #666; font-size: 14px; margin-bottom: 15px;">{description}</p>
                <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                    <p style="margin: 0;"><strong>URL:</strong> <a href='{url}' target='_blank'>{url}</a></p>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <p style="margin: 0;"><strong>Status:</strong> 
                            <span style='font-weight:bold; color:{status_color};'>HTTP {status_code}</span>
                        </p>
                    </div>
                    <div>
                        <p style="margin: 0;"><strong>Uptime:</strong> 
                            <span class="{uptime_class}" style="font-weight: bold;">{uptime:.1f}%</span>
                        </p>
                    </div>
                </div>
            </div>
        """
    else:
        card_html = f"""
            <div class="status-card {pulse_class}" style='padding:15px; border: 1px solid #f5c6cb; border-radius: 10px; background-color: #f8f9fa;'>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h3 style='color: {status_color}; margin: 0;'>{name}</h3>
                    <span style='font-weight:bold; color:{status_color}; background-color:{"rgba(40,167,69,0.2)" if status else "rgba(220,53,69,0.2)"}; padding: 5px 10px; border-radius: 20px;'>
                        {status_text}
                    </span>
                </div>
                <p style="color: #666; font-size: 14px; margin-bottom: 15px;">{description}</p>
                <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                    <p style="margin: 0;"><strong>URL:</strong> <a href='{url}' target='_blank'>{url}</a></p>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <p style="margin: 0;"><strong>Status:</strong> 
                            <span style='font-weight:bold; color:{status_color};'>HTTP {status_code if status_code else "N/A"}</span>
                        </p>
                    </div>
                    <div>
                        <p style="margin: 0;"><strong>Uptime:</strong> 
                            <span class="{uptime_class}" style="font-weight: bold;">{uptime:.1f}%</span>
                        </p>
                    </div>
                </div>
                <div style="margin-top: 10px; padding: 10px; background-color: rgba(220,53,69,0.1); border-radius: 5px;">
                    <p style="margin: 0;"><strong>Fora do ar desde:</strong> {downtime}</p>
                    <p style="margin: 5px 0 0 0; font-size: 12px;">Último check: {datetime.now(BR_TZ).strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        """
    st.markdown(card_html, unsafe_allow_html=True)

def gerar_graficos_status(service_name, history_data):
    """
    Gera um gráfico de disponibilidade para um serviço específico.
    
    Parâmetros:
        service_name (str): Nome do serviço
        history_data (list): Lista de tuplas (timestamp, status)
    """
    if not history_data:
        return None
    
    # Converter dados para DataFrame
    df = pd.DataFrame(history_data, columns=['timestamp', 'status'])
    df['status_num'] = df['status'].apply(lambda x: 1 if x else 0)
    
    # Criar gráfico de linha para status
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['status_num'],
        mode='lines+markers',
        name='Status',
        line=dict(color='green', width=2),
        marker=dict(
            size=8,
            color=df['status_num'].apply(lambda x: 'green' if x == 1 else 'red'),
            symbol='circle'
        )
    ))
    
    # Configurar layout
    fig.update_layout(
        title=f'Disponibilidade de {service_name} nas últimas horas',
        xaxis_title='Hora',
        yaxis_title='Status',
        yaxis=dict(
            tickmode='array',
            tickvals=[0, 1],
            ticktext=['Offline', 'Online'],
            range=[-0.1, 1.1]
        ),
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='rgba(240,240,240,0.5)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    
    return fig

def calcular_uptime(history_data, window_hours=24):
    """
    Calcula a porcentagem de uptime nas últimas 'window_hours' horas
    
    Parâmetros:
        history_data (list): Lista de tuplas (timestamp, status)
        window_hours (int): Janela de tempo em horas para cálculo
    
    Retorna:
        float: Porcentagem de uptime (0-100)
    """
    if not history_data:
        return 100.0
    
    cutoff_time = datetime.now(BR_TZ) - timedelta(hours=window_hours)
    recent_data = [item for item in history_data if item[0] >= cutoff_time]
    
    if not recent_data:
        return 100.0
    
    up_count = sum(1 for _, status in recent_data if status)
    total_count = len(recent_data)
    
    return (up_count / total_count) * 100 if total_count > 0 else 100.0

def render_rotina_card(title, status, messages):
    """
    Renderiza um cartão para mostrar o status de uma rotina de processamento
    
    Parâmetros:
        title (str): Título da rotina
        status (bool): Status da rotina (True=operante, False=não operante)
        messages (list): Lista de mensagens de detalhes
    """
    if status is None:
        bg_color = "#f8f9fa"
        border_color = "#e0e0e0"
        title_color = "#6c757d"
        status_text = "Status Desconhecido"
        status_bg = "rgba(108, 117, 125, 0.2)"
        pulse_class = ""
    elif status:
        bg_color = "#f8f9fa"
        border_color = "#d4edda"
        title_color = "green"
        status_text = "OPERANTE"
        status_bg = "rgba(40, 167, 69, 0.2)"
        pulse_class = "success-pulse"
    else:
        bg_color = "#f8f9fa"
        border_color = "#f5c6cb"
        title_color = "red"
        status_text = "NÃO OPERANTE"
        status_bg = "rgba(220, 53, 69, 0.2)"
        pulse_class = "error-pulse"
    
    card_html = f"""
        <div class="status-card {pulse_class}" style='padding:15px; border: 1px solid {border_color}; border-radius: 10px; background-color: {bg_color};'>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style='color: {title_color}; margin: 0;'>{title}</h3>
                <span style='font-weight:bold; color:{title_color}; background-color:{status_bg}; padding: 5px 10px; border-radius: 20px;'>
                    {status_text}
                </span>
            </div>
            <div style="margin-top: 10px;">
                {''.join([f"<p style='margin: 5px 0; font-size: 14px;'>{msg}</p>" for msg in messages])}
            </div>
            <p style="margin: 10px 0 0 0; font-size: 12px; color: #666;">Último check: {datetime.now(BR_TZ).strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    """
    return card_html

def gerar_relatorio():
    """
    Gera um relatório em formato HTML com o status atual de todos os serviços e rotinas
    
    Retorna:
        str: HTML formatado com o relatório
    """
    now = datetime.now(BR_TZ).strftime("%d/%m/%Y %H:%M:%S")
    
    # Início do HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Relatório de Status - Torre de Controle</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f7fa; }}
            .container {{ max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1, h2 {{ color: #333; }}
            h1 {{ text-align: center; margin-bottom: 30px; }}
            h2 {{ border-bottom: 1px solid #eee; padding-bottom: 10px; margin-top: 30px; }}
            .status-item {{ margin-bottom: 15px; padding: 15px; border-radius: 8px; }}
            .status-online {{ background-color: #d4edda; }}
            .status-offline {{ background-color: #f8d7da; }}
            .status-title {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
            .status-badge {{ padding: 5px 10px; border-radius: 20px; font-weight: bold; }}
            .badge-online {{ background-color: rgba(40,167,69,0.2); color: green; }}
            .badge-offline {{ background-color: rgba(220,53,69,0.2); color: red; }}
            .footer {{ text-align: center; margin-top: 30px; font-size: 12px; color: #666; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Relatório de Status - Torre de Controle</h1>
            <p>Gerado em: {now}</p>
            
            <h2>Status dos Dashboards</h2>
    """
    
    # Adicionar status dos dashboards
    for name, details in services.items():
        status_checks = st.session_state.history.get(name, [])
        current_status = status_checks[-1][1] if status_checks else False
        uptime = calcular_uptime(status_checks)
        status_class = "status-online" if current_status else "status-offline"
        badge_class = "badge-online" if current_status else "badge-offline"
        status_text = "ONLINE" if current_status else "OFFLINE"
        
        html += f"""
            <div class="status-item {status_class}">
                <div class="status-title">
                    <h3>{name}</h3>
                    <span class="status-badge {badge_class}">{status_text}</span>
                </div>
                <p>{details.get('description', '')}</p>
                <p><strong>URL:</strong> <a href="{details['url']}">{details['url']}</a></p>
                <p><strong>Uptime (24h):</strong> {uptime:.1f}%</p>
        """
        
        if not current_status:
            downtime = st.session_state.downtime.get(name)
            html += f"<p><strong>Fora do ar desde:</strong> {downtime}</p>"
            
        html += "</div>"
    
    # Adicionar status das rotinas
    html += "<h2>Status das Rotinas de Processamento</h2>"
    
    rotinas = [
        {"name": "Extração de Janelas", "key": "janelas"},
        {"name": "LogComex - Diário", "key": "logcomex"},
        {"name": "Detran - Semanal", "key": "detran"}
    ]
    
    for rotina in rotinas:
        rotina_data = st.session_state.rotina_status.get(rotina["key"], {})
        status = rotina_data.get("status")
        messages = rotina_data.get("messages", [])
        
        if status is None:
            status_class = ""
            badge_class = ""
            status_text = "Status Desconhecido"
        elif status:
            status_class = "status-online"
            badge_class = "badge-online"
            status_text = "OPERANTE"
        else:
            status_class = "status-offline"
            badge_class = "badge-offline"
            status_text = "NÃO OPERANTE"
        
        html += f"""
            <div class="status-item {status_class}">
                <div class="status-title">
                    <h3>{rotina["name"]}</h3>
                    <span class="status-badge {badge_class}">{status_text}</span>
                </div>
        """
        
        for msg in messages:
            html += f"<p>{msg}</p>"
            
        html += "</div>"
    
    # Finalizar HTML
    html += """
            <div class="footer">
                <p>Este relatório foi gerado automaticamente pelo sistema de monitoramento Torre de Controle.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

def get_download_link(html_content, filename="relatorio_status.html"):
    """
    Gera um link para download do relatório em HTML
    
    Parâmetros:
        html_content (str): Conteúdo HTML do relatório
        filename (str): Nome do arquivo para download
    
    Retorna:
        str: Link HTML
    """
    html_bytes = html_content.encode()
    b64 = base64.b64encode(html_bytes).decode()
    href = f'data:text/html;base64,{b64}'
    return f'<a href="{href}" download="{filename}" class="download-button" style="display: inline-block; padding: 10px 20px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Baixar Relatório</a>'

# =====================================================================
# Funções Principais
# =====================================================================

def atualizar_metricas():
    """
    Atualiza as métricas gerais do sistema para exibição no dashboard
    """
    # Calcular total de serviços online
    total_servicos = len(services)
    servicos_online = sum(1 for name in services if st.session_state.history.get(name, []) and st.session_state.history[name][-1][1])
    
    # Calcular total de rotinas operantes
    total_rotinas = 3  # janelas, logcomex, detran
    rotinas_operantes = sum(1 for key in ["janelas", "logcomex", "detran"] 
                           if st.session_state.rotina_status.get(key, {}).get("status", False))
    
    # Calcular média de uptime
    uptime_values = [calcular_uptime(st.session_state.history.get(name, [])) for name in services]
    uptime_medio = sum(uptime_values) / len(uptime_values) if uptime_values else 0
    
    # Métricas de disponibilidade
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-title">Serviços Online</div>
            <div class="metric-value {get_uptime_color(servicos_online/total_servicos*100)}">{servicos_online}/{total_servicos}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-title">Rotinas Operantes</div>
            <div class="metric-value {get_uptime_color(rotinas_operantes/total_rotinas*100)}">{rotinas_operantes}/{total_rotinas}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-title">Uptime Médio (24h)</div>
            <div class="metric-value {get_uptime_color(uptime_medio)}">{uptime_medio:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

def monitorar_servicos() -> None:
    """
    Monitora os serviços definidos no dicionário 'services' e exibe o status e os prints lado a lado.
    Cada dashboard é exibido em uma coluna e a imagem se ajusta à largura da coluna.
    """
    # Atualizar métricas de status
    atualizar_metricas()
    
    # Mostrar hora da última atualização
    st.markdown(f"""
    <div class="refresh-info">
        Última atualização: {st.session_state.last_refresh.strftime('%d/%m/%Y %H:%M:%S')} 
        (Atualiza automaticamente a cada 2 minutos)
    </div>
    """, unsafe_allow_html=True)
    
    # Adicionar botão para atualização manual
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("🔄 Atualizar Agora", use_container_width=True):
            st.session_state.last_refresh = datetime.now(BR_TZ)
            st.rerun()
    
    # Definir as abas para os painéis
    tab1, tab2 = st.tabs(["🖥️ Visão dos Dashboards", "📊 Histórico de Status"])
    
    with tab1:
        st.markdown("<h2 style='text-align: center;'>Status dos Dashboards - Itracker</h2>", unsafe_allow_html=True)
        cols = st.columns(len(services))
        
        for col, (name, details) in zip(cols, services.items()):
            url = details["url"]
            marker = details["marker"]
            description = details.get("description", "")
            
            status, status_code = verificar_status_servico(url, marker)
            
            # Adicionar ao histórico para calcular uptime
            timestamp = datetime.now(BR_TZ)
            if name in st.session_state.history:
                # Manter apenas as últimas 24 horas de dados
                cutoff = timestamp - timedelta(hours=24)
                st.session_state.history[name] = [
                    item for item in st.session_state.history[name] if item[0] >= cutoff
                ]
                st.session_state.history[name].append((timestamp, status))
            else:
                st.session_state.history[name] = [(timestamp, status)]
            
            # Calcular uptime
            uptime = calcular_uptime(st.session_state.history[name])
            st.session_state.service_uptime[name] = uptime
            
            with col:
                if status:
                    st.session_state.downtime[name] = None
                    renderizar_status_card(name, url, status, status_code, description=description, uptime=uptime)
                    if CAPTURE_SCREENSHOT:
                        screenshot = capturar_screenshot(url, marker)
                        if screenshot:
                            st.image(screenshot, caption=f"Visualização atual de {name}", use_column_width=True)
                            st.download_button(
                                label="📥 Baixar Screenshot",
                                data=screenshot,
                                file_name=f"{name.lower().replace(' ', '_')}_screenshot.png",
                                mime="image/png",
                                key=f"btn_{name.lower().replace(' ', '_')}",
                                help="Baixar a imagem do dashboard"
                            )
                else:
                    if st.session_state.downtime[name] is None:
                        st.session_state.downtime[name] = datetime.now(BR_TZ).strftime("%d/%m/%Y %H:%M:%S")
                    renderizar_status_card(name, url, status, status_code, 
                                          downtime=st.session_state.downtime[name], 
                                          description=description, uptime=uptime)
                st.markdown("<br>", unsafe_allow_html=True)
    
    with tab2:
        st.markdown("<h2 style='text-align: center;'>Histórico de Disponibilidade</h2>", unsafe_allow_html=True)
        
        # Criar gráficos de histórico para cada serviço
        for name in services:
            history_data = st.session_state.history.get(name, [])
            fig = gerar_graficos_status(name, history_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Sem dados históricos suficientes para {name}")

def verificar_rotina_processamento() -> None:
    """
    Verifica o status da rotina de processamento baseada na atualização dos arquivos do Google Drive
    (rotina original) e exibe o status na interface do Streamlit.
    """
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
                
        st.session_state.rotina_status["janelas"]["status"] = operational
        st.session_state.rotina_status["janelas"]["messages"] = messages
        
        card_html = render_rotina_card("Extração de Janelas", operational, messages)
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e:
        error_html = render_rotina_card("Extração de Janelas", False, [f"Erro: {str(e)}"])
        st.markdown(error_html, unsafe_allow_html=True)
        logging.exception("Erro ao verificar rotina de processamento")
        st.session_state.rotina_status["janelas"]["status"] = False
        st.session_state.rotina_status["janelas"]["messages"] = [f"Erro: {str(e)}"]

def verificar_rotina_processamento_extra() -> None:
    """
    Verifica se a execução que começou às 6h de cada dia atualizou corretamente as planilhas
    (Exportação.xlsx, Importação.xlsx e Cabotagem.xlsx) utilizando as credenciais extra.
    Para cada planilha, o horário de modificação deve ser igual ou posterior a 6h do dia corrente.
    """
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
            today_6am = datetime.now(modified_time.tzinfo).replace(hour=6, minute=0, second=0, microsecond=0)
            if modified_time >= today_6am:
                messages.append(f"{name} foi atualizado após as 6h.")
            else:
                messages.append(f"{name} NÃO foi atualizado após as 6h.")
                operational = False
        
        st.session_state.rotina_status["logcomex"]["status"] = operational
        st.session_state.rotina_status["logcomex"]["messages"] = messages
        
        card_html = render_rotina_card("LogComex - Diário", operational, messages)
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e:
        error_html = render_rotina_card("LogComex - Diário", False, [f"Erro: {str(e)}"])
        st.markdown(error_html, unsafe_allow_html=True)
        logging.exception("Erro ao verificar rotina de processamento extra")
        st.session_state.rotina_status["logcomex"]["status"] = False
        st.session_state.rotina_status["logcomex"]["messages"] = [f"Erro: {str(e)}"]

def verificar_rotina_processamento_weekly() -> None:
    """
    Verifica se as planilhas dos DETRAN (Detran-RJ, Detran-SP e Detran-ES)
    foram extraídas nos últimos 7 dias, utilizando as credenciais extra.
    Cada planilha deve ter dados com menos de 7 dias da data atual.
    """
    try:
        extra_creds = service_account.Credentials.from_service_account_file(
            EXTRA_CREDENTIALS_FILE,
            scopes=['https://www.googleapis.com/auth/drive.metadata.readonly']
        )
        extra_drive_service = build('drive', 'v3', credentials=extra_creds)
        operational = True
        messages = []
        seven_days_seconds = 7 * 24 * 3600
        for name, file_id in weekly_spreadsheets.items():
            file_metadata = extra_drive_service.files().get(fileId=file_id, fields="modifiedTime").execute()
            modified_time_str = file_metadata.get("modifiedTime")
            modified_time = dateutil.parser.isoparse(modified_time_str)
            time_diff = (datetime.now(timezone.utc) - modified_time).total_seconds()
            if time_diff <= seven_days_seconds:
                messages.append(f"{name} foi atualizado nos últimos 7 dias.")
            else:
                messages.append(f"{name} NÃO foi atualizado nos últimos 7 dias.")
                operational = False
        
        st.session_state.rotina_status["detran"]["status"] = operational
        st.session_state.rotina_status["detran"]["messages"] = messages
        
        card_html = render_rotina_card("Detran - Semanal", operational, messages)
        st.markdown(card_html, unsafe_allow_html=True)
    except Exception as e:
        error_html = render_rotina_card("Detran - Semanal", False, [f"Erro: {str(e)}"])
        st.markdown(error_html, unsafe_allow_html=True)
        logging.exception("Erro ao verificar rotina de processamento semanal")
        st.session_state.rotina_status["detran"]["status"] = False
        st.session_state.rotina_status["detran"]["messages"] = [f"Erro: {str(e)}"]

def exibir_configuracoes():
    """
    Exibe opções de configuração para o dashboard no sidebar
    """
    st.sidebar.title("⚙️ Configurações")
    
    # Opções de intervalo de atualização
    st.sidebar.subheader("Intervalo de Atualização")
    refresh_interval = st.sidebar.slider(
        "Tempo entre atualizações (segundos)",
        min_value=30,
        max_value=300,
        value=120,
        step=30
    )
    
    # Opção para captura de screenshot
    capture_option = st.sidebar.checkbox("Capturar screenshots", value=CAPTURE_SCREENSHOT)
    if capture_option != CAPTURE_SCREENSHOT:
        st.sidebar.warning("A mudança será aplicada após reiniciar o aplicativo.")
    
    # Relatório de status
    st.sidebar.subheader("Relatório de Status")
    if st.sidebar.button("Gerar Relatório de Status"):
        with st.sidebar:
            with st.spinner("Gerando relatório..."):
                report_html = gerar_relatorio()
                st.sidebar.markdown(get_download_link(report_html), unsafe_allow_html=True)
    
    # Informações sobre o sistema
    st.sidebar.markdown("---")
    st.sidebar.subheader("Informações do Sistema")
    st.sidebar.info(
        f"""
        🕒 Hora atual: {datetime.now(BR_TZ).strftime('%d/%m/%Y %H:%M:%S')}
        🔄 Próxima atualização: em {refresh_interval} segundos
        💻 Total de serviços monitorados: {len(services)}
        """
    )
    
    # Créditos
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style='text-align: center'>
            <p style='font-size: 12px; color: #666;'>
                Torre de Controle - Monitor de Aplicações<br>
                v2.0 - Abril 2025
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    return refresh_interval * 1000  # Converter para milissegundos

def main():
    """
    Função principal que orquestra o monitoramento dos serviços e a verificação das rotinas de processamento.
    """
    # Configurações no sidebar
    refresh_interval = exibir_configuracoes()
    
    # Configurar autorefresh
    st_autorefresh(interval=refresh_interval, limit=None, key="monitor")
    
    # Atualizar timestamp da última atualização
    st.session_state.last_refresh = datetime.now(BR_TZ)
    
    # Monitorar serviços
    monitorar_servicos()
    
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    
    # Verificar rotinas de processamento
    st.markdown("<h1 style='text-align: center;'>Status das Rotinas de Processamento</h1>", unsafe_allow_html=True)
    cols = st.columns(3)
    with cols[0]:
        verificar_rotina_processamento()
    with cols[1]:
        verificar_rotina_processamento_extra()
    with cols[2]:
        verificar_rotina_processamento_weekly()
    
    # Rodapé
    st.markdown(
        """
        <div class="footer">
            <p>Torre de Controle - Monitor de Aplicações | Desenvolvido pelo setor de Qualidade - iTracker</p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()