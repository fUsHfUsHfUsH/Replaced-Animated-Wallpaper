"""Local system helper for the REPLACED menu (OPTIONS box).
Serves 127.0.0.1:8001 only. Endpoints used by index.html:
  GET  /status                  -> {volume, muted, brightness}
  POST /volume     {level 0-100} -> set master volume
  POST /brightness {level 0-100} -> set display brightness (laptop panels via WMI)
  POST /power      {action}      -> sleep | restart | shutdown | signout
Run: python system_helper.py (keep it running while using the menu).
"""
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8001


def get_volume():
    import comtypes
    comtypes.CoInitialize()
    try:
        from pycaw.pycaw import AudioUtilities
        vol = AudioUtilities.GetSpeakers().EndpointVolume
        return round(vol.GetMasterVolumeLevelScalar() * 100), bool(vol.GetMute())
    finally:
        comtypes.CoUninitialize()


def set_volume(level):
    import comtypes
    comtypes.CoInitialize()
    try:
        from pycaw.pycaw import AudioUtilities
        vol = AudioUtilities.GetSpeakers().EndpointVolume
        vol.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100.0, None)
        if vol.GetMute():
            vol.SetMute(0, None)
        return round(vol.GetMasterVolumeLevelScalar() * 100)
    finally:
        comtypes.CoUninitialize()


def get_brightness():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness"],
        capture_output=True, text=True, timeout=30)
    vals = [int(x) for x in r.stdout.replace("\r", "\n").split("\n") if x.strip().isdigit()]
    return vals[0] if vals else None


def set_brightness(level):
    level = max(0, min(100, int(level)))
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{level})"],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError("brightness not supported on this display")
    return level


def do_power(action):
    # Delays give a chance to cancel with: shutdown /a
    cmds = {
        "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        "restart": ["shutdown", "/r", "/t", "10", "/c", "Restarting from REPLACED menu"],
        "shutdown": ["shutdown", "/s", "/t", "10", "/c", "Shutting down from REPLACED menu"],
        "signout": ["shutdown", "/l"],
    }
    if action not in cmds:
        raise ValueError("unknown action")
    subprocess.Popen(cmds[action])
    return action


class Handler(BaseHTTPRequestHandler):
    server_version = "ReplacedHelper/1.0"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            try:
                volume, muted = get_volume()
            except Exception as e:
                return self._json({"error": f"volume: {e}"}, 500)
            try:
                brightness = get_brightness()
            except Exception:
                brightness = None
            return self._json({"volume": volume, "muted": muted, "brightness": brightness})
        return self._json({"error": "not found"}, 404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad json"}, 400)
        try:
            if self.path == "/volume":
                return self._json({"volume": set_volume(int(data.get("level", 0)))})
            if self.path == "/brightness":
                return self._json({"brightness": set_brightness(int(data.get("level", 0)))})
            if self.path == "/power":
                return self._json({"action": do_power(str(data.get("action", "")))})
        except Exception as e:
            return self._json({"error": str(e)[:200]}, 500)
        return self._json({"error": "not found"}, 404)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"helper on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
