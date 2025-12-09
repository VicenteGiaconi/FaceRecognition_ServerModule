import subprocess
import sys

# Ruta de ADB - AJUSTA ESTA RUTA
ADB_PATH = r'C:\Program Files\Unity\Hub\Editor\6000.0.47f1\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe'

print("=== TEST DE CONEXIÓN ADB ===")
print(f"Usando ADB: {ADB_PATH}\n")

# Test 1: Verificar dispositivos
print("1. Verificando dispositivos conectados...")
try:
    result = subprocess.run([ADB_PATH, 'devices'], 
                          capture_output=True, 
                          text=True, 
                          timeout=5)
    print(f"Salida:\n{result.stdout}")
    
    if "device" in result.stdout and "unauthorized" not in result.stdout:
        print("✓ Dispositivo conectado y autorizado\n")
    else:
        print("✗ Dispositivo no autorizado o no conectado\n")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}\n")
    sys.exit(1)

# Test 2: Limpiar logcat
print("2. Limpiando logcat anterior...")
try:
    subprocess.run([ADB_PATH, 'logcat', '-c'], timeout=5)
    print("✓ Logcat limpiado\n")
except Exception as e:
    print(f"✗ Error: {e}\n")

# Test 3: Leer logcat en tiempo real
print("3. Leyendo logcat en tiempo real...")
print("   Filtrando por Unity:D")
print("   Presiona Ctrl+C para detener\n")
print("-" * 60)

try:
    process = subprocess.Popen(
        [ADB_PATH, 'logcat', '-s', 'Unity:D'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        bufsize=1
    )
    
    line_count = 0
    facial_data_count = 0
    
    for line in process.stdout:
        line_count += 1
        
        # Mostrar todas las líneas
        print(f"[{line_count}] {line.strip()}")
        
        # Contar líneas con FACIAL_DATA
        if '[FACIAL_DATA]' in line:
            facial_data_count += 1
            print(f"    ^^^ FACIAL_DATA DETECTADO (total: {facial_data_count}) ^^^")
        
        # Detener después de 50 líneas para el test
        if line_count >= 50:
            print("\n" + "=" * 60)
            print(f"Test completado: {line_count} líneas leídas")
            print(f"Datos faciales encontrados: {facial_data_count}")
            
            if facial_data_count > 0:
                print("✓✓✓ CONEXIÓN FUNCIONANDO CORRECTAMENTE ✓✓✓")
            else:
                print("✗✗✗ NO SE DETECTARON DATOS FACIALES ✗✗✗")
                print("\nPosibles causas:")
                print("1. La app no está grabando (presiona botón A en Quest Pro)")
                print("2. RealtimeDataTransmitter no está enviando datos")
                print("3. El tag [FACIAL_DATA] está mal escrito en Unity")
            break
            
except KeyboardInterrupt:
    print("\n\nTest interrumpido por usuario")
    print(f"Líneas leídas: {line_count}")
    print(f"Datos faciales encontrados: {facial_data_count}")
except Exception as e:
    print(f"\n✗ Error durante lectura: {e}")
finally:
    if 'process' in locals():
        process.terminate()

print("\n=== FIN DEL TEST ===")