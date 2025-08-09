@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Enhanced Media Converter v2.0
::
:: This script provides a user-friendly, action-oriented menu to convert,
:: analyze, and manipulate media files using ffmpeg and ffprobe.
:: ============================================================================

if not exist "ffmpeg.exe" (
    echo ffmpeg.exe not found. Please place this script in the same folder.
    pause
    exit /b
)
if not exist "ffprobe.exe" (
    echo ffprobe.exe not found. Please place this script in the same folder.
    pause
    exit /b
)

:main_menu
cls
echo ===============================================
echo          ffmpeg-this
echo ===============================================
echo.
echo 1. Select a Media File to Process
echo 2. Batch Convert All Videos to a Format
echo 3. Exit
echo.
set /p choice="Enter your choice: "

if "%choice%"=="1" goto list_files
if "%choice%"=="2" goto batch_convert
if "%choice%"=="3" exit /b

echo Invalid choice.
pause
goto main_menu

:list_files
cls
echo ===============================================
echo           Select a Media File
echo ===============================================
echo.
set /a count=0
for %%f in (*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv *.mp3 *.flac *.wav *.ogg) do (
    if exist "%%f" (
        set /a count+=1
        set "file_!count!=%%f"
        echo !count!. %%f
    )
)

if %count%==0 (
    echo No media files found in this directory.
    pause
    goto main_menu
)

echo.
set /p file_choice="Enter the number of the file to process (or 0 to go back): "
if /i "%file_choice%"=="0" goto main_menu
if not defined file_choice (goto list_files)
if %file_choice% gtr %count% (
    echo Invalid selection.
    pause
    goto list_files
)
if %file_choice% lss 1 (
    echo Invalid selection.
    pause
    goto list_files
)

set "selected_file=!file_%file_choice%!"
goto action_menu

:action_menu
cls
echo ===============================================
echo      Actions for: %selected_file%
echo ===============================================
echo.
echo 1. Inspect File Details
echo 2. Convert (Lossless)
echo 3. Convert (Smaller File Size)
echo 4. Trim Video
echo 5. Extract Audio
echo 6. Remove Audio
echo.
echo 7. Back to File List
echo 8. Main Menu
echo.
set /p action_choice="Enter your choice: "

if "%action_choice%"=="1" goto inspect_file
if "%action_choice%"=="2" goto convert_lossless
if "%action_choice%"=="3" goto convert_lossy
if "%action_choice%"=="4" goto trim_video
if "%action_choice%"=="5" goto extract_audio
if "%action_choice%"=="6" goto remove_audio
if "%action_choice%"=="7" goto list_files
if "%action_choice%"=="8" goto main_menu

echo Invalid choice.
pause
goto action_menu

:inspect_file
cls
echo ===============================================
echo        File Information: %selected_file%
echo ===============================================
echo.
for %%s in ("%selected_file%") do set size_bytes=%%~zs
set /a size_mb=!size_bytes! / 1048576
echo Size: !size_mb! MB

for /f "delims=" %%i in ('ffprobe -v error -show_entries format^=duration -of default^=noprint_wrappers^=1:nokey^=1 "%selected_file%"') do set "duration=%%i"
echo Duration: !duration! seconds
echo.

echo --- Video Streams ---
set has_video=false
for /f "usebackq tokens=1-5 delims=," %%a in (`ffprobe -v error -select_streams v -show_entries stream^=index,codec_name,width,height,r_frame_rate -of csv^=p^=0 "%selected_file%" 2^>nul`) do (
    set has_video=true
    echo   Stream #%%a: %%b, %%cx%%d, %%e fps
)
if not !has_video! == true echo   No video streams found.
echo.

echo --- Audio Streams ---
set has_audio=false
for /f "usebackq tokens=1-4 delims=," %%a in (`ffprobe -v error -select_streams a -show_entries stream^=index,codec_name,sample_rate,channels -of csv^=p^=0 "%selected_file%" 2^>nul`) do (
    set has_audio=true
    echo   Stream #%%a: %%b, %%c Hz, %%d channels
)
if not !has_audio! == true echo   No audio streams found.
echo.
echo ===============================================
pause
goto action_menu

