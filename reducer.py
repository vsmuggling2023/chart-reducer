import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import subprocess
import time
import struct

# --- CONFIGURACIÓN ---
INSTRUMENTOS = {
    'Single': 'Guitarra',
    'DoubleBass': 'Bajo',
    'Drums': 'Batería',
    'Keys': 'Teclado',
}

DIFICULTADES = ['Easy', 'Medium', 'Hard', 'Expert']

# Rangos de notas MIDI por dificultad (Clone Hero/Guitar Hero estándar)
RANGOS_NOTAS_MIDI = {
    'Expert': 96,  # 96-100
    'Hard': 84,    # 84-88
    'Medium': 72,  # 72-76
    'Easy': 60     # 60-64
}

NOMBRES_PISTA_MIDI = {
    'Single': 'PART GUITAR',
    'DoubleBass': 'PART BASS',
    'Drums': 'PART DRUMS',
    'Keys': 'PART KEYS',
}

# --- FUNCIONES MIDI ---
def escribir_variable_length(valor):
    """Convierte entero a formato variable length MIDI"""
    bytes_result = []
    bytes_result.append(valor & 0x7F)
    valor >>= 7
    while valor > 0:
        bytes_result.append((valor & 0x7F) | 0x80)
        valor >>= 7
    return bytes(reversed(bytes_result))

def leer_variable_length(data, pos):
    """Lee número de longitud variable"""
    value = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not (byte & 0x80):
            break
    return value, pos

