@echo off
pyinstaller wp3_designer.py --onefile
RD /S /Q __pycache__
RD /S /Q build
DEL wp3_designer.spec
MOVE /Y dist\wp3_designer.exe .
RD /S /Q dist