:convert_lossless
cls
echo ===============================================
echo      Lossless Convert: %selected_file%
echo ===============================================
echo.
echo Select output format:
echo 1. MP4
echo 2. MKV
echo 3. MOV
set /p format_choice="Choice: "
if "%format_choice%"=="1" set output_format=mp4
if "%format_choice%"=="2" set output_format=mkv
if "%format_choice%"=="3" set output_format=mov
if not defined output_format (
    echo Invalid choice.
    pause
    goto action_menu
)

for %%i in ("%selected_file%") do set "output_file=%%~ni_lossless.%output_format%"
ffmpeg.exe -i "%selected_file%" -map 0 -c copy -c:s mov_text "!output_file!"
echo.
echo Conversion finished.
pause
goto action_menu

:convert_lossy
cls
echo ===============================================
echo      Lossy Convert: %selected_file%
echo ===============================================
echo.
echo Select quality preset (lower CRF is higher quality):
echo 1. High Quality (CRF 18)
echo 2. Medium Quality (CRF 23)
echo 3. Low Quality (CRF 28)
set /p quality_choice="Choice: "
if "%quality_choice%"=="1" set crf=18
if "%quality_choice%"=="2" set crf=23
if "%quality_choice%"=="3" set crf=28
if not defined crf (
    echo Invalid choice.
    pause
    goto action_menu
)

for %%i in ("%selected_file%") do set "output_file=%%~ni_crf%crf%.mp4"
ffmpeg.exe -i "%selected_file%" -c:v libx264 -crf %crf% -c:a copy "!output_file!"
echo.
echo Conversion finished.
pause
goto action_menu



:trim_video
cls
echo ===============================================
echo      Trim Video: %selected_file%
echo ===============================================
echo.
set /p start_time="Enter start time (HH:MM:SS): "
set /p end_time="Enter end time (HH:MM:SS): "

if not defined start_time (goto action_menu)
if not defined end_time (goto action_menu)

for %%i in ("%selected_file%") do set "output_file=%%~ni_trimmed.%%~xi"
ffmpeg.exe -i "%selected_file%" -ss %start_time% -to %end_time% -c copy "!output_file!"
echo.
echo Trimming finished.
pause
goto action_menu

:extract_audio
cls
echo ===============================================
echo      Extract Audio: %selected_file%
echo ===============================================
echo.
echo Select audio format:
echo 1. MP3 (lossy)
echo 2. FLAC (lossless)
echo 3. WAV (uncompressed)
set /p audio_choice="Choice: "
if "%audio_choice%"=="1" set audio_opts=-c:a libmp3lame -q:a 2 & set ext=mp3
if "%audio_choice%"=="2" set audio_opts=-c:a flac & set ext=flac
if "%audio_choice%"=="3" set audio_opts=-c:a pcm_s16le & set ext=wav
if not defined audio_opts (
    echo Invalid choice.
    pause
    goto action_menu
)

for %%i in ("%selected_file%") do set "output_file=%%~ni_audio.%ext%"
ffmpeg.exe -i "%selected_file%" -vn !audio_opts! "!output_file!"
echo.
echo Extraction finished.
pause
goto action_menu

:remove_audio
cls
for %%i in ("%selected_file%") do set "output_file=%%~ni_no_audio.%%~xi"
echo Removing audio from "%selected_file%"...
ffmpeg.exe -i "%selected_file%" -c:v copy -an "!output_file!"
echo.
echo Audio removal finished.
pause
goto action_menu

:batch_convert
cls
echo ===============================================
echo         Batch Convert All Video Files
echo ===============================================
echo.
echo Select output format:
echo 1. MP4
echo 2. MKV
echo 3. MOV
set /p batch_format_choice="Choice: "
if "%batch_format_choice%"=="1" set batch_format=mp4
if "%batch_format_choice%"=="2" set batch_format=mkv
if "%batch_format_choice%"=="3" set batch_format=mov
if not defined batch_format (
    echo Invalid choice.
    pause
    goto main_menu
)

echo.
echo This will convert ALL video files to .%batch_format%
set /p confirm="Are you sure? (y/n): "
if /i not "%confirm%"=="y" goto main_menu

for %%f in (*.mkv *.mp4 *.avi *.mov *.webm *.flv *.wmv) do (
    if exist "%%f" (
        echo Converting "%%f"...
        ffmpeg.exe -i "%%f" -map 0 -c copy -c:s mov_text "%%~nf_batch.%batch_format%"
    )
)

echo.
echo Batch conversion finished.
pause
goto main_menu