def leer_midi_completo(ruta_archivo):
    """
    Lee archivo MIDI completo y separa las pistas.
    Retorna: (header_bytes, lista_pistas, dict_instrumentos_parseados, ticks_per_beat)
    """
    try:
        with open(ruta_archivo, "rb") as f:
            data = f.read()
        
        pos = 0
        
        # Leer header
        if data[pos:pos+4] != b"MThd":
            return None, None, None, 192
        
        pos += 4
        header_length = int.from_bytes(data[pos:pos+4], 'big')
        pos += 4
        header_bytes = data[pos-8:pos+header_length]
        
        format_type = int.from_bytes(data[pos:pos+2], 'big')
        num_tracks = int.from_bytes(data[pos+2:pos+4], 'big')
        ticks_per_beat = int.from_bytes(data[pos+4:pos+6], 'big')
        pos += header_length
        
        # Leer cada pista completa
        pistas = []
        instrumentos_parseados = {}
        
        while pos < len(data) - 8:
            if data[pos:pos+4] == b"MTrk":
                pos += 4
                track_length = int.from_bytes(data[pos:pos+4], 'big')
                pos += 4
                track_data = data[pos:pos+track_length]
                pos += track_length
                
                # Guardar pista completa (bytes originales)
                track_completo = b"MTrk" + struct.pack(">I", track_length) + track_data
                pistas.append(track_completo)
                
                # Parsear para identificar instrumento
                nombre_pista, notas = parsear_pista_midi(track_data, ticks_per_beat)
                
                # Identificar si es un instrumento conocido
                inst_code = None
                for code, nombre_midi in NOMBRES_PISTA_MIDI.items():
                    if nombre_pista and nombre_midi in nombre_pista.upper():
                        inst_code = code
                        break
                
                # Detectar y SEPARAR notas por dificultad
                if inst_code and notas:
                    # SEPARAR todas las notas por rango MIDI
                    notas_expert = [(t, n, d) for t, n, d in notas if 96 <= n <= 100]
                    notas_hard = [(t, n, d) for t, n, d in notas if 84 <= n <= 88]
                    notas_medium = [(t, n, d) for t, n, d in notas if 72 <= n <= 76]
                    notas_easy = [(t, n, d) for t, n, d in notas if 60 <= n <= 64]
                    notas_especiales = [(t, n) for t, n, d in notas if n < 60 or (n > 64 and n < 72) or (n > 76 and n < 84) or (n > 88 and n < 96) or n > 100]
                    
                    # Si tiene al menos Expert O alguna dificultad, procesar
                    if notas_expert or notas_hard or notas_medium or notas_easy:
                        if inst_code not in instrumentos_parseados:
                            instrumentos_parseados[inst_code] = {
                                'notas_especiales': notas_especiales  # PRESERVAR eventos especiales
                            }
                        
                        # Procesar Expert (siempre necesario para generar las otras)
                        if notas_expert:
                            from collections import defaultdict
                            notas_por_tick = defaultdict(list)
                            for tick, nota_midi, duracion in notas_expert:
                                fret = nota_midi - 96  # Expert usa 96-100
                                notas_por_tick[tick].append((fret, duracion))
                            
                            # Convertir a formato (tick, fret, duration)
                            notas_fret = []
                            for tick in sorted(notas_por_tick.keys()):
                                for fret, duracion in notas_por_tick[tick]:
                                    notas_fret.append((tick, fret, duracion))
                            
                            instrumentos_parseados[inst_code]['Expert'] = notas_fret
                        
                        # Si NO tiene Expert pero tiene otras dificultades, avisar
                        elif notas_hard or notas_medium or notas_easy:
                            # Este instrumento tiene dificultades pero no Expert
                            # No podemos regenerar sin Expert
                            pass
            else:
                pos += 1
        
        return header_bytes, pistas, instrumentos_parseados, ticks_per_beat
        
    except Exception as e:
        print(f"Error leyendo MIDI: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, 192

def parsear_pista_midi(track_data, ticks_per_beat):
    """
    Parsea una pista MIDI para extraer nombre y notas CON DURACIONES.
    Retorna: (nombre_pista, lista_notas_con_duracion)
    donde lista_notas_con_duracion = [(tick_inicio, nota_midi, duracion), ...]
    """
    nombre_pista = None
    notas_con_duracion = []
    
    # Trackear Note On activos para calcular duraciones
    notas_activas = {}  # {nota_midi: tick_inicio}
    
    pos = 0
    tiempo_absoluto = 0
    running_status = 0
    
    while pos < len(track_data):
        try:
            delta_time, pos = leer_variable_length(track_data, pos)
            tiempo_absoluto += delta_time
            
            if pos >= len(track_data):
                break
            
            status = track_data[pos]
            if status < 0x80:
                status = running_status
            else:
                pos += 1
                running_status = status
            
            # Note On
            if 0x90 <= status <= 0x9F:
                if pos + 1 < len(track_data):
                    note = track_data[pos]
                    velocity = track_data[pos + 1]
                    pos += 2
                    if velocity > 0:
                        # Registrar Note On
                        notas_activas[note] = tiempo_absoluto
                    else:
                        # Note On con velocity 0 = Note Off
                        if note in notas_activas:
                            tick_inicio = notas_activas[note]
                            duracion = tiempo_absoluto - tick_inicio
                            notas_con_duracion.append((tick_inicio, note, duracion))
                            del notas_activas[note]
            
            # Note Off
            elif 0x80 <= status <= 0x8F:
                if pos + 1 < len(track_data):
                    note = track_data[pos]
                    pos += 2
                    # Calcular duración
                    if note in notas_activas:
                        tick_inicio = notas_activas[note]
                        duracion = tiempo_absoluto - tick_inicio
                        notas_con_duracion.append((tick_inicio, note, duracion))
                        del notas_activas[note]
                else:
                    pos += 0
            elif 0xA0 <= status <= 0xBF:
                pos += 2 if pos + 1 < len(track_data) else 0
            elif 0xC0 <= status <= 0xDF:
                pos += 1 if pos < len(track_data) else 0
            elif 0xE0 <= status <= 0xEF:
                pos += 2 if pos + 1 < len(track_data) else 0
            
            # Meta events
            elif status == 0xFF:
                if pos < len(track_data):
                    meta_type = track_data[pos]
                    pos += 1
                    length, pos = leer_variable_length(track_data, pos)
                    
                    # Track Name (0x03)
                    if meta_type == 0x03 and length > 0:
                        try:
                            nombre_bytes = track_data[pos:pos+length]
                            nombre_pista = nombre_bytes.decode('latin-1', errors='ignore')
                        except:
                            pass
                    
                    pos += length
            elif status == 0xF0 or status == 0xF7:
                length, pos = leer_variable_length(track_data, pos)
                pos += length
            else:
                pos += 1
        except:
            pos += 1
    
    # Cerrar notas que quedaron abiertas (asignar duración mínima)
    for note, tick_inicio in notas_activas.items():
        duracion = max(10, tiempo_absoluto - tick_inicio)
        notas_con_duracion.append((tick_inicio, note, duracion))
    
    return nombre_pista, notas_con_duracion

def crear_pista_midi(nombre_pista, notas, base_nota, ticks_per_beat):
    """
    Crea una pista MIDI completa con las notas dadas.
    notas: lista de (tick, fret, duration) donde fret es 0-4
    base_nota: nota MIDI base (60 para Easy, 72 para Medium, etc.)
    """
    eventos = bytearray()
    
    # Track Name
    nombre_bytes = nombre_pista.encode('latin-1')
    eventos.extend(b'\x00\xFF\x03')  # Delta 0, Meta Event, Track Name
    eventos.extend(escribir_variable_length(len(nombre_bytes)))
    eventos.extend(nombre_bytes)
    
    # Ordenar notas por tick
    notas_ordenadas = sorted(notas, key=lambda x: x[0])
    
    ultimo_tick = 0
    for tick, fret, duration in notas_ordenadas:
        delta = tick - ultimo_tick
        nota_midi = base_nota + fret
        
        # Note On
        eventos.extend(escribir_variable_length(delta))
        eventos.append(0x90)  # Note On canal 0
        eventos.append(nota_midi)
        eventos.append(96)  # Velocity
        
        # Note Off
        dur = duration if duration > 0 else 10
        eventos.extend(escribir_variable_length(dur))
        eventos.append(0x80)  # Note Off canal 0
        eventos.append(nota_midi)
        eventos.append(0)
        
        ultimo_tick = tick + dur
    
    # End of Track
    eventos.extend(b'\x00\xFF\x2F\x00')
    
    # Construir pista completa con header MTrk
    track_completo = b"MTrk" + struct.pack(">I", len(eventos)) + bytes(eventos)
    
    return track_completo

def guardar_midi(ruta, header_bytes, pistas_originales, nuevas_pistas, num_tracks_total):
    """
    Guarda archivo MIDI con las pistas originales + nuevas pistas.
    """
    with open(ruta, 'wb') as f:
        # Escribir header con número actualizado de pistas
        f.write(b"MThd")
        f.write(struct.pack(">I", 6))  # Header length
        
        # Extraer format y division del header original
        format_type = int.from_bytes(header_bytes[8:10], 'big')
        division = header_bytes[12:14]
        
        f.write(struct.pack(">H", format_type))
        f.write(struct.pack(">H", num_tracks_total))
        f.write(division)
        
        # Escribir pistas originales
        for pista in pistas_originales:
            f.write(pista)
        
        # Escribir nuevas pistas
        for pista in nuevas_pistas:
            f.write(pista)

# --- PARSER CHART ---
def detectar_instrumentos_chart(lineas):
    """Detecta instrumentos en archivo .chart"""
    instrumentos = {}
    seccion_actual = None
    inst_actual = None
    diff_actual = None
    dentro = False
    
    for linea in lineas:
        linea = linea.strip()
        
        if linea == '{':
            dentro = True
            continue
        elif linea == '}':
            dentro = False
            seccion_actual = None
            inst_actual = None
            diff_actual = None
            continue
        
        if linea.startswith('[') and linea.endswith(']'):
            seccion = linea[1:-1]
            
            for diff in DIFICULTADES:
                for inst_code in INSTRUMENTOS.keys():
                    if seccion == f"{diff}{inst_code}":
                        seccion_actual = seccion
                        inst_actual = inst_code
                        diff_actual = diff
                        
                        if inst_code not in instrumentos:
                            instrumentos[inst_code] = {}
                        instrumentos[inst_code][diff] = []
                        break
        
        elif dentro and inst_actual and '=' in linea:
            partes = linea.split()
            if len(partes) >= 5 and partes[1] == '=' and partes[2] == 'N':
                try:
                    tick = int(partes[0])
                    fret = int(partes[3])
                    duration = int(partes[4])
                    instrumentos[inst_actual][diff_actual].append((tick, fret, duration))
                except:
                    continue
    
    return instrumentos

# --- REDUCCIÓN MEJORADA ---
def aplicar_reduccion_adaptativa(notas_expert, dificultad, ticks_per_beat, star_power_ticks=[]):
    """
    Reduce notas según dificultad con algoritmo ADAPTATIVO basado en densidad de Expert.
    
    - Hard: ~60-65% densidad, 5 botones, acordes máx 2 notas
    - Medium: ~50% densidad, 4 botones, notas simples
    - Easy: ~30% densidad, 3 botones, notas simples
    
    PRESERVA Star Power en sus posiciones originales.
    """
    from collections import defaultdict
    import math
    
    # Multiplicadores del espaciado mediano para cada dificultad
    # Valores más bajos = MÁS notas (filtro más permisivo)
    # Valores más altos = MENOS notas (filtro más estricto)
    SPACING_MULTIPLIER = {
        'Hard': 1.01,    # ~60-65% de notas (muy ligeramente más espaciado que Expert)
        'Medium': 2.00,  # ~50% de notas (doble espaciado)
        'Easy': 3.33     # ~30% de notas (triple espaciado)
    }
    
    # Máximo fret permitido (0=G, 1=R, 2=Y, 3=B, 4=O)
    MAX_FRET = {
        'Hard': 4,    # G,R,Y,B,O (5 botones)
        'Medium': 3,  # G,R,Y,B (4 botones)
        'Easy': 2     # G,R,Y (3 botones)
    }
    
    # Máximo de notas simultáneas (acordes)
    MAX_CHORD_SIZE = {
        'Hard': 2,    # Máximo 2 notas
        'Medium': 1,  # Solo notas simples
        'Easy': 1     # Solo notas simples
    }
    
    spacing_mult = SPACING_MULTIPLIER.get(dificultad, 1.0)
    limite_fret = MAX_FRET.get(dificultad, 4)
    max_chord = MAX_CHORD_SIZE.get(dificultad, 2)
    
    # Convertir star_power_ticks a set para búsqueda rápida
    star_power_set = set(star_power_ticks)
    
    # Agrupar por tick para manejar acordes
    notas_por_tick = defaultdict(list)
    for tick, fret, duracion in notas_expert:
        notas_por_tick[tick].append((fret, duracion))
    
    ticks_ordenados = sorted(notas_por_tick.keys())
    
    # CALCULAR ESPACIADO PROMEDIO en Expert
    if len(ticks_ordenados) < 2:
        # Si hay muy pocas notas, usar todo
        return notas_expert
    
    espaciados = []
    for i in range(len(ticks_ordenados) - 1):
        espaciado = ticks_ordenados[i + 1] - ticks_ordenados[i]
        if espaciado > 0:  # Ignorar notas simultáneas
            espaciados.append(espaciado)
    
    if not espaciados:
        return notas_expert
    
    # Usar mediana para ser más robusto contra outliers
    espaciados.sort()
    espaciado_mediano = espaciados[len(espaciados) // 2]
    
    # CALCULAR ESPACIADO MÍNIMO basado en multiplicador
    # Hard (1.01x): acepta notas casi tan juntas como Expert
    # Medium (2.0x): necesita el doble de espaciado
    # Easy (3.33x): necesita triple espaciado
    min_tick_diff = int(espaciado_mediano * spacing_mult)
    
    # Reducir por ticks
    notas_reducidas = []
    last_tick = -999999
    
    for tick in ticks_ordenados:
        # 1. Filtrar frets que cumplen el límite
        frets_validos = [(f, d) for f, d in notas_por_tick[tick] if f <= limite_fret]
        
        if not frets_validos:
            continue
        
        # 2. CRÍTICO: Si este tick tiene Star Power, SIEMPRE incluirlo
        es_star_power = tick in star_power_set
        
        # 3. Verificar espaciado mínimo (excepto para Star Power)
        if not es_star_power and (tick - last_tick < min_tick_diff):
            continue
        
        # 4. Reducir acordes si exceden el máximo
        if len(frets_validos) > max_chord:
            frets_validos = reducir_acorde(frets_validos, max_chord)
        
        # 5. Agregar notas del acorde reducido
        for fret, duration in frets_validos:
            notas_reducidas.append((tick, fret, duration))
        
        last_tick = tick
    
    return notas_reducidas

def reducir_acorde(notas, max_notas):
    """
    Reduce un acorde a máximo 'max_notas' notas.
    Estrategia GHWT: mantener las notas MÁS CERCANAS (consecutivas) entre sí.
    
    Esto asegura que acordes diferentes en Expert sigan siendo diferentes en Hard:
    - R Y O (1,2,4) → R Y (1,2) - las 2 más cercanas
    - R B O (1,3,4) → B O (3,4) - las 2 más cercanas
    - G Y B (0,2,3) → Y B (2,3) - las 2 más cercanas
    """
    if len(notas) <= max_notas:
        return notas
    
    # Ordenar por fret
    notas_ordenadas = sorted(notas, key=lambda x: x[0])
    
    if max_notas == 1:
        # Para notas simples: elegir la nota más baja (más fundamental)
        return [notas_ordenadas[0]]
    
    elif max_notas == 2:
        # Para acordes de 2: encontrar el PAR de notas más CERCANAS (consecutivas)
        # Esto mantiene acordes únicos y es más fácil de tocar
        
        if len(notas_ordenadas) == 2:
            return notas_ordenadas
        
        # Calcular separaciones entre cada par consecutivo
        mejor_par = None
        menor_separacion = float('inf')
        
        for i in range(len(notas_ordenadas) - 1):
            fret_a = notas_ordenadas[i][0]
            fret_b = notas_ordenadas[i + 1][0]
            separacion = fret_b - fret_a
            
            # Encontrar el par con menor separación (más cercano)
            if separacion < menor_separacion:
                menor_separacion = separacion
                mejor_par = [notas_ordenadas[i], notas_ordenadas[i + 1]]
        
        return mejor_par if mejor_par else notas_ordenadas[:2]
    
    else:
        # Para otros casos, mantener las primeras N notas
        return notas_ordenadas[:max_notas]

def crear_seccion_chart(nombre, notas):
    """Crea sección de chart"""
    if not notas:
        return ""
    
    texto = f'\n[{nombre}]\n{{\n'
    for tick, fret, duration in notas:
        texto += f'  {tick} = N {fret} {duration}\n'
    texto += '}\n'
    return texto

# --- INTERFAZ ---
class GHReducerApp:
    def __init__(self, master):
        self.master = master
        master.title("GH Chart Reducer v7.1 - REDUCCIÓN ADAPTATIVA MEJORADA")
        master.geometry("700x720")
        
        self.ruta_archivo = ""
        self.tipo_archivo = None
        self.contenido_chart = []
        self.midi_header = None
        self.midi_pistas = None
        self.instrumentos_disponibles = {}
        self.ticks_per_beat = 192
        
        # UI
        frame_archivo = tk.Frame(master)
        frame_archivo.pack(pady=10, padx=10, fill=tk.X)
        
        self.label_archivo = tk.Label(frame_archivo, text="Ningún archivo cargado", 
                                      wraplength=650, font=("Arial", 10))
        self.label_archivo.pack()
        
        self.btn_cargar = tk.Button(frame_archivo, text="📂 Cargar .chart / .mid", 
                                     command=self.cargar_archivo, 
                                     font=("Arial", 11, "bold"), bg="#2196F3", fg="white", pady=8)
        self.btn_cargar.pack(pady=8)
        
        frame_info = tk.LabelFrame(master, text="💡 Información", padx=10, pady=10)
        frame_info.pack(pady=5, padx=10, fill=tk.X)
        
        info_text = "✅ .mid → guarda como .mid (preserva VOCALS, Star Power ⭐ y tempos)\n✅ .chart → guarda como .chart\n✅ Reducción ADAPTATIVA: se ajusta automáticamente a la densidad de cada instrumento"
        tk.Label(frame_info, text=info_text, font=("Arial", 9), justify=tk.LEFT).pack()
        
        frame_inst = tk.LabelFrame(master, text="Instrumento a Reducir", padx=10, pady=10)
        frame_inst.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        tk.Label(frame_inst, text="Selecciona el instrumento:").pack()
        
        self.combo_inst = ttk.Combobox(frame_inst, state="disabled", width=45)
        self.combo_inst.pack(pady=5)
        
        tk.Label(frame_inst, text="Dificultades:").pack(pady=(10, 0))
        
        self.list_diffs = tk.Listbox(frame_inst, height=6)
        self.list_diffs.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.btn_generar = tk.Button(master, text="⚙️ Generar Dificultades (TODOS los instrumentos)", 
                                     command=self.generar_dificultades, state=tk.DISABLED,
                                     font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", pady=8)
        self.btn_generar.pack(pady=10)
        
        frame_log = tk.LabelFrame(master, text="Log", padx=5, pady=5)
        frame_log.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        self.text_log = tk.Text(frame_log, height=10, width=80, font=("Courier", 9))
        scroll = tk.Scrollbar(frame_log, command=self.text_log.yview)
        self.text_log.config(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_log.pack(fill=tk.BOTH, expand=True)
    
    def log(self, msg):
        self.text_log.insert(tk.END, msg + "\n")
        self.text_log.see(tk.END)
    
    def cargar_archivo(self):
        self.ruta_archivo = filedialog.askopenfilename(
            filetypes=[
                ("Archivos compatibles", "*.chart *.mid"),
                ("Chart Files", "*.chart"),
                ("MIDI Files", "*.mid")
            ]
        )
        
        if not self.ruta_archivo:
            return
        
        self.text_log.delete(1.0, tk.END)
        self.list_diffs.delete(0, tk.END)
        self.instrumentos_disponibles = {}
        
        self.label_archivo.config(text=f"📁 {os.path.basename(self.ruta_archivo)}")
        ext = os.path.splitext(self.ruta_archivo)[1].lower()
        
        if ext == '.mid':
            self.tipo_archivo = 'midi'
            self.log("🎵 Archivo MIDI detectado")
            self.log("Leyendo archivo completo (preservando TODO)...\n")
            
            self.midi_header, self.midi_pistas, self.instrumentos_disponibles, self.ticks_per_beat = leer_midi_completo(self.ruta_archivo)
            
            if not self.instrumentos_disponibles:
                self.log("❌ No se detectaron instrumentos")
                messagebox.showerror("Error", "No se detectaron instrumentos en el MIDI")
                return
            
            self.log(f"✅ Pistas originales preservadas: {len(self.midi_pistas)}")
            self.log(f"✅ Ticks per beat: {self.ticks_per_beat}")
            self.log("   (Incluye VOCALS, Star Power ⭐, tempos, eventos, etc.)\n")
            
            self.log("📊 Instrumentos detectados:")
            for inst_code, data in self.instrumentos_disponibles.items():
                nombre = INSTRUMENTOS.get(inst_code, inst_code)
                self.log(f"\n🎸 {nombre}:")
                
                # Verificar si tiene Expert
                if 'Expert' not in data:
                    self.log(f"   ⚠️ SIN EXPERT - No se puede regenerar (se necesita Expert)")
                    continue
                
                # Mostrar eventos especiales
                if 'notas_especiales' in data and data['notas_especiales']:
                    self.log(f"   ⭐ {len(data['notas_especiales'])} eventos especiales (Star Power, etc.)")
                
                for diff in DIFICULTADES:
                    if diff in data:
                        notas = data[diff]
                        ticks_unicos = len(set(n[0] for n in notas))
                        self.log(f"   ✅ {diff}: {ticks_unicos} notas detectadas")
                    else:
                        self.log(f"   ➖ {diff}: No existe (se generará)")
        
        elif ext == '.chart':
            self.tipo_archivo = 'chart'
            self.log("📄 Archivo .chart detectado\n")
            
            try:
                with open(self.ruta_archivo, 'r', encoding='utf-8') as f:
                    self.contenido_chart = f.readlines()
                
                self.instrumentos_disponibles = detectar_instrumentos_chart(self.contenido_chart)
                
                if not self.instrumentos_disponibles:
                    self.log("❌ No se detectaron instrumentos")
                    return
                
                self.log("📊 Instrumentos detectados:")
                for inst_code, diffs in self.instrumentos_disponibles.items():
                    nombre = INSTRUMENTOS.get(inst_code, inst_code)
                    self.log(f"\n🎸 {nombre}:")
                    for diff in DIFICULTADES:
                        if diff in diffs:
                            self.log(f"   ✅ {diff}: {len(diffs[diff])} notas")
                        else:
                            self.log(f"   ❌ {diff}: No existe")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                messagebox.showerror("Error", str(e))
                return
        
        # Actualizar UI
        if self.instrumentos_disponibles:
            lista_inst = []
            for inst_code in self.instrumentos_disponibles:
                nombre = INSTRUMENTOS.get(inst_code, inst_code)
                # Contar solo dificultades, no 'notas_especiales'
                num_diffs = len([k for k in self.instrumentos_disponibles[inst_code].keys() if k in DIFICULTADES])
                lista_inst.append(f"{nombre} ({num_diffs} dificultades)")
            
            self.combo_inst['values'] = lista_inst
            self.combo_inst.current(0)
            self.combo_inst.config(state="readonly")
            self.combo_inst.bind("<<ComboboxSelected>>", self.actualizar_diffs)
            self.actualizar_diffs()
            self.btn_generar.config(state=tk.NORMAL)
    
    def actualizar_diffs(self, event=None):
        self.list_diffs.delete(0, tk.END)
        
        idx = self.combo_inst.current()
        inst_code = list(self.instrumentos_disponibles.keys())[idx]
        data = self.instrumentos_disponibles[inst_code]
        
        for diff in DIFICULTADES:
            if diff in data:
                ticks_unicos = len(set(n[0] for n in data[diff]))
                self.list_diffs.insert(tk.END, f"✅ {diff}: {ticks_unicos} notas")
            else:
                self.list_diffs.insert(tk.END, f"❌ {diff}: No existe")
    
    def generar_dificultades(self):
        """Genera dificultades para TODOS los instrumentos (REGENERA si ya existen)"""
        if not self.instrumentos_disponibles:
            return
        
        self.log(f"\n\n{'='*60}")
        self.log("⚙️ GENERANDO DIFICULTADES PARA TODOS LOS INSTRUMENTOS")
        self.log(f"{'='*60}\n")
        
        # Procesar CADA instrumento
        instrumentos_procesados = {}
        
        for inst_code, data in self.instrumentos_disponibles.items():
            inst_nombre = INSTRUMENTOS.get(inst_code, inst_code)
            
            if 'Expert' not in data:
                self.log(f"⚠️ {inst_nombre}: Sin Expert, omitiendo...")
                continue
            
            notas_expert = data['Expert']
            ticks_expert = len(set(n[0] for n in notas_expert))
            
            # Extraer ticks de Star Power (nota MIDI 116)
            star_power_ticks = []
            if 'notas_especiales' in data:
                star_power_ticks = [tick for tick, nota in data['notas_especiales'] if nota == 116]
            
            self.log(f"\n🎸 {inst_nombre}:")
            self.log(f"   Expert: {ticks_expert} notas")
            if star_power_ticks:
                self.log(f"   ⭐ Star Power: {len(star_power_ticks)} secciones")
            
            # CRÍTICO: SIEMPRE generar todas las dificultades (regenerar si existen)
            nuevas_diffs = {}
            for diff in ['Hard', 'Medium', 'Easy']:
                notas = aplicar_reduccion_adaptativa(notas_expert, diff, self.ticks_per_beat, star_power_ticks)
                nuevas_diffs[diff] = notas
                ticks_generados = len(set(n[0] for n in notas))
                porcentaje = int((ticks_generados / ticks_expert) * 100) if ticks_expert > 0 else 0
                
                estado = "regenerada" if diff in data else "generada"
                self.log(f"   ✅ {diff}: {ticks_generados} notas ({porcentaje}% de Expert) - {estado}")
            
            instrumentos_procesados[inst_code] = nuevas_diffs
        
        if not instrumentos_procesados:
            messagebox.showinfo("Info", "No hay instrumentos con Expert para procesar")
            return
        
        # Guardar según tipo
        if self.tipo_archivo == 'midi':
            ext_salida = ".mid"
            tipo_desc = "MIDI Files"
        else:
            ext_salida = ".chart"
            tipo_desc = "Chart Files"
        
        ruta_salida = filedialog.asksaveasfilename(
            defaultextension=ext_salida,
            filetypes=[(tipo_desc, f"*{ext_salida}")],
            initialfile=f"REDUCED_{os.path.splitext(os.path.basename(self.ruta_archivo))[0]}{ext_salida}"
        )
        
        if not ruta_salida:
            return
        
        try:
            if self.tipo_archivo == 'midi':
                self.guardar_como_midi_multi(ruta_salida, instrumentos_procesados)
            else:
                self.guardar_como_chart_multi(ruta_salida, instrumentos_procesados)
            
            self.log(f"\n{'='*60}")
            self.log(f"💾 GUARDADO: {os.path.basename(ruta_salida)}")
            self.log(f"{'='*60}\n")
            messagebox.showinfo("✅ Éxito", f"Dificultades generadas para todos los instrumentos:\n{ruta_salida}")
        except Exception as e:
            self.log(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"No se pudo guardar:\n{e}")
    
    def guardar_como_midi_multi(self, ruta, instrumentos_procesados):
        """Guarda MIDI procesando TODOS los instrumentos"""
        self.log("\n📝 Generando archivo MIDI completo...")
        
        # Índices de pistas que corresponden a instrumentos procesados
        pistas_procesadas_indices = set()
        pistas_finales = []
        
        # Primera pasada: identificar y procesar instrumentos
        for idx, pista_original in enumerate(self.midi_pistas):
            # Parsear nombre de esta pista
            nombre, _ = parsear_pista_midi(pista_original[8:], self.ticks_per_beat)
            
            # Verificar si esta pista corresponde a algún instrumento procesado
            pista_reemplazada = False
            
            for inst_code, nuevas_diffs in instrumentos_procesados.items():
                nombre_pista_buscado = NOMBRES_PISTA_MIDI.get(inst_code, "PART GUITAR")
                
                if nombre and nombre_pista_buscado in nombre.upper():
                    # Marcar esta pista como procesada
                    pistas_procesadas_indices.add(idx)
                    
                    # Solo usar las dificultades REGENERADAS (no combinar con existentes)
                    todas_dificultades = {}
                    
                    # Siempre incluir Expert original
                    if 'Expert' in self.instrumentos_disponibles[inst_code]:
                        todas_dificultades['Expert'] = self.instrumentos_disponibles[inst_code]['Expert']
                    
                    # Agregar dificultades REGENERADAS (Hard, Medium, Easy)
                    for diff, notas in nuevas_diffs.items():
                        todas_dificultades[diff] = notas
                    
                    # Obtener eventos especiales
                    eventos_especiales = self.instrumentos_disponibles[inst_code].get('notas_especiales', [])
                    
                    # Crear nueva pista con TODAS las dificultades + eventos especiales
                    pista_nueva = self.crear_pista_multidificultad(nombre_pista_buscado, todas_dificultades, eventos_especiales)
                    pistas_finales.append(pista_nueva)
                    pista_reemplazada = True
                    
                    inst_nombre = INSTRUMENTOS.get(inst_code, inst_code)
                    self.log(f"   ✅ Pista '{nombre}' ({inst_nombre}) actualizada")
                    break
            
            # Si esta pista NO fue procesada, mantenerla original
            if not pista_reemplazada:
                pistas_finales.append(pista_original)
        
        # Guardar MIDI completo
        num_total = len(pistas_finales)
        guardar_midi(ruta, self.midi_header, pistas_finales, [], num_total)
        
        self.log(f"\n✅ MIDI guardado con {num_total} pistas")
        self.log(f"   Instrumentos actualizados: {len(instrumentos_procesados)}")
    
    def crear_pista_multidificultad(self, nombre_pista, dificultades_dict, eventos_especiales=[]):
        """
        Crea una pista MIDI con múltiples dificultades + eventos especiales.
        dificultades_dict: {'Expert': [(tick, fret, dur), ...], 'Hard': [...], ...}
        eventos_especiales: [(tick, nota_midi), ...] - Star Power, etc.
        """
        eventos = bytearray()
        
        # Track Name
        nombre_bytes = nombre_pista.encode('latin-1')
        eventos.extend(b'\x00\xFF\x03')
        eventos.extend(escribir_variable_length(len(nombre_bytes)))
        eventos.extend(nombre_bytes)
        
        # Recopilar TODOS los eventos MIDI con tick absoluto
        todos_eventos = []
        
        # 1. Agregar eventos de todas las dificultades
        for diff, notas in dificultades_dict.items():
            base_nota = RANGOS_NOTAS_MIDI.get(diff, 96)
            for tick, fret, duration in notas:
                nota_midi = base_nota + fret
                dur = duration if duration > 0 else 10
                
                # Note On y Note Off como eventos separados
                todos_eventos.append((tick, 'on', nota_midi))
                todos_eventos.append((tick + dur, 'off', nota_midi))
        
        # 2. Agregar eventos especiales (Star Power, etc.)
        for tick, nota_midi in eventos_especiales:
            dur = 10  # Duración mínima para eventos especiales
            todos_eventos.append((tick, 'on', nota_midi))
            todos_eventos.append((tick + dur, 'off', nota_midi))
        
        # CRÍTICO: Ordenar TODOS los eventos por tick absoluto
        # Si hay empate en tick, Note Off va antes que Note On
        todos_eventos.sort(key=lambda x: (x[0], x[1] == 'on'))
        
        # Generar eventos MIDI con deltas correctos
        ultimo_tick = 0
        for tick_abs, tipo, nota_midi in todos_eventos:
            delta = tick_abs - ultimo_tick
            
            if tipo == 'on':
                # Note On
                eventos.extend(escribir_variable_length(delta))
                eventos.append(0x90)
                eventos.append(nota_midi)
                eventos.append(96)
            else:
                # Note Off
                eventos.extend(escribir_variable_length(delta))
                eventos.append(0x80)
                eventos.append(nota_midi)
                eventos.append(0)
            
            ultimo_tick = tick_abs
        
        # End of Track
        eventos.extend(b'\x00\xFF\x2F\x00')
        
        # Construir pista completa
        track_completo = b"MTrk" + struct.pack(">I", len(eventos)) + bytes(eventos)
        
        return track_completo
    
    def guardar_como_chart_multi(self, ruta, instrumentos_procesados):
        """Guarda como .chart con TODOS los instrumentos procesados"""
        with open(ruta, 'w', encoding='utf-8') as f:
            f.writelines(self.contenido_chart)
            
            for inst_code, nuevas_diffs in instrumentos_procesados.items():
                for diff, notas in nuevas_diffs.items():
                    seccion = f"{diff}{inst_code}"
                    f.write(crear_seccion_chart(seccion, notas))

if __name__ == "__main__":
    root = tk.Tk()
    app = GHReducerApp(root)
    root.mainloop()