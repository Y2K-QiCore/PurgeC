@echo off
set PYTHONPATH=%~dp0lib;%~dp0python\Lib\site-packages
set PATH=%~dp0python;%PATH%
python\python.exe scripts\main.py
pause