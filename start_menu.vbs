Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\chris\replaced-menu"
' Helper API for brightness/volume/power (no console window)
sh.Run """C:\Users\chris\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"" ""C:\Users\chris\replaced-menu\system_helper.py""", 0, False
' Menu page server for http://127.0.0.1:8000/
sh.Run """C:\Users\chris\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe"" -m http.server 8000", 0, False
