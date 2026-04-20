"""
facial_monitor_cable.py
-----------------------
Dashboard de monitoreo del Meta Quest Pro via cable USB (ADB).

- Datos faciales en tiempo real: ADB logcat
- Control de video: ADB (sin WiFi, sin IP)

Variables de entorno (.env):
    ADB_PATH=/ruta/completa/a/adb
"""

import subprocess
import threading
import json
import re
import os
import csv
from datetime import datetime
from collections import deque

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ADB_PATH     = os.getenv("ADB_PATH", "adb")
PACKAGE_NAME = "com.UnityTechnologies.com.unity.template.urpblank"
QUEST_FILES_PATH = f"/sdcard/Android/data/{PACKAGE_NAME}/files"

if not os.path.exists(ADB_PATH) and ADB_PATH != "adb":
    print(f"\n{'='*60}\nERROR: ADB no encontrado en: {ADB_PATH}\n{'='*60}\n")
    input("Presiona Enter para salir...")
    exit(1)

for folder in ["results/full"]:
    os.makedirs(folder, exist_ok=True)

EXPRESSION_NAMES = {
    0: "BrowLowererL",        1: "BrowLowererR",        2: "CheekPuffL",          3: "CheekPuffR",
    4: "CheekRaiserL",        5: "CheekRaiserR",         6: "CheekSuckL",          7: "CheekSuckR",
    8: "ChinRaiserB",         9: "ChinRaiserT",          10: "DimplerL",           11: "DimplerR",
    12: "EyesClosedL",        13: "EyesClosedR",         14: "EyesLookDownL",      15: "EyesLookDownR",
    16: "EyesLookLeftL",      17: "EyesLookLeftR",       18: "EyesLookRightL",     19: "EyesLookRightR",
    20: "EyesLookUpL",        21: "EyesLookUpR",         22: "InnerBrowRaiserL",   23: "InnerBrowRaiserR",
    24: "JawDrop",            25: "JawSidewaysLeft",     26: "JawSidewaysRight",   27: "JawThrust",
    28: "LidTightenerL",      29: "LidTightenerR",       30: "LipCornerDepressorL",31: "LipCornerDepressorR",
    32: "LipCornerPullerL",   33: "LipCornerPullerR",    34: "LipFunnelLB",        35: "LipFunnelLT",
    36: "LipFunnelRB",        37: "LipFunnelRT",         38: "LipPressorL",        39: "LipPressorR",
    40: "LipPuckerL",         41: "LipPuckerR",          42: "LipStretcherL",      43: "LipStretcherR",
    44: "LipSuckLB",          45: "LipSuckLT",           46: "LipSuckRB",          47: "LipSuckRT",
    48: "LipTightenerL",      49: "LipTightenerR",       50: "LipsToward",         51: "LowerLipDepressorL",
    52: "LowerLipDepressorR", 53: "MouthLeft",           54: "MouthRight",         55: "NoseWrinklerL",
    56: "NoseWrinklerR",      57: "OuterBrowRaiserL",    58: "OuterBrowRaiserR",   59: "UpperLidRaiserL",
    60: "UpperLidRaiserR",    61: "UpperLipRaiserL",     62: "UpperLipRaiserR"
}

KEY_EXPRESSIONS = {
    "blink":        [12, 13],
    "brow_tension": [0, 1, 22, 23],
    "mouth":        [24, 32, 33, 42, 43],
    "attention":    [14, 15, 20, 21],
}


