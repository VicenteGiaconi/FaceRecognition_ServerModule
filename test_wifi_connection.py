import socket
import time

def get_local_ip():
    """Obtiene la IP local de la PC"""
    try:
        # Crear un socket temporal para obtener la IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        return None

def test_server():
    """Prueba el servidor TCP para WebSocket"""
    
    print("=" * 70)
    print("TEST DE SERVIDOR WEBSOCKET PARA QUEST PRO (WIFI)")
    print("=" * 70)
    
    # Obtener IP local
    local_ip = get_local_ip()
    if not local_ip:
        print("✗ No se pudo obtener la IP local")
        return
    
    print(f"\n✓ IP local detectada: {local_ip}")
    print(f"\nCONFIGURACIÓN EN UNITY:")
    print(f"  WebSocketSender > Server IP: {local_ip}")
    print(f"  WebSocketSender > Server Port: 8765")
    print("=" * 70)
    
    # Iniciar servidor
    port = 8765
    
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', port))
        server.listen(1)
        
        print(f"\n✓ Servidor escuchando en {local_ip}:{port}")
        print("\nESPERANDO CONEXIÓN DESDE QUEST PRO...")
        print("(Presiona Ctrl+C para salir)")
        print("-" * 70)
        
        # Timeout de 60 segundos
        server.settimeout(60)
        
        try:
            client, address = server.accept()
            print(f"\n✓✓✓ CONEXIÓN RECIBIDA DE: {address}")
            print(f"IP del Quest Pro: {address[0]}")
            print(f"Puerto: {address[1]}")
            
            # Recibir datos
            print("\nRecibiendo datos...")
            data = b""
            client.settimeout(10)
            
            while True:
                try:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                except socket.timeout:
                    break
            
            client.close()
            
            if data:
                print(f"\n✓ Datos recibidos: {len(data)} bytes")
                
                # Intentar parsear JSON
                try:
                    import json
                    json_data = json.loads(data.decode('utf-8'))
                    
                    print("\n✓✓✓ JSON VÁLIDO RECIBIDO ✓✓✓")
                    print("\nRESUMEN:")
                    
                    metadata = json_data.get('metadata', {})
                    print(f"  Timestamp: {metadata.get('timestamp', 'N/A')}")
                    print(f"  Duración: {metadata.get('duration', 0):.2f}s")
                    print(f"  Puntos de datos: {metadata.get('dataPoints', 0)}")
                    print(f"  Parpadeos: {metadata.get('totalBlinks', 0)}")
                    
                    stats = json_data.get('statistics', {})
                    if stats:
                        print("\n  ESTADÍSTICAS:")
                        for metric, values in stats.items():
                            avg = values.get('avg', 0)
                            print(f"    {metric}: {avg*100:.1f}%")
                    
                    print("\n✓✓✓ CONEXIÓN WIFI FUNCIONANDO PERFECTAMENTE ✓✓✓")
                    
                except json.JSONDecodeError as e:
                    print(f"\n✗ Error parseando JSON: {e}")
                    print(f"Primeros 200 caracteres: {data[:200]}")
            else:
                print("\n✗ No se recibieron datos")
                
        except socket.timeout:
            print("\n✗ TIMEOUT - No se recibió conexión en 60 segundos")
            print("\nPOSIBLES CAUSAS:")
            print("1. Quest Pro no está en la misma red WiFi")
            print("2. La IP en Unity no es correcta")
            print("3. Firewall bloqueando el puerto 8765")
            print("4. No presionaste botón B para detener la grabación")
            
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"\n✗ El puerto {port} ya está en uso")
            print("Cierra el dashboard de Python primero")
        else:
            print(f"\n✗ Error: {e}")
    except KeyboardInterrupt:
        print("\n\nTest interrumpido por usuario")
    finally:
        server.close()
        print("\n" + "=" * 70)

if __name__ == "__main__":
    test_server()