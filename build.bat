@echo off
echo go into venv
echo Continue?
pause > nul
call .venv\Scripts\activate.bat
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo start build exe file
echo Continue?
pause > nul
pyinstaller -y --debug all --onefile --windowed -i pack/icon.ico main.py
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo change work directory
echo Continue?
pause > nul
copy metadata.json dist\metadata.json /Y
cd pack
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo copy necessary files
echo Continue?
pause > nul
copy BBPC.cfg BepInEx64\BepInEx\config\BBPC.cfg /Y
copy BBPC.cfg BepInEx86\BepInEx\config\BBPC.cfg /Y
copy header.png ..\dist\pack\header.png /Y
copy left.png ..\dist\pack\left.png /Y
copy items.json ..\dist\pack\items.json /Y
copy icon.ico ..\dist\pack\icon.ico /Y
copy LICENSE ..\dist\pack\LICENSE /Y
copy readme.txt ..\dist\pack\readme.txt /Y
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo pack main files
echo Continue?
pause > nul
7z a BBDevAPI.7z BBDevAPI/.
7z a BBPC.7z BBPC/.
7z a BepInEx64.7z BepInEx64/.
7z a BepInEx86.7z BepInEx86/.
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo copy main files
echo Continue?
pause > nul
copy BBDevAPI.7z ..\dist\pack\BBDevAPI.7z /Y
copy BBPC.7z ..\dist\pack\BBPC.7z /Y
copy BepInEx64.7z ..\dist\pack\BepInEx64.7z /Y
copy BepInEx86.7z ..\dist\pack\BepInEx86.7z /Y
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo pack minimal installer
echo Continue?
pause > nul
7z a "../BB+ 0.11 v1.12 Beta [MINI].7z" ../dist/.
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo pack other files
echo Continue?
pause > nul
7z a NullTeacher.7z NullTeacher/.
7z a TeacherAPI.7z TeacherAPI/.
7z a CustomMainMenuAPI.7z CustomMainMenuAPI/.
7z a BBA-G.7z BBA-G/.
7z a FunSettings.7z FunSettings/.
7z a TweaksPlus.7z TweaksPlus/.
7z a PixelInternalAPI.7z PixelInternalAPI/.
7z a ExtraLockers.7z ExtraLockers/.
7z a CustomMusics.7z CustomMusics/.
7z a Animations.7z Animations/.
7z a ModdedModesAPI.7z ModdedModesAPI/.
7z a ChaoticChallenges.7z ChaoticChallenges/.
7z a StackableItems.7z StackableItems/.
7z a SeedExtension.7z SeedExtension/.
7z a PineDebug.7z PineDebug/.
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo copy other files
echo Continue?
pause > nul
copy NullTeacher.7z ..\dist\pack\NullTeacher.7z /Y
copy TeacherAPI.7z ..\dist\pack\TeacherAPI.7z /Y
copy CustomMainMenuAPI.7z ..\dist\pack\CustomMainMenuAPI.7z /Y
copy BBA-G.7z ..\dist\pack\BBA-G.7z /Y
copy FunSettings.7z ..\dist\pack\FunSettings.7z /Y
copy TweaksPlus.7z ..\dist\pack\TweaksPlus.7z /Y
copy PixelInternalAPI.7z ..\dist\pack\PixelInternalAPI.7z /Y
copy ExtraLockers.7z ..\dist\pack\ExtraLockers.7z /Y
copy CustomMusics.7z ..\dist\pack\CustomMusics.7z /Y
copy Animations.7z ..\dist\pack\Animations.7z /Y
copy ModdedModesAPI.7z ..\dist\pack\ModdedModesAPI.7z /Y
copy ChaoticChallenges.7z ..\dist\pack\ChaoticChallenges.7z /Y
copy StackableItems.7z ..\dist\pack\StackableItems.7z /Y
copy SeedExtension.7z ..\dist\pack\SeedExtension.7z /Y
copy PineDebug.7z ..\dist\pack\PineDebug.7z /Y
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo pack full installer
echo Continue?
pause > nul
7z a "../BB+ 0.11 v1.12 Beta [FULL].7z" ../dist/.
if "%errorlevel%" neq "0" (
    echo Error when running this section!
    pause
    exit /b %errorlevel%
)
cls
echo remove temp files
echo Continue?
pause > nul
rd /S /Q ..\dist\pack
mkdir ..\dist\pack
del /S /Q ..\dist\metadata.json
cls
echo Done!
pause