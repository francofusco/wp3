@echo off
pyinstaller wp3_designer.py --onefile --add-data config.yaml;.
MOVE /Y dist\wp3_designer.exe .
RD /S /Q __pycache__
RD /S /Q build
RD /S /Q dist
DEL wp3_designer.spec
