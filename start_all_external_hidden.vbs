Set WshShell = CreateObject("WScript.Shell")
WshShell.Run chr(34) & "start_all_external.bat" & chr(34), 0
Set WshShell = Nothing 