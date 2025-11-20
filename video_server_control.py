import os
import glob
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from http.server import SimpleHTTPRequestHandler
import socketserver
import subprocess
import time

# ===================================================================
# --- CONFIGURACIÓN DE PUERTOS Y RUTAS ---
# ===================================================================
VIDEO_COMMAND_PORT = 9000  # Puerto TCP para enviar el comando de URL a Unity
HTTP_SERVER_PORT = 8000    # Puerto HTTP para el streaming de video
VIDEO_DIR = "Videos"       # Subdirectorio donde se encuentran los videos

# Ruta de ADB (Asegúrate de que sea la correcta, como en tu script original)
# Si no usas ADB para obtener la IP, puedes usar la IP de tu PC directamente
ADB_PATH = r'C:\Program Files\Unity\Hub\Editor\6000.0.47f1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe'

# ===================================================================
# --- CLASE PARA MANEJO DE LA INTERFAZ Y SERVIDORES ---
# ===================================================================

class VideoControlServer:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Video VR")
        self.root.geometry("500x300")
        
        self.available_videos = {}
        self.http_server = None
        
        self.scan_videos()
        self.start_http_server()
        self.setup_ui()

    def scan_videos(self):
        """Escanea la carpeta Videos y genera las URLs HTTP."""
        if not os.path.exists(VIDEO_DIR):
            os.makedirs(VIDEO_DIR)
            print(f"[SETUP] Directorio '{VIDEO_DIR}' creado. Agrega videos.")
            return

        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        video_files = glob.glob(os.path.join(VIDEO_DIR, "*.mp4"))
        
        self.available_videos.clear()
        for full_path in video_files:
            file_name = os.path.basename(full_path)
            # La URL usa la IP de la PC y el puerto HTTP.
            http_url = f"http://{local_ip}:{HTTP_SERVER_PORT}/{VIDEO_DIR}/{file_name}"
            self.available_videos[file_name] = http_url
            
        print(f"[SETUP] {len(self.available_videos)} videos cargados para streaming.")

    def start_http_server(self):
        """Inicia un servidor HTTP en un thread para servir archivos."""
        
        # Clase para manejar las peticiones HTTP
        class VideoHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                # Establece el directorio actual como raíz para servir archivos
                super().__init__(directory=os.getcwd(), *args, **kwargs)

        def run_http_server():
            try:
                # El servidor escucha en todas las interfaces ('0.0.0.0')
                with socketserver.TCPServer(("", HTTP_SERVER_PORT), VideoHandler) as httpd:
                    self.http_server = httpd
                    print(f"[HTTP] Servidor de streaming iniciado en puerto {HTTP_SERVER_PORT}.")
                    httpd.serve_forever()
            except Exception as e:
                print(f"[ERROR] Fallo al iniciar Servidor HTTP: {e}")
                messagebox.showerror("Error HTTP", f"Fallo al iniciar el servidor HTTP en el puerto {HTTP_SERVER_PORT}. Puede estar en uso.")

        http_thread = threading.Thread(target=run_http_server, daemon=True)
        http_thread.start()

    def send_video_command(self, video_url):
        """Envía la URL del video a Unity por TCP (Cliente TCP aquí)."""
        quest_ip = '127.0.0.1' 
        try:
            # Intentamos obtener la IP del Quest Pro para la conexión directa (opcional, requiere ADB)
            if os.path.exists(ADB_PATH):
                 result = subprocess.run([ADB_PATH, 'shell', 'ip addr show wlan0'], capture_output=True, text=True)
                 ip_line = [line for line in result.stdout.split('\n') if 'inet ' in line and 'scope global' in line]
                 if ip_line:
                    quest_ip = ip_line[0].split()[1].split('/')[0]
            
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((quest_ip, VIDEO_COMMAND_PORT))
            
            # Enviamos la URL del video
            client_socket.sendall(video_url.encode('ascii') + b'\n') # Agregamos un salto de línea
            print(f"[TCP] Comando enviado: '{video_url}' a {quest_ip}:{VIDEO_COMMAND_PORT}")

            client_socket.close()
            return True
            
        except Exception as e:
            print(f"[ERROR] Fallo al enviar comando TCP: {e}")
            messagebox.showerror("Error TCP", 
                                 f"No se pudo conectar a la Quest Pro en {quest_ip}:{VIDEO_COMMAND_PORT}.\n"
                                 f"Verifica: Unity esté escuchando y la IP/puerto sean accesibles.")
            return False

    # ===================================================================
    # --- INTERFAZ DE USUARIO ---
    # ===================================================================

    def setup_ui(self):
        """Configura la interfaz Tkinter para seleccionar el video."""
        
        if not self.available_videos:
            ttk.Label(self.root, text=f"ERROR: No se encontraron videos en la carpeta '{VIDEO_DIR}'.", 
                      foreground="red").pack(pady=50)
            return
            
        ttk.Label(self.root, text="Selecciona el Video 360:", 
                  font=("Arial", 12, "bold")).pack(pady=(20, 10))

        video_names = list(self.available_videos.keys())
        self.selected_video = tk.StringVar(self.root)
        self.selected_video.set(video_names[0]) 
        
        video_menu = ttk.OptionMenu(self.root, self.selected_video, video_names[0], *video_names)
        video_menu.config(width=40)
        video_menu.pack(pady=10)

        def set_and_send():
            selected_name = self.selected_video.get()
            video_url = self.available_videos[selected_name] 
            
            self.send_video_command(video_url)

        send_btn = ttk.Button(self.root, text="Enviar Video a VR", 
                              command=set_and_send, width=40)
        send_btn.pack(pady=20)
        
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        ttk.Label(self.root, 
                  text=f"Streaming URL base: http://{local_ip}:{HTTP_SERVER_PORT}",
                  foreground="gray").pack()
        
    def on_closing(self):
        """Manejo del cierre de la aplicación."""
        if self.http_server:
            self.http_server.shutdown()
            print("[HTTP] Servidor HTTP detenido.")
        self.root.destroy()


if __name__ == "__main__":
    # Importar SimpleHTTPRequestHandler y socketserver debe hacerse aquí si no estaban arriba
    try:
        import socketserver
        from http.server import SimpleHTTPRequestHandler
    except ImportError:
        print("ERROR: Asegúrate de tener Python instalado correctamente con sus librerías estándar.")
        exit(1)
        
    root = tk.Tk()
    server_app = VideoControlServer(root)
    root.protocol("WM_DELETE_WINDOW", server_app.on_closing)
    root.mainloop()