O script monitora três aspectos principais a cada 2 minutos (120000 ms), graças ao st_autorefresh:

1. Status dos Dashboards
Verifica se os serviços definidos no dicionário services estão operantes. Para cada serviço:
Faz uma requisição HTTP para a URL associada.
Se CHECK_MARKER for True, verifica se um marcador de texto específico aparece no HTML retornado.
Se CAPTURE_SCREENSHOT for True, captura uma captura de tela do serviço usando Selenium.
Atualiza o estado de downtime se um serviço cair.
2. Status das Rotinas de Processamento
Verificação de atualização dos arquivos no Google Drive:
Para cada arquivo listado nos dicionários spreadsheet_files, extra_spreadsheets e weekly_spreadsheets, o script:
Obtém o horário da última modificação via API do Google Drive.
Verifica se os arquivos foram atualizados dentro de um intervalo esperado:
spreadsheet_files: Atualizações dentro de 5 minutos.
extra_spreadsheets: Atualizações após as 6h do dia corrente.
weekly_spreadsheets: Atualizações dentro dos últimos 7 dias.
Com base nessas verificações, exibe mensagens indicando se as atualizações ocorreram conforme esperado.
Resumo do que é verificado a cada 2 minutos:
Os três dashboards monitorados (Painel Comercial, Painel de Multas, Painel de Janelas) estão no ar?
As planilhas do Google Drive foram atualizadas corretamente?
Janelas: Arquivos modificados nos últimos 5 minutos.
LogComex: Arquivos modificados após as 6h do dia atual.
DETRAN: Arquivos modificados nos últimos 7 dias.
Caso algo não esteja conforme esperado, o script exibe mensagens de erro e alerta visualmente no Streamlit.