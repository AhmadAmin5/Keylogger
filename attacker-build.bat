@echo off

echo Cleaning old files...
rmdir /s /q build
del bin\Listener.exe

echo Building EXE...

python -m PyInstaller ^
--onefile ^
--name Listener ^
--distpath bin ^
attacker.py

@REM --icon victim-icon.ico ^
del *.spec
rmdir /s /q build

echo Done.
pause