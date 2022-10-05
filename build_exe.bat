@echo off
pyinstaller wp3_designer.py --onefile
MOVE /Y dist\wp3_designer.exe .
tar -a -cf wp3_designer.zip config.yaml wp3_designer.exe
RD /S /Q __pycache__
RD /S /Q build
RD /S /Q dist
DEL wp3_designer.spec
DEL wp3_designer.exe
