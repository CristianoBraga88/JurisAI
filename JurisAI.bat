@echo off
cd /d "%~dp0"
call venv\Scripts\activate
start "" cmd /c "timeout /t 6 /nobreak >nul && start http://localhost:8501"
python -m streamlit run app.py