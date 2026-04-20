import subprocess
import threading
import json
import time
from datetime import datetime
from collections import deque
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import csv
import os
import glob
import socket
import re
from dotenv import load_dotenv
load_dotenv()

ADB_PATH = os.getenv('ADB_PATH')
QUEST_IP = os.getenv('QUEST_IP')

if not os.path.exists(ADB_PATH):
    print("\n" + "="*60)
    print("ERROR: No se encontró ADB en la ruta configurada")
    print("="*60)
    print(f"\nRuta buscada: {ADB_PATH}")
    print("\nVerifica que:")
    print("1. Unity esté instalado correctamente")
    print("2. La ruta de ADB sea correcta")
    print("="*60 + "\n")
    input("Presiona Enter para salir...")
    exit(1)
else:
    print(f"✓ ADB encontrado en: {ADB_PATH}\n")

EXPRESSION_NAMES = {
    0: "BrowLowererL", 1: "BrowLowererR", 2: "CheekPuffL", 3: "CheekPuffR",
    4: "CheekRaiserL", 5: "CheekRaiserR", 6: "CheekSuckL", 7: "CheekSuckR",
    8: "ChinRaiserB", 9: "ChinRaiserT", 10: "DimplerL", 11: "DimplerR",
    12: "EyesClosedL", 13: "EyesClosedR", 14: "EyesLookDownL", 15: "EyesLookDownR",
    16: "EyesLookLeftL", 17: "EyesLookLeftR", 18: "EyesLookRightL", 19: "EyesLookRightR",
    20: "EyesLookUpL", 21: "EyesLookUpR", 22: "InnerBrowRaiserL", 23: "InnerBrowRaiserR",
    24: "JawDrop", 25: "JawSidewaysLeft", 26: "JawSidewaysRight", 27: "JawThrust",
    28: "LidTightenerL", 29: "LidTightenerR", 30: "LipCornerDepressorL", 31: "LipCornerDepressorR",
    32: "LipCornerPullerL", 33: "LipCornerPullerR", 34: "LipFunnelLB", 35: "LipFunnelLT",
    36: "LipFunnelRB", 37: "LipFunnelRT", 38: "LipPressorL", 39: "LipPressorR",
    40: "LipPuckerL", 41: "LipPuckerR", 42: "LipStretcherL", 43: "LipStretcherR",
    44: "LipSuckLB", 45: "LipSuckLT", 46: "LipSuckRB", 47: "LipSuckRT",
    48: "LipTightenerL", 49: "LipTightenerR", 50: "LipsToward", 51: "LowerLipDepressorL",
    52: "LowerLipDepressorR", 53: "MouthLeft", 54: "MouthRight", 55: "NoseWrinklerL",
    56: "NoseWrinklerR", 57: "OuterBrowRaiserL", 58: "OuterBrowRaiserR", 59: "UpperLidRaiserL",
    60: "UpperLidRaiserR", 61: "UpperLipRaiserL", 62: "UpperLipRaiserR"
}

KEY_EXPRESSIONS = {
    'blink': [12, 13],
    'brow_tension': [0, 1, 22, 23],
    'mouth_activity': [24, 32, 33, 42, 43],
    'attention': [14, 15, 20, 21]
}

class FacialTrackingDashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Quest Pro - Facial Tracking Dashboard")
        self.root.geometry("1400x900")

        self.data_buffer = deque(maxlen=100)
        self.is_recording = False
        self.adb_process = None
        self.csv_file = None
        self.csv_writer = None

        self.websocket_port = 8765
        self.video_control_port = 8766
        self.available_videos = []
        self.current_video = ""
        self.quest_ip = QUEST_IP

        self.attention_score = 0
        self.stress_score = 0
        self.blink_count = 0
        self.last_blink_time = 0

        self.setup_ui()
        self.root.after(1, self.start_websocket_server)
        self.load_video_list()

    def setup_ui(self):
        control_frame = ttk.Frame(self.root)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        self.start_btn = ttk.Button(control_frame, text="▶ Iniciar Captura",
                                     command=self.start_capture, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="⏹ Detener Captura",
                                    command=self.stop_capture, width=20, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(control_frame, text="● Desconectado",
                                       foreground="red", font=("Arial", 12, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=20)

        video_control_frame = ttk.LabelFrame(self.root, text="🎥 Control de Video 360", padding=10)
        video_control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(video_control_frame, text="Seleccionar video:").pack(side=tk.LEFT, padx=5)

        self.video_combo = ttk.Combobox(video_control_frame, state="readonly", width=40)
        self.video_combo.pack(side=tk.LEFT, padx=5)
        self.video_combo.bind("<<ComboboxSelected>>", self.on_video_selected)

        self.refresh_videos_btn = ttk.Button(video_control_frame, text="🔄 Actualizar",
                                             command=self.load_video_list)
        self.refresh_videos_btn.pack(side=tk.LEFT, padx=5)

        self.current_video_label = ttk.Label(video_control_frame, text="Video actual: --",
                                             font=("Arial", 10))
        self.current_video_label.pack(side=tk.LEFT, padx=20)

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        metrics_frame = ttk.LabelFrame(main_frame, text="📊 Métricas Derivadas", padding=10)
        metrics_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        self.attention_label = ttk.Label(metrics_frame, text="Atención: --", font=("Arial", 14))
        self.attention_label.pack(pady=5)

        self.stress_label = ttk.Label(metrics_frame, text="Estrés: --", font=("Arial", 14))
        self.stress_label.pack(pady=5)

        self.blink_label = ttk.Label(metrics_frame, text="Parpadeos: 0", font=("Arial", 14))
        self.blink_label.pack(pady=5)

        ttk.Separator(metrics_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        ttk.Label(metrics_frame, text="Expresiones Clave:", font=("Arial", 12, "bold")).pack()

        self.key_expressions_text = scrolledtext.ScrolledText(metrics_frame, width=30, height=20)
        self.key_expressions_text.pack(pady=5)

        graph_frame = ttk.LabelFrame(main_frame, text="📈 Gráficos en Tiempo Real", padding=10)
        graph_frame.grid(row=0, column=1, sticky="nsew", padx=5)

        self.fig = Figure(figsize=(8, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.ax1 = self.fig.add_subplot(311)
        self.ax2 = self.fig.add_subplot(312)
        self.ax3 = self.fig.add_subplot(313)

        self.ax1.set_title("Atención")
        self.ax2.set_title("Estrés (Tensión Facial)")
        self.ax3.set_title("Actividad de Boca")

        log_frame = ttk.LabelFrame(main_frame, text="📝 Log de Datos", padding=10)
        log_frame.grid(row=0, column=2, sticky="nsew", padx=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, width=40, height=40)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=2)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(0, weight=1)

    def start_capture(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"results/full/facial_data_pc_{timestamp}.csv"

        os.makedirs("results/full", exist_ok=True)

        try:
            self.csv_file = open(filename, 'w', newline='')
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow(['Timestamp', 'Expression_ID', 'Expression_Name', 'Value'])
        except Exception as e:
            self.log(f"Error creando archivo CSV: {e}")
            return

        self.is_recording = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="● Capturando", foreground="green")

        self.log("=" * 60)
        self.log("INICIANDO CAPTURA")
        self.log("=" * 60)
        self.log(f"Guardando datos en: {filename}")
        self.log("")
        self.log("Iniciando conexión ADB para datos en tiempo real...")

        self.adb_thread = threading.Thread(target=self.read_adb_logcat, daemon=True)
        self.adb_thread.start()

        self.root.after(100, self.update_graphs)

    def stop_capture(self):
        self.is_recording = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="● Detenido", foreground="orange")

        if self.csv_file:
            self.csv_file.close()
            self.log("Archivo CSV cerrado y guardado")

        self.log("Captura detenida")

    def read_adb_logcat(self):
        try:
            subprocess.run([ADB_PATH, 'logcat', '-c'], check=True)

            self.adb_process = subprocess.Popen(
                [ADB_PATH, 'logcat', '-s', 'Unity:D'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            self.log("Conectado a Quest Pro vía ADB")

            for line in self.adb_process.stdout:
                if not self.is_recording:
                    break

                if '[FACIAL_DATA]' in line:
                    try:
                        json_start = line.index('[FACIAL_DATA]') + len('[FACIAL_DATA]')
                        json_str = line[json_start:].strip()
                        json_str = re.sub(r'(\d+),(\d+)', r'\1.\2', json_str)
                        data = json.loads(json_str)
                        self.process_data(data)
                    except (ValueError, json.JSONDecodeError):
                        pass

        except Exception as e:
            self.log(f"Error en ADB: {str(e)}")
            self.root.after(0, lambda: self.status_label.config(
                text="● Error de conexión", foreground="red"))

    def process_data(self, data):
        timestamp = data.get('t', 0)
        expressions = data.get('d', {})

        for exp_id, value in expressions.items():
            exp_id = int(exp_id)
            exp_name = EXPRESSION_NAMES.get(exp_id, f"Unknown_{exp_id}")
            self.csv_writer.writerow([timestamp, exp_id, exp_name, value])

        self.calculate_metrics(expressions, timestamp)

        self.data_buffer.append({
            'time': timestamp,
            'attention': self.attention_score,
            'stress': self.stress_score,
            'mouth': sum([expressions.get(str(i), 0) for i in KEY_EXPRESSIONS['mouth_activity']]) / 5
        })

        self.root.after(0, self.update_metrics_display)

    def calculate_metrics(self, expressions, timestamp):
        attention_values = [expressions.get(str(i), 0) for i in KEY_EXPRESSIONS['attention']]
        self.attention_score = 1.0 - (sum(attention_values) / len(attention_values))

        stress_values = [expressions.get(str(i), 0) for i in KEY_EXPRESSIONS['brow_tension']]
        self.stress_score = sum(stress_values) / len(stress_values)

        blink_values = [expressions.get(str(i), 0) for i in KEY_EXPRESSIONS['blink']]
        avg_blink = sum(blink_values) / len(blink_values)

        if avg_blink > 0.7 and (timestamp - self.last_blink_time) > 0.2:
            self.blink_count += 1
            self.last_blink_time = timestamp

    def update_metrics_display(self):
        self.attention_label.config(
            text=f"Atención: {self.attention_score*100:.1f}%",
            foreground="green" if self.attention_score > 0.7 else "orange"
        )
        self.stress_label.config(
            text=f"Estrés: {self.stress_score*100:.1f}%",
            foreground="red" if self.stress_score > 0.5 else "green"
        )
        self.blink_label.config(text=f"Parpadeos: {self.blink_count}")

        self.key_expressions_text.delete(1.0, tk.END)
        if self.data_buffer:
            latest = self.data_buffer[-1]
            self.key_expressions_text.insert(tk.END, f"Timestamp: {latest['time']:.2f}s\n\n")
            self.key_expressions_text.insert(tk.END, f"Atención: {latest['attention']*100:.1f}%\n")
            self.key_expressions_text.insert(tk.END, f"Estrés: {latest['stress']*100:.1f}%\n")
            self.key_expressions_text.insert(tk.END, f"Act. Boca: {latest['mouth']*100:.1f}%\n")

    def update_graphs(self):
        if not self.is_recording:
            return

        if len(self.data_buffer) > 1:
            times = [d['time'] for d in self.data_buffer]
            attention = [d['attention'] for d in self.data_buffer]
            stress = [d['stress'] for d in self.data_buffer]
            mouth = [d['mouth'] for d in self.data_buffer]

            self.ax1.clear()
            self.ax2.clear()
            self.ax3.clear()

            self.ax1.plot(times, attention, 'g-', linewidth=2)
            self.ax1.set_ylabel('Atención')
            self.ax1.set_ylim([0, 1])
            self.ax1.grid(True)

            self.ax2.plot(times, stress, 'r-', linewidth=2)
            self.ax2.set_ylabel('Estrés')
            self.ax2.set_ylim([0, 1])
            self.ax2.grid(True)

            self.ax3.plot(times, mouth, 'b-', linewidth=2)
            self.ax3.set_ylabel('Act. Boca')
            self.ax3.set_xlabel('Tiempo (s)')
            self.ax3.set_ylim([0, 1])
            self.ax3.grid(True)

            self.canvas.draw()

        self.root.after(100, self.update_graphs)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        if self.is_recording:
            self.stop_capture()
        self.root.destroy()

    def start_websocket_server(self):
        def server_thread():
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server_socket.bind(('0.0.0.0', self.websocket_port))
                server_socket.listen(1)

                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)

                self.root.after(0, lambda: self.log(f"Servidor TCP iniciado en {local_ip}:{self.websocket_port}"))

                while True:
                    try:
                        client, address = server_socket.accept()
                        data = b""
                        while True:
                            chunk = client.recv(4096)
                            if not chunk:
                                break
                            data += chunk
                        client.close()

                        if data:
                            json_str = data.decode('utf-8').strip()
                            import re
                            json_str = re.sub(r'(\d),(\d)', r'\1.\2', json_str)
                            self.root.after(0, lambda j=json_str: self.process_session_summary(j))

                    except Exception as e:
                        self.root.after(0, lambda: self.log(f"Error en conexión: {e}"))

            except Exception as e:
                self.root.after(0, lambda: self.log(f"Error en servidor TCP: {e}"))

        threading.Thread(target=server_thread, daemon=True).start()

    def process_session_summary(self, json_str):
        try:
            data = json.loads(json_str)
            self.log("="*60)
            self.log("RESUMEN DE SESIÓN RECIBIDO")
            self.log("="*60)

            metadata = data.get('metadata', {})
            self.log(f"Timestamp: {metadata.get('timestamp', 'N/A')}")
            self.log(f"Duración: {metadata.get('duration', 0):.2f}s")
            self.log(f"Puntos de datos: {metadata.get('dataPoints', 0)}")
            self.log(f"Total parpadeos: {metadata.get('totalBlinks', 0)}")

            stats = data.get('statistics', {})
            self.log("ESTADÍSTICAS:")
            for metric, values in stats.items():
                self.log(f"  {metric}: Min={values.get('min',0):.3f} Max={values.get('max',0):.3f} Avg={values.get('avg',0):.3f}")

            os.makedirs("results/summary", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = f"results/summary/session_summary_{timestamp}.json"
            with open(summary_file, 'w') as f:
                json.dump(data, f, indent=2)
            self.log(f"Resumen guardado en: {summary_file}")

        except Exception as e:
            self.log(f"Error procesando resumen: {e}")

    def send_command_to_quest(self, command):
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(5)
            client.connect((self.quest_ip, self.video_control_port))
            client.sendall(command.encode('utf-8'))
            response = client.recv(4096).decode('utf-8')
            client.close()
            return response
        except socket.timeout:
            self.log("✗ Timeout conectando al Quest Pro")
            messagebox.showerror("Error", "No se pudo conectar al Quest Pro.\nVerifica que:\n1. La app esté corriendo\n2. Estén en la misma red WiFi\n3. La IP sea correcta")
            return None
        except Exception as e:
            self.log(f"✗ Error enviando comando: {e}")
            return None

    def load_video_list(self):
        self.log("Solicitando lista de videos...")
        response = self.send_command_to_quest("LIST")
        if response:
            try:
                data = json.loads(response)
                if data.get('status') == 'ok':
                    self.available_videos = data.get('videos', [])
                    self.current_video = data.get('current', '')
                    self.video_combo['values'] = self.available_videos
                    if self.current_video in self.available_videos:
                        self.video_combo.set(self.current_video)
                    self.current_video_label.config(text=f"Video actual: {self.current_video}")
                    self.log(f"✓ {len(self.available_videos)} videos disponibles")
                else:
                    self.log(f"✗ Error: {data.get('message', 'Unknown error')}")
            except json.JSONDecodeError as e:
                self.log(f"✗ Error parseando respuesta: {e}")

    def on_video_selected(self, event=None):
        selected = self.video_combo.get()
        if not selected:
            return
        if messagebox.askyesno("Cambiar video", f"¿Cambiar al video '{selected}'?"):
            self.change_video(selected)

    def change_video(self, video_name):
        self.log(f"Cambiando a video: {video_name}")
        response = self.send_command_to_quest(f"PLAY:{video_name}")
        if response:
            try:
                data = json.loads(response)
                if data.get('status') == 'ok':
                    self.current_video = video_name
                    self.current_video_label.config(text=f"Video actual: {video_name}")
                    self.log(f"✓ Video cambiado exitosamente")
                else:
                    self.log(f"✗ Error: {data.get('message', 'Unknown error')}")
            except json.JSONDecodeError as e:
                self.log(f"✗ Error parseando respuesta: {e}")

if __name__ == "__main__":
    dashboard = FacialTrackingDashboard()
    dashboard.run()