class FacialTrackingDashboard:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Quest Pro – Facial Tracking Dashboard (Cable USB)")
        self.root.geometry("1400x900")

        self.data_buffer     = deque(maxlen=100)
        self.is_recording    = False
        self.adb_process     = None
        self.csv_file        = None
        self.csv_writer      = None
        self.attention_score = 0.0
        self.stress_score    = 0.0
        self.blink_count     = 0
        self.last_blink_time = 0.0
        self.available_videos = []
        self.current_video    = ""

        self.logcat_active = False
        self.logcat_process = None

        self._build_ui()
        # Iniciar logcat en segundo plano siempre
        self.root.after(500, self._start_background_logcat)

    def _start_background_logcat(self):
        """Inicia logcat permanente para recibir VIDEO_LIST y datos faciales."""
        if self.logcat_active:
            return
        self.logcat_active = True
        threading.Thread(target=self._run_background_logcat, daemon=True).start()
        self.log("Iniciando conexión ADB en segundo plano...")

    def _run_background_logcat(self):
        try:
            subprocess.run([ADB_PATH, "logcat", "-c"], timeout=5)

            self.logcat_process = subprocess.Popen(
                [ADB_PATH, "logcat", "-s", "Unity:D"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, bufsize=1,
            )

            self.root.after(0, lambda: self.log("✓ ADB conectado. Listo para recibir datos."))
            self.root.after(0, lambda: self.status_lbl.config(
                text="● ADB conectado", foreground="blue"))

            for line in self.logcat_process.stdout:
                if not self.logcat_active:
                    break

                # Datos faciales — solo procesar si hay captura activa
                if "[FACIAL_DATA]" in line and self.is_recording:
                    try:
                        start = line.index("[FACIAL_DATA]") + len("[FACIAL_DATA]")
                        raw   = re.sub(r"(\d),(\d)", r"\1.\2", line[start:].strip())
                        data  = json.loads(raw)
                        if "event" in data:
                            ev = data["event"]
                            self.root.after(0, lambda e=ev: self.log(f"[Quest] Sesión: {e}"))
                        else:
                            self._process_facial_data(data)
                    except (ValueError, json.JSONDecodeError):
                        pass

                # Lista de videos — siempre procesada
                elif "[VIDEO_LIST]" in line:
                    try:
                        start    = line.index("[VIDEO_LIST]") + len("[VIDEO_LIST]")
                        json_str = line[start:].strip()
                        self._handle_video_list(json_str)
                    except Exception:
                        pass

        except FileNotFoundError:
            self.root.after(0, lambda: self.log("ERROR: ADB no encontrado. Verifica ADB_PATH en .env"))
            self.root.after(0, lambda: self.status_lbl.config(
                text="● Error ADB", foreground="red"))
        except Exception as e:
            self.root.after(0, lambda: self.log(f"Error ADB: {e}"))
        finally:
            self.logcat_active = False

    def _build_ui(self):
        # ── Barra de captura ──
        top = ttk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=8)

        self.start_btn = ttk.Button(top, text="▶ Iniciar Captura",
                                    command=self.start_capture, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(top, text="⏹ Detener Captura",
                                   command=self.stop_capture, width=20, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.status_lbl = ttk.Label(top, text="● Desconectado",
                                    foreground="red", font=("Arial", 12, "bold"))
        self.status_lbl.pack(side=tk.LEFT, padx=20)

        # ── Panel de control de video ──
        video_frame = ttk.LabelFrame(self.root, text="🎥 Control de Video 360 (via ADB cable)", padding=8)
        video_frame.pack(fill=tk.X, padx=10, pady=4)

        row1 = ttk.Frame(video_frame)
        row1.pack(fill=tk.X)

        ttk.Label(row1, text="Video:").pack(side=tk.LEFT, padx=(0, 4))

        self.video_combo = ttk.Combobox(row1, state="readonly", width=45)
        self.video_combo.pack(side=tk.LEFT, padx=4)

        ttk.Button(row1, text="▶ Reproducir", width=14,
                   command=self._send_play_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(row1, text="⏮", width=4,
                   command=self._send_prev).pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="⏭", width=4,
                   command=self._send_next).pack(side=tk.LEFT, padx=2)

        row2 = ttk.Frame(video_frame)
        row2.pack(fill=tk.X, pady=(4, 0))

        ttk.Button(row2, text="🔄 Obtener lista del Quest", width=26,
                   command=self._request_video_list).pack(side=tk.LEFT, padx=(0, 10))

        self.current_lbl = ttk.Label(row2, text="Video actual: --", font=("Arial", 10))
        self.current_lbl.pack(side=tk.LEFT)

        # ── Área principal ──
        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Columna 1 – métricas
        col1 = ttk.LabelFrame(main, text="📊 Métricas Derivadas", padding=10)
        col1.grid(row=0, column=0, sticky="nsew", padx=5)

        self.attention_lbl = ttk.Label(col1, text="Atención: --", font=("Arial", 14))
        self.attention_lbl.pack(pady=5)
        self.stress_lbl = ttk.Label(col1, text="Estrés: --", font=("Arial", 14))
        self.stress_lbl.pack(pady=5)
        self.blink_lbl = ttk.Label(col1, text="Parpadeos: 0", font=("Arial", 14))
        self.blink_lbl.pack(pady=5)

        ttk.Separator(col1, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(col1, text="Último frame:", font=("Arial", 11, "bold")).pack()
        self.key_text = scrolledtext.ScrolledText(col1, width=30, height=18)
        self.key_text.pack(pady=5)

        # Columna 2 – gráficos
        col2 = ttk.LabelFrame(main, text="📈 Gráficos en Tiempo Real", padding=10)
        col2.grid(row=0, column=1, sticky="nsew", padx=5)

        self.fig = Figure(figsize=(8, 7))
        self.ax1 = self.fig.add_subplot(311)
        self.ax2 = self.fig.add_subplot(312)
        self.ax3 = self.fig.add_subplot(313)
        for ax, title in zip([self.ax1, self.ax2, self.ax3],
                             ["Atención", "Estrés", "Act. Boca"]):
            ax.set_title(title); ax.set_ylim([0, 1]); ax.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=col2)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Columna 3 – log
        col3 = ttk.LabelFrame(main, text="📝 Log", padding=10)
        col3.grid(row=0, column=2, sticky="nsew", padx=5)

        self.log_text = scrolledtext.ScrolledText(col3, width=40, height=38)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(0, weight=1)

    # ── Control de video via ADB ───────────────────────────────────────────────

    def _send_adb_command(self, command_str):
        remote_path = f"{QUEST_FILES_PATH}/quest_cmd.txt"

        def _run():
            try:
                # Usar shell=True para que la redirección > funcione correctamente
                full_cmd = f'"{ADB_PATH}" shell "echo {command_str} > {remote_path}"'
                result = subprocess.run(
                    full_cmd, shell=True,
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    self.root.after(0, lambda: self.log(f"✓ Comando enviado: {command_str}"))
                else:
                    self.root.after(0, lambda: self.log(f"✗ Error ADB: {result.stderr.strip()}"))
            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: self.log("✗ ADB timeout. ¿Quest conectado?"))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"✗ Error: {e}"))

        threading.Thread(target=_run, daemon=True).start()

    def _send_play_selected(self):
        selected = self.video_combo.get()
        if not selected:
            messagebox.showwarning("Sin selección", "Selecciona un video primero.")
            return
        self._send_adb_command(f"PLAY:{selected}")
        self.current_video = selected
        self.current_lbl.config(text=f"Video actual: {selected}")

    def _send_next(self):
        self._send_adb_command("NEXT")

    def _send_prev(self):
        self._send_adb_command("PREV")

    def _request_video_list(self):
        self.log("Solicitando lista de videos al Quest...")
        self._send_adb_command("LIST")

    def _handle_video_list(self, json_str):
        try:
            # Limpiar posibles caracteres extra al final de la línea
            json_str = json_str.strip()
            self.log(f"[DEBUG] VIDEO_LIST recibido: {json_str[:100]}")
            data    = json.loads(json_str)
            videos  = data.get("videos", [])
            current = data.get("current", "")

            self.available_videos = videos
            self.current_video    = current

            def _update(v=videos, c=current):
                self.video_combo["values"] = v
                if c in v:
                    self.video_combo.set(c)
                self.current_lbl.config(text=f"Video actual: {c}")
                self.log(f"✓ Lista actualizada: {len(v)} videos.")

            self.root.after(0, _update)
        except Exception as ex:
            err = str(ex)
            self.root.after(0, lambda e=err: self.log(f"✗ Error parseando lista: {e}"))

    # ── Captura ADB ────────────────────────────────────────────────────────────

    def start_capture(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"results/full/facial_data_{timestamp}.csv"

        try:
            self.csv_file   = open(filename, "w", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(["Timestamp", "Expression_ID", "Expression_Name", "Value"])
        except Exception as e:
            self.log(f"Error creando CSV: {e}")
            return

        self.is_recording    = True
        self.blink_count     = 0
        self.last_blink_time = 0.0

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_lbl.config(text="● Capturando", foreground="green")

        self.log("=" * 50)
        self.log("CAPTURA INICIADA")
        self.log(f"Guardando en: {filename}")
        self.log("=" * 50)

        # El logcat ya está corriendo en segundo plano
        # Solo iniciamos la actualización de gráficos
        self.root.after(100, self._update_graphs)

    def stop_capture(self):
        self.is_recording = False

        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.log("CSV guardado.")

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_lbl.config(text="● ADB conectado", foreground="blue")
        self.log("Captura detenida.")



    # ── Procesamiento de datos faciales ───────────────────────────────────────

    def _process_facial_data(self, data):
        timestamp   = data.get("t", 0)
        expressions = data.get("d", {})

        rows = []
        for exp_id_str, value in expressions.items():
            exp_id   = int(exp_id_str)
            exp_name = EXPRESSION_NAMES.get(exp_id, f"Unknown_{exp_id}")
            rows.append([timestamp, exp_id, exp_name, value])

        def _write(rows=rows):
            if self.csv_writer:
                self.csv_writer.writerows(rows)
        self.root.after(0, _write)

        self._calculate_metrics(expressions, timestamp)

        mouth = [expressions.get(str(i), 0) for i in KEY_EXPRESSIONS["mouth"]]
        self.data_buffer.append({
            "time":      timestamp,
            "attention": self.attention_score,
            "stress":    self.stress_score,
            "mouth":     sum(mouth) / max(len(mouth), 1),
        })

        self.root.after(0, self._update_labels)

    def _calculate_metrics(self, expressions, timestamp):
        def avg(ids):
            vals = [expressions.get(str(i), 0) for i in ids]
            return sum(vals) / max(len(vals), 1)

        self.attention_score = 1.0 - avg(KEY_EXPRESSIONS["attention"])
        self.stress_score    = avg(KEY_EXPRESSIONS["brow_tension"])

        if avg(KEY_EXPRESSIONS["blink"]) > 0.7 and (timestamp - self.last_blink_time) > 0.2:
            self.blink_count    += 1
            self.last_blink_time = timestamp

    def _update_labels(self):
        self.attention_lbl.config(
            text=f"Atención: {self.attention_score*100:.1f}%",
            foreground="green" if self.attention_score > 0.7 else "orange")
        self.stress_lbl.config(
            text=f"Estrés: {self.stress_score*100:.1f}%",
            foreground="red" if self.stress_score > 0.5 else "green")
        self.blink_lbl.config(text=f"Parpadeos: {self.blink_count}")

        if self.data_buffer:
            d = self.data_buffer[-1]
            self.key_text.delete(1.0, tk.END)
            self.key_text.insert(tk.END,
                f"t={d['time']:.2f}s\n\n"
                f"Atención:  {d['attention']*100:.1f}%\n"
                f"Estrés:    {d['stress']*100:.1f}%\n"
                f"Act.Boca:  {d['mouth']*100:.1f}%\n")

    def _update_graphs(self):
        if not self.is_recording:
            return

        if len(self.data_buffer) > 1:
            times     = [d["time"]      for d in self.data_buffer]
            attention = [d["attention"] for d in self.data_buffer]
            stress    = [d["stress"]    for d in self.data_buffer]
            mouth     = [d["mouth"]     for d in self.data_buffer]

            self.ax1.clear(); self.ax2.clear(); self.ax3.clear()
            self.ax1.plot(times, attention, "g-", linewidth=2)
            self.ax1.set_title("Atención"); self.ax1.set_ylim([0,1]); self.ax1.grid(True)
            self.ax2.plot(times, stress,    "r-", linewidth=2)
            self.ax2.set_title("Estrés");   self.ax2.set_ylim([0,1]); self.ax2.grid(True)
            self.ax3.plot(times, mouth,     "b-", linewidth=2)
            self.ax3.set_title("Act. Boca"); self.ax3.set_ylim([0,1]); self.ax3.grid(True)
            self.ax3.set_xlabel("Tiempo (s)")
            self.canvas.draw()

        self.root.after(100, self._update_graphs)

    def log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {message}\n")
        self.log_text.see(tk.END)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.log("Dashboard listo. Conecta el Quest Pro con cable USB.")
        self.log("Presiona ▶ para iniciar captura, o usa el botón A/X del Quest.")
        self.root.mainloop()

    def _on_close(self):
        if self.is_recording:
            self.stop_capture()
        self.logcat_active = False
        if self.logcat_process:
            try: self.logcat_process.terminate()
            except: pass
        self.root.destroy()


if __name__ == "__main__":
    FacialTrackingDashboard().run()