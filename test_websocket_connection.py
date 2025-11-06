import socket
import json

def test_server():
    """Script de prueba para verificar que el servidor funciona"""
    
    # Configurar servidor
    port = 8765
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', port))
        server.listen(1)
        
        # Obtener IP local
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        print("="*60)
        print("SERVIDOR DE PRUEBA INICIADO")
        print("="*60)
        print(f"Escuchando en: {local_ip}:{port}")
        print(f"\nConfigura esta IP en Unity:")
        print(f"  Server IP: {local_ip}")
        print(f"  Server Port: {port}")
        print("\nEsperando conexión desde Quest Pro...")
        print("Presiona Ctrl+C para salir")
        print("="*60)
        
        while True:
            client, address = server.accept()
            print(f"\n✓ Conexión recibida de: {address}")
            
            # Recibir datos
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            client.close()
            
            if data:
                print(f"✓ Datos recibidos: {len(data)} bytes")
                
                # Intentar parsear JSON
                try:
                    json_data = json.loads(data.decode('utf-8'))
                    print("✓ JSON válido recibido")
                    print("\nMetadata:")
                    metadata = json_data.get('metadata', {})
                    for key, value in metadata.items():
                        print(f"  {key}: {value}")
                    
                    print("\nEstadísticas:")
                    stats = json_data.get('statistics', {})
                    for metric, values in stats.items():
                        print(f"  {metric}: avg={values.get('avg', 0):.3f}")
                    
                    raw_data = json_data.get('rawData', [])
                    print(f"\nPuntos de datos raw: {len(raw_data)}")
                    
                except json.JSONDecodeError as e:
                    print(f"✗ Error al parsear JSON: {e}")
                    print(f"Datos recibidos (primeros 200 chars): {data[:200]}")
            else:
                print("✗ No se recibieron datos")
            
            print("\nEsperando siguiente conexión...")
            print("-"*60)
            
    except KeyboardInterrupt:
        print("\n\nServidor detenido por el usuario")
    except Exception as e:
        print(f"\n✗ Error: {e}")
    finally:
        server.close()

if __name__ == "__main__":
    test_server()