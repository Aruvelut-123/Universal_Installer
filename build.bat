@echo off
echo start build exe file
echo Continue?
pause > nul
pyinstaller -y --clean --onefile --windowed -i pack/icon.ico main.py
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo change work directory
echo Continue?
pause > nul
cd pack
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo copy necessary files
echo Continue?
pause > nul
copy /Y BBPC.cfg BepInEx64/BepInEx/config/BBPC.cfg
copy /Y BBPC.cfg BepInEx86/BepInEx/config/BBPC.cfg
copy /Y header.png ../dist/pack/header.png
copy /Y left.png ../dist/pack/left.png
copy /Y items.json ../dist/pack/items.json
copy /Y icon.ico ../dist/pack/icon.ico
copy /Y LICENSE ../dist/pack/LICENSE
copy /Y readme.txt ../dist/pack/readme.txt
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo pack main files
echo Continue?
pause > nul
7z a BBDevAPI/. BBDevAPI.7z
7z a BBPC/. BBPC.7z
7z a BepInEx64/. BepInEx64.7z
7z a BepInEx86/. BepInEx86.7z
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo copy main files
echo Continue?
pause > nul
copy /Y BBDevAPI.7z ../dist/pack/BBDevAPI.7z
copy /Y BBPC.7z ../dist/pack/BBPC.7z
copy /Y BepInEx64.7z ../dist/pack/BepInEx64.7z
copy /Y BepInEx86.7z ../dist/pack/BepInEx86.7z
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo pack minimal installer
echo Continue?
pause > nul
7z a ../dist/. ../dist/BB+ 0.11 v1.12 Beta [MINI].7z
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo pack other files
echo Continue?
pause > nul
7z a NullTeacher/. NullTeacher.7z
7z a TeacherAPI/. TeacherAPI.7z
7z a CustomMainMenuAPI/. CustomMainMenuAPI.7z
7z a BBA-G/. BBA-G.7z
7z a FunSettings/. FunSettings.7z
7z a TweaksPlus/. TweaksPlus.7z
7z a PixelInternalAPI/. PixelInternalAPI.7z
7z a ExtraLockers/. ExtraLockers.7z
7z a CustomMusics/. CustomMusics.7z
7z a Animations/. Animations.7z
7z a ModdedModesAPI/. ModdedModesAPI.7z
7z a ChaoticChallenges/. ChaoticChallenges.7z
7z a StackableItems/. StackableItems.7z
7z a SeedExtension/. SeedExtension.7z
7z a PineDebug/. PineDebug.7z
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo copy other files
echo Continue?
pause > nul
copy /Y NullTeacher.7z ../dist/pack/NullTeacher.7z
copy /Y TeacherAPI.7z ../dist/pack/TeacherAPI.7z
copy /Y CustomMainMenuAPI.7z ../dist/pack/CustomMainMenuAPI.7z
copy /Y BBA-G.7z ../dist/pack/BBA-G.7z
copy /Y FunSettings.7z ../dist/pack/FunSettings.7z
copy /Y TweaksPlus.7z ../dist/pack/TweaksPlus.7z
copy /Y PixelInternalAPI.7z ../dist/pack/PixelInternalAPI.7z
copy /Y ExtraLockers.7z ../dist/pack/ExtraLockers.7z
copy /Y CustomMusics.7z ../dist/pack/CustomMusics.7z
copy /Y Animations.7z ../dist/pack/Animations.7z
copy /Y ModdedModesAPI.7z ../dist/pack/ModdedModesAPI.7z
copy /Y ChaoticChallenges.7z ../dist/pack/ChaoticChallenges.7z
copy /Y StackableItems.7z ../dist/pack/StackableItems.7z
copy /Y SeedExtension.7z ../dist/pack/SeedExtension.7z
copy /Y PineDebug.7z ../dist/pack/PineDebug.7z
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo pack full installer
echo Continue?
pause > nul
7z a ../dist/. ../dist/BB+ 0.11 v1.12 Beta [FULL].7z
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
echo Done!
pause