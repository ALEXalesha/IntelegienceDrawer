; NSIS installer for DrawGuess
; Build: build.ps1 (или "C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi)
; Файл обязан быть в UTF-8 с BOM: при "Unicode true" makensis без BOM читает его
; как ANSI и портит кириллицу (ярлык «Удалить DrawGuess» становился мусором).

Unicode true

!define APP_NAME "DrawGuess"
!define APP_EXE  "DrawGuess.exe"
!define PUBLISHER "Alexey"
!define APP_VERSION "1.3.1"

Name "${APP_NAME}"
OutFile "release\DrawGuess-${APP_VERSION}-Setup.exe"
; С 1.3.1 - для одного пользователя, без прав администратора, как остальные программы
; автора: в %LOCALAPPDATA%\Programs и в HKCU. До 1.3.0 ставилась в Program Files и
; просила UAC ради того, что ни для чего не было нужно.
InstallDir "$LOCALAPPDATA\Programs\${APP_NAME}"
InstallDirRegKey HKCU "Software\${APP_NAME}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma

!include "MUI2.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "drawguess.ico"
!define MUI_UNICON "drawguess.ico"
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"

; Копия до 1.3.0 в Program Files удаляется только с правами администратора - установщик
; её не трогает, а говорит, где она (в тихой установке /S - молча).
Function .onInit
    ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString"
    StrCmp $0 "" done
    MessageBox MB_OK|MB_ICONINFORMATION "Прежняя версия DrawGuess стоит в Program Files для всех пользователей. Новая ставится только для вас и прав администратора не просит. Старую можно удалить в «Установка и удаление программ» (там нужны права администратора)." /SD IDOK
done:
FunctionEnd

Section "Install"
    SetOutPath "$INSTDIR"
    File "dist\${APP_EXE}"

    WriteUninstaller "$INSTDIR\uninstall.exe"

    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Удалить ${APP_NAME}.lnk" "$INSTDIR\uninstall.exe"
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    WriteRegStr HKCU "Software\${APP_NAME}" "InstallDir" "$INSTDIR"

    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${PUBLISHER}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "NoRepair" 1
SectionEnd

Section "Uninstall"
    Delete "$INSTDIR\${APP_EXE}"
    Delete "$INSTDIR\uninstall.exe"
    RMDir "$INSTDIR"

    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\Удалить ${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"

    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
    DeleteRegKey HKCU "Software\${APP_NAME}"
SectionEnd
