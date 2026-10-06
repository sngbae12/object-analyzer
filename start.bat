@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"

echo ========================================
echo  사물 분석 앱
echo ========================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo 가상환경 Python을 사용합니다: .venv
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python이 설치되어 있지 않습니다.
        echo https://www.python.org 에서 Python 3.11 이상을 설치한 뒤 다시 실행하세요.
        pause
        exit /b 1
    )
    echo 가상환경이 없어 .venv를 만들고 requirements.txt를 설치합니다...
    python -m venv .venv
    if errorlevel 1 (
        echo 가상환경 생성에 실패했습니다.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    "!PYTHON_EXE!" -m pip install --upgrade pip
    "!PYTHON_EXE!" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
)

"!PYTHON_EXE!" -c "import PyQt5, PIL" 2>nul
if errorlevel 1 (
    echo 필요한 패키지를 설치합니다...
    "!PYTHON_EXE!" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
)

set "QT_ROOT=%~dp0.venv\Lib\site-packages\PyQt5\Qt5"
if exist "%QT_ROOT%\plugins" (
    set "QT_PLUGIN_PATH=%QT_ROOT%\plugins"
    set "QT_QPA_PLATFORM_PLUGIN_PATH=%QT_ROOT%\plugins\platforms"
    set "PATH=%QT_ROOT%\bin;%PATH%"
)
set "QT_QPA_PLATFORM="

echo 앱을 실행합니다...
"!PYTHON_EXE!" main.py
if errorlevel 1 (
    echo.
    echo 실행 중 오류가 발생했습니다. 종료 코드: %ERRORLEVEL%
    if exist "실행오류.txt" type "실행오류.txt"
    pause
)
endlocal
