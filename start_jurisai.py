import subprocess
import webbrowser
import time
import sys
import os

# caminho da pasta do projeto
project_dir = os.path.dirname(os.path.abspath(__file__))

app_path = os.path.join(project_dir, "app.py")

# inicia streamlit usando python atual
subprocess.Popen([
    sys.executable,
    "-m",
    "streamlit",
    "run",
    app_path
])

# espera iniciar
time.sleep(4)

# abre navegador
webbrowser.open("http://localhost:8501")