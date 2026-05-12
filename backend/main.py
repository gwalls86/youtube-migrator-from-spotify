"""
Spotify → YouTube Migrator — FastAPI Backend
Migra una playlist de Spotify (CSV de Exportify) a YouTube Music.

Uso:
    pip install fastapi uvicorn google-auth google-auth-oauthlib google-api-python-client ytmusicapi
    python main.py

Luego abre frontend/index.html en tu navegador.
Puerto: 8004
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import pickle
import queue
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import signal
import tkinter as tk
from tkinter import filedialog

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_FILE = "spotify_migrator_config.json"

BLACKLIST_WORDS = [
    "letra", "letras", "lyrics", "lyric", "karaoke",
    "cover", "covers", "versión cover", "en vivo", "live",
    "session", "sessions", "sofar", "acoustic", "acústico",
    "unplugged", "fan video", "fan made", "audio only",
    "full album", "full ep", "subtitulado", "traducido",
    "reaction", "reacción", "tutorial", "instrumental",
]

# ─────────────────────────────────────────────────────────────────────────────
# DATACLASS CONFIG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MigratorConfig:
    csv_file:        str = ""
    client_secrets:  str = "client_secrets.json"
    ytmusic_auth:    str = "ytmusic_auth.json"
    progress_file:   str = "progress.json"
    token_file:      str = "token.pickle"
    playlist_title:  str = "🎵 Mis canciones de Spotify"
    playlist_desc:   str = "Migrada desde Spotify con script automático"
    privacy:         str = "private"
    history:         Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC
# ─────────────────────────────────────────────────────────────────────────────

class MigrateRequest(BaseModel):
    csv_file:        str
    client_secrets:  str = "client_secrets.json"
    ytmusic_auth:    str = "ytmusic_auth.json"
    progress_file:   str = "progress.json"
    token_file:      str = "token.pickle"
    playlist_title:  str = "🎵 Mis canciones de Spotify"
    playlist_desc:   str = "Migrada desde Spotify con script automático"
    privacy:         str = "private"


class ConfigSaveRequest(BaseModel):
    config: dict


class ResetProgressRequest(BaseModel):
    progress_file: str


# ─────────────────────────────────────────────────────────────────────────────
# WORKER BRIDGE
# ─────────────────────────────────────────────────────────────────────────────

class OperationCancelled(Exception):
    pass


class CancellationToken:
    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def check(self) -> None:
        if self._cancelled.is_set():
            raise OperationCancelled()


class WorkerBridge:
    def __init__(self) -> None:
        self.q: queue.Queue[Tuple[str, Any]] = queue.Queue()
        self.cancel_token = CancellationToken()

    def log(self, message: str, level: str = "INFO") -> None:
        self.q.put(("log", {"message": message, "level": level,
                             "ts": datetime.now().strftime("%H:%M:%S")}))

    def progress(self, current: int, total: int, label: str = "") -> None:
        self.q.put(("progress", {"current": current, "total": total, "label": label}))

    def stats(self, data: dict) -> None:
        self.q.put(("stats", data))

    def status(self, text: str) -> None:
        self.q.put(("status", {"text": text}))

    def auth_needed(self, url: str) -> None:
        """Notifica al frontend que se abrió el navegador para OAuth."""
        self.q.put(("auth_needed", {"url": url}))

    def done(self, success: bool, summary: str = "", playlist_id: str = "") -> None:
        self.q.put(("done", {"success": success, "summary": summary, "playlist_id": playlist_id}))

    def drain(self) -> List[Tuple[str, Any]]:
        events = []
        while True:
            try:
                events.append(self.q.get_nowait())
            except queue.Empty:
                break
        return events


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def song_key(artist: str, name: str) -> str:
    return f"{artist.lower().strip()} - {name.lower().strip()}"


def is_blacklisted(title: str) -> bool:
    t = title.lower()
    return any(w in t for w in BLACKLIST_WORDS)


def _load_progress(progress_file: str) -> dict:
    if os.path.exists(progress_file):
        try:
            data = json.loads(Path(progress_file).read_text(encoding="utf-8"))
            if "done_song_keys" not in data:
                data["done_song_keys"] = []
            return data
        except Exception:
            pass
    return {"playlist_id": None, "done_song_keys": []}


def _save_progress(progress_file: str, playlist_id: str, done_song_keys: set) -> None:
    Path(progress_file).write_text(
        json.dumps({"playlist_id": playlist_id,
                    "done_song_keys": list(done_song_keys)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ─────────────────────────────────────────────────────────────────────────────
# LÓGICA DE MIGRACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def run_migration(cfg: MigratorConfig, bridge: WorkerBridge) -> None:
    import google.auth.transport.requests
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from ytmusicapi import YTMusic

    SCOPES = ["https://www.googleapis.com/auth/youtube"]

    # ── Validar archivos ──────────────────────────────────────────────────────
    for label, path in [
        ("CSV", cfg.csv_file),
        ("client_secrets.json", cfg.client_secrets),
        ("ytmusic_auth.json", cfg.ytmusic_auth),
    ]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Archivo no encontrado: {label} → {path}")

    # ── Autenticación YouTube (OAuth) ─────────────────────────────────────────
    bridge.log("Conectando con YouTube…", "INFO")
    bridge.status("Autenticando con Google…")

    creds = None
    if os.path.exists(cfg.token_file):
        with open(cfg.token_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            bridge.log("Refrescando token de acceso…", "INFO")
            creds.refresh(google.auth.transport.requests.Request())
        else:
            bridge.log("Se abrirá el navegador para autenticación OAuth de Google…", "WARNING")
            bridge.auth_needed("Abriendo navegador para login de Google...")
            flow = InstalledAppFlow.from_client_secrets_file(cfg.client_secrets, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(cfg.token_file, "wb") as f:
            pickle.dump(creds, f)

    youtube = build("youtube", "v3", credentials=creds)
    bridge.log("✓ Conectado a YouTube", "SUCCESS")
    bridge.cancel_token.check()

    # ── Conectar ytmusicapi ───────────────────────────────────────────────────
    bridge.log("Conectando con YouTube Music…", "INFO")
    ytmusic = YTMusic(cfg.ytmusic_auth)
    bridge.log("✓ Conectado a YouTube Music", "SUCCESS")
    bridge.cancel_token.check()

    # ── Leer CSV ──────────────────────────────────────────────────────────────
    bridge.log(f"Leyendo CSV: {cfg.csv_file}", "INFO")
    songs = []
    with open(cfg.csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name   = row.get("Track Name", "").strip()
            artist = row.get("Artist Name(s)", "").strip()
            artist = artist.split(",")[0].strip()
            if name and artist:
                songs.append({"name": name, "artist": artist})

    bridge.log(f"✓ {len(songs)} canciones leídas del CSV", "SUCCESS")

    csv_key = Path(cfg.csv_file).stem
    if csv_key not in cfg.history:
        cfg.history[csv_key] = {
            "playlist_title": cfg.playlist_title,
            "progress_file": cfg.progress_file,
        }

    bridge.cancel_token.check()

    # ── Cargar progreso ───────────────────────────────────────────────────────
    prog_data      = _load_progress(cfg.progress_file)
    saved_pl_id    = prog_data.get("playlist_id")
    done_song_keys = set(prog_data.get("done_song_keys", []))

    if not done_song_keys:
        bridge.log("Sin historial previo — se procesará el CSV completo", "WARNING")
    else:
        bridge.log(f"Historial cargado: {len(done_song_keys)} canciones ya procesadas", "INFO")

    # ── Playlist ──────────────────────────────────────────────────────────────
    bridge.log("Verificando playlist…", "INFO")
    bridge.status("Verificando playlist en YouTube…")
    playlist_id = None

    if saved_pl_id:
        try:
            r = youtube.playlists().list(part="id", id=saved_pl_id).execute()
            if r.get("items"):
                playlist_id = saved_pl_id
                bridge.log(f"✓ Playlist guardada encontrada: {playlist_id}", "SUCCESS")
        except Exception:
            pass

    if not playlist_id:
        try:
            response = youtube.playlists().list(
                part="id,snippet", mine=True, maxResults=50
            ).execute()
            for item in response.get("items", []):
                if item["snippet"]["title"] == cfg.playlist_title:
                    playlist_id = item["id"]
                    bridge.log(f"✓ Playlist existente: {playlist_id}", "SUCCESS")
                    cfg.history[csv_key]["playlist_id"] = playlist_id
                    break
        except Exception as e:
            bridge.log(f"No se pudo listar playlists: {e}", "WARNING")

    if not playlist_id:
        response = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": cfg.playlist_title, "description": cfg.playlist_desc},
                "status": {"privacyStatus": cfg.privacy}
            }
        ).execute()
        playlist_id = response["id"]
        bridge.log(f"✓ Playlist creada: {playlist_id}", "SUCCESS")
        cfg.history[csv_key]["playlist_id"] = playlist_id
        time.sleep(3)

    bridge.cancel_token.check()

    # ── Función de búsqueda ───────────────────────────────────────────────────
    def search_video(artist, name):
        query = f"{artist} - {name}"
        atv_fallback = None

        try:
            songs_results = ytmusic.search(query, filter="songs", limit=5)
            for r in songs_results:
                vid = r.get("videoId")
                if not vid:
                    continue
                vtype = r.get("videoType", "")
                if vtype == "MUSIC_VIDEO_TYPE_OMV":
                    return vid, r.get("title", ""), "OMV"
                if vtype == "MUSIC_VIDEO_TYPE_ATV" and atv_fallback is None:
                    atv_fallback = (vid, r.get("title", ""), "ATV")
        except Exception as e:
            bridge.log(f"Error búsqueda songs: {e}", "WARNING")

        try:
            vid_results = ytmusic.search(query, filter="videos", limit=10)
            for r in vid_results:
                vid   = r.get("videoId")
                title = r.get("title", "")
                if vid and not is_blacklisted(title):
                    return vid, title, "VIDEO"
        except Exception as e:
            bridge.log(f"Error búsqueda videos: {e}", "WARNING")

        if atv_fallback:
            return atv_fallback

        return None, None, None

    # ── Bucle principal ───────────────────────────────────────────────────────
    added     = 0
    skipped   = 0
    not_found = []
    quota_hit = False
    total     = len(songs)

    bridge.log("", "INFO")
    bridge.log("INICIANDO MIGRACIÓN", "INFO")
    bridge.status("Migrando canciones…")

    for i, song in enumerate(songs, 1):
        bridge.cancel_token.check()
        key   = song_key(song["artist"], song["name"])
        label = f"{song['artist']} — {song['name']}"
        bridge.progress(i, total, label)

        if key in done_song_keys:
            bridge.log(f"[{i}/{total}] ⏭  {label}", "DIM")
            skipped += 1
            bridge.stats({
                "added": added, "skipped": skipped,
                "not_found": len(not_found), "total": total, "current": i,
            })
            continue

        bridge.log(f"[{i}/{total}] 🔍 {label}", "INFO")
        video_id, video_title, vid_type = search_video(song["artist"], song["name"])

        if not video_id:
            bridge.log(f"  ⚠ No encontrado en YouTube", "WARNING")
            not_found.append(label)
            done_song_keys.add(key)
            bridge.stats({
                "added": added, "skipped": skipped,
                "not_found": len(not_found), "total": total, "current": i,
            })
            continue

        type_tag = {"OMV": "🎬 Video oficial", "ATV": "🎵 Audio oficial", "VIDEO": "📹 Video"}.get(vid_type, "")
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={"snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id}
                }}
            ).execute()
            done_song_keys.add(key)
            bridge.log(f"  ✓ {type_tag}: {video_title}", "SUCCESS")
            added += 1
            if added % 5 == 0:
                _save_progress(cfg.progress_file, playlist_id, done_song_keys)
        except HttpError as e:
            if "quotaExceeded" in str(e):
                bridge.log("⛔ CUOTA AGOTADA — guardando progreso…", "ERROR")
                _save_progress(cfg.progress_file, playlist_id, done_song_keys)
                quota_hit = True
                break
            else:
                bridge.log(f"  ✗ Error HTTP: {e}", "ERROR")

        bridge.stats({
            "added": added, "skipped": skipped,
            "not_found": len(not_found), "total": total, "current": i,
        })
        time.sleep(0.3)

    _save_progress(cfg.progress_file, playlist_id, done_song_keys)

    # ── Resumen ───────────────────────────────────────────────────────────────
    bridge.log(f"Total CSV: {total}  ·  Agregadas: {added}  ·  Ya procesadas: {skipped}  ·  No encontradas: {len(not_found)}", "SUCCESS")

    if not_found:
        bridge.log("Canciones no encontradas:", "WARNING")
        for s in not_found:
            bridge.log(f"  • {s}", "WARNING")

    if quota_hit:
        bridge.log("⏰ Cuota agotada — se resetea ~2am Colombia. Corre el script mañana para continuar.", "WARNING")
        bridge.done(False, "Cuota agotada — continuar mañana", playlist_id)
    else:
        bridge.log(f"🎬 https://www.youtube.com/playlist?list={playlist_id}", "SUCCESS")
        bridge.done(True, "¡Migración completada!", playlist_id)


# ─────────────────────────────────────────────────────────────────────────────
# ESTADO GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

_worker_bridge: Optional[WorkerBridge] = None
_worker_thread: Optional[threading.Thread] = None
_last_cfg: Optional[MigratorConfig] = None
CONFIG_PATH = Path(__file__).parent / CONFIG_FILE


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Spotify → YouTube Migrator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
def get_config():
    return _load_config()


@app.post("/api/config")
def save_config(req: ConfigSaveRequest):
    _save_config(req.config)
    return {"ok": True}


@app.get("/api/progress")
def get_progress(progress_file: str = "progress.json"):
    data = _load_progress(progress_file)
    return {
        "playlist_id": data.get("playlist_id"),
        "done_count": len(data.get("done_song_keys", [])),
        "exists": os.path.exists(progress_file),
    }


@app.post("/api/reset-progress")
def reset_progress(req: ResetProgressRequest):
    if os.path.exists(req.progress_file):
        os.remove(req.progress_file)
        return {"ok": True, "message": "Progreso eliminado"}
    return {"ok": False, "message": "Archivo no existe"}


@app.post("/api/start")
def start_migration(req: MigrateRequest):
    global _worker_bridge, _worker_thread, _last_cfg

    if _worker_thread and _worker_thread.is_alive():
        return {"ok": False, "error": "Ya hay una migración en curso"}

    cfg = MigratorConfig(
        csv_file       = req.csv_file,
        client_secrets = req.client_secrets,
        ytmusic_auth   = req.ytmusic_auth,
        progress_file  = req.progress_file,
        token_file     = req.token_file,
        playlist_title = req.playlist_title,
        playlist_desc  = req.playlist_desc,
        privacy        = req.privacy,
    )

    # Cargar historial del config guardado
    saved = _load_config()
    if "migrator" in saved and "history" in saved["migrator"]:
        cfg.history = saved["migrator"]["history"]

    _last_cfg = cfg
    _worker_bridge = WorkerBridge()
    bridge = _worker_bridge

    def worker():
        try:
            run_migration(cfg, bridge)
        except OperationCancelled:
            bridge.log("Operación cancelada por el usuario", "WARNING")
            bridge.done(False, "Cancelado")
        except Exception as exc:
            bridge.log(f"Error inesperado: {exc}", "ERROR")
            bridge.log(traceback.format_exc(), "DIM")
            bridge.done(False, str(exc))
        finally:
            # Guardar config con historial actualizado
            saved = _load_config()
            if "migrator" not in saved:
                saved["migrator"] = {}
            saved["migrator"]["history"] = cfg.history
            _save_config(saved)

    _worker_thread = threading.Thread(target=worker, daemon=True)
    _worker_thread.start()
    return {"ok": True}


@app.post("/api/stop")
def stop_migration():
    if _worker_bridge:
        _worker_bridge.cancel_token.cancel()
        return {"ok": True}
    return {"ok": False, "error": "No hay migración activa"}


@app.get("/api/status")
def get_status():
    return {"running": bool(_worker_thread and _worker_thread.is_alive())}


@app.get("/api/events")
async def event_stream(request: Request):
    async def generator():
        while True:
            if await request.is_disconnected():
                break
            bridge = _worker_bridge
            if bridge:
                for event_type, payload in bridge.drain():
                    data = json.dumps({"type": event_type, "payload": payload})
                    yield f"data: {data}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/shutdown")
async def shutdown():
    async def kill_proc():
        await asyncio.sleep(1)
        import os
        os.kill(os.getpid(), signal.SIGTERM)
        
    asyncio.create_task(kill_proc())
    return {"ok": True, "message": "Servidor apagándose..."}


@app.get("/api/select-folder")
def select_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = filedialog.askdirectory()
    root.destroy()
    return {"folder": folder_path}


@app.get("/api/select-file")
def select_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(filetypes=[("Archivos soportados", "*.csv;*.json"), ("Todos los archivos", "*.*")])
    root.destroy()
    return {"file": file_path}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Spotify -> YouTube Migrator -- Backend local")
    print("  http://localhost:8004")
    print("  Abre frontend/index.html en tu navegador")
    print("=" * 60)
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="warning")
