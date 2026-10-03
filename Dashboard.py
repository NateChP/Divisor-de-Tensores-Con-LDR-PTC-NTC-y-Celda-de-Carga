import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
from collections import deque
import math

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    messagebox.showerror("Error crítico", "Falta instalar la librería pyserial. Ejecuta 'pip install pyserial' en tu terminal.")
    exit(1)

MAX_PUNTOS = 100  # Cantidad de puntos guardados para las gráficas


class LectorSerial(threading.Thread):
    """Hilo que lee continuamente el puerto serial sin bloquear la GUI."""

    def __init__(self, puerto, baudrate, cola_salida):
        super().__init__(daemon=True)
        self.puerto = puerto
        self.baudrate = baudrate
        self.cola_salida = cola_salida
        self._detener = threading.Event()
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.puerto, self.baudrate, timeout=3)
        except Exception as e:
            self.cola_salida.put(("error", str(e)))
            return

        while not self._detener.is_set():
            try:
                linea = self.ser.readline().decode("utf-8", errors="ignore").strip()
                if linea:
                    self.cola_salida.put(("dato", linea))
            except Exception as e:
                self.cola_salida.put(("error", str(e)))
                break

    def detener(self):
        self._detener.set()
        if self.ser and self.ser.is_open:
            self.ser.close()


class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dashboard de Sensores - LDR / NTC / PTC / Peso")
        self.geometry("1100x750")

        self.cola = queue.Queue()
        self.hilo_serial = None

        # Historial para las gráficas de los 4 sensores
        self.hist_ldr = deque(maxlen=MAX_PUNTOS)
        self.hist_ntc = deque(maxlen=MAX_PUNTOS)
        self.hist_ptc = deque(maxlen=MAX_PUNTOS)
        self.hist_peso = deque(maxlen=MAX_PUNTOS)

        self._crear_barra_conexion()
        self._crear_paneles_valores()
        self._crear_graficas()

        self.after(100, self._procesar_cola)

    def _crear_barra_conexion(self):
        marco = ttk.Frame(self, padding=8)
        marco.pack(fill="x")

        ttk.Label(marco, text="Puerto:").pack(side="left")
        self.combo_puertos = ttk.Combobox(marco, width=15, state="readonly")
        self.combo_puertos.pack(side="left", padx=5)
        self._actualizar_puertos()

        ttk.Button(marco, text="Refrescar", command=self._actualizar_puertos).pack(
            side="left", padx=5
        )

        ttk.Label(marco, text="Baudrate:").pack(side="left", padx=(15, 0))
        self.combo_baud = ttk.Combobox(
            marco, width=10, state="readonly", values=["9600", "115200"]
        )
        self.combo_baud.set("115200")
        self.combo_baud.pack(side="left", padx=5)

        self.btn_conectar = ttk.Button(
            marco, text="Conectar", command=self._alternar_conexion
        )
        self.btn_conectar.pack(side="left", padx=15)

        self.lbl_estado = ttk.Label(marco, text="Desconectado", foreground="red")
        self.lbl_estado.pack(side="left", padx=10)

    def _crear_paneles_valores(self):
        marco = ttk.Frame(self, padding=10)
        marco.pack(fill="x")

        self.vars_valores = {}
        etiquetas = [
            ("LDR (V)", "ldr_v"),
            ("R_LDR (Ω)", "r_ldr"),
            ("R_NTC (Ω)", "r_ntc"),
            ("R_PTC (Ω)", "r_ptc"),
            ("Peso (g)", "peso"),
            ("LED indicador", "led"),
        ]

        self.labels_valores = {}
        for i, (texto, clave) in enumerate(etiquetas):
            fila, col = divmod(i, 3)
            cont = ttk.LabelFrame(marco, text=texto, padding=8)
            cont.grid(row=fila, column=col, padx=8, pady=5, sticky="nsew")
            var = tk.StringVar(value="--")
            self.vars_valores[clave] = var
            lbl = ttk.Label(cont, textvariable=var, font=("Consolas", 14, "bold"))
            lbl.pack()
            self.labels_valores[clave] = lbl

        for c in range(3):
            marco.grid_columnconfigure(c, weight=1)

    def _crear_graficas(self):
        marco = ttk.Frame(self, padding=10)
        marco.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(10, 6), dpi=90)
        self.ax_ldr = self.fig.add_subplot(2, 2, 1)
        self.ax_ntc = self.fig.add_subplot(2, 2, 2)
        self.ax_ptc = self.fig.add_subplot(2, 2, 3)
        self.ax_peso = self.fig.add_subplot(2, 2, 4)

        self.ax_ldr.set_title("LDR (V)")
        self.ax_ntc.set_title("R_NTC (Ω)")
        self.ax_ptc.set_title("R_PTC (Ω)")
        self.ax_peso.set_title("Peso (g)")

        self.canvas = FigureCanvasTkAgg(self.fig, master=marco)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _actualizar_puertos(self):
        puertos = [p.device for p in serial.tools.list_ports.comports()]
        self.combo_puertos["values"] = puertos
        if puertos:
            self.combo_puertos.set(puertos[0])

    def _alternar_conexion(self):
        if self.hilo_serial is None:
            puerto = self.combo_puertos.get()
            baud = int(self.combo_baud.get())
            if not puerto:
                messagebox.showwarning("Aviso", "Selecciona un puerto serial")
                return
            self.hilo_serial = LectorSerial(puerto, baud, self.cola)
            self.hilo_serial.start()
            self.btn_conectar.config(text="Desconectar")
            self.lbl_estado.config(text=f"Conectado a {puerto}", foreground="green")
        else:
            self.hilo_serial.detener()
            self.hilo_serial = None
            self.btn_conectar.config(text="Conectar")
            self.lbl_estado.config(text="Desconectado", foreground="red")

    def _procesar_cola(self):
        try:
            while True:
                tipo, contenido = self.cola.get_nowait()
                if tipo == "dato":
                    self._actualizar_valores(contenido)
                elif tipo == "error":
                    messagebox.showerror("Error de conexión", contenido)
                    self._alternar_conexion()
        except queue.Empty:
            pass
        self.after(100, self._procesar_cola)

    def _actualizar_valores(self, linea):
        linea = linea.lstrip("> ").strip()

        if "Iniciando" in linea or "Verificando" in linea or "listo" in linea or "setup" in linea:
            return

        partes = linea.split(",")
        if len(partes) != 7:
            return  

        try:
            partes_limpias = [x.strip().replace(",", ".") for x in partes]
            (
                ldr_v, r_ldr,
                r_ntc,
                ptc_v, r_ptc,
                peso, led_estado,
            ) = [float(x) for x in partes_limpias]
        except ValueError:
            return

        # Validación de valores nulos o infinitos (NaN / Inf)
        valido_ldr = not (math.isnan(ldr_v) or math.isinf(ldr_v))
        valido_ntc = not (math.isnan(r_ntc) or math.isinf(r_ntc))
        valido_ptc = not (math.isnan(r_ptc) or math.isinf(r_ptc))
        valido_peso = not (math.isnan(peso) or math.isinf(peso))

        # Actualizar etiquetas de texto
        self.vars_valores["ldr_v"].set(f"{ldr_v:.3f} V" if valido_ldr else "Error")
        self.vars_valores["r_ldr"].set(f"{r_ldr:.0f}" if valido_ldr else "Error")
        self.vars_valores["r_ntc"].set(f"{r_ntc:.0f} Ω" if valido_ntc else "Error")
        self.vars_valores["r_ptc"].set(f"{r_ptc:.0f} Ω" if valido_ptc else "Error")
        self.vars_valores["peso"].set(f"{peso:.2f} g" if valido_peso else "Error")

        if led_estado >= 1:
            self.vars_valores["led"].set("ENCENDIDO")
            self.labels_valores["led"].config(foreground="green")
        else:
            self.vars_valores["led"].set("APAGADO")
            self.labels_valores["led"].config(foreground="gray")

        # Agregar al historial de las gráficas
        if valido_ldr: self.hist_ldr.append(ldr_v)
        if valido_ntc: self.hist_ntc.append(r_ntc)
        if valido_ptc: self.hist_ptc.append(r_ptc)
        if valido_peso: self.hist_peso.append(peso)

        self._redibujar_graficas(valido_ldr, valido_ntc, valido_ptc, valido_peso)

    def _redibujar_graficas(self, v_ldr, v_ntc, v_ptc, v_peso):
        # Gráfica LDR
        self.ax_ldr.clear()
        self.ax_ldr.set_title("LDR (V)")
        if v_ldr and len(self.hist_ldr) > 0:
            self.ax_ldr.plot(list(self.hist_ldr), color="orange")
        else:
            self.ax_ldr.text(0.5, 0.5, "No conectado /\nMal conectado", horizontalalignment='center', verticalalignment='center', transform=self.ax_ldr.transAxes, color='red', fontsize=11, fontweight='bold')

        # Gráfica R_NTC
        self.ax_ntc.clear()
        self.ax_ntc.set_title("R_NTC (Ω)")
        if v_ntc and len(self.hist_ntc) > 0:
            self.ax_ntc.plot(list(self.hist_ntc), color="red")
        else:
            self.ax_ntc.text(0.5, 0.5, "No conectado /\nMal conectado", horizontalalignment='center', verticalalignment='center', transform=self.ax_ntc.transAxes, color='red', fontsize=11, fontweight='bold')

        # Gráfica PTC
        self.ax_ptc.clear()
        self.ax_ptc.set_title("R_PTC (Ω)")
        if v_ptc and len(self.hist_ptc) > 0:
            self.ax_ptc.plot(list(self.hist_ptc), color="purple")
        else:
            self.ax_ptc.text(0.5, 0.5, "No conectado /\nMal conectado", horizontalalignment='center', verticalalignment='center', transform=self.ax_ptc.transAxes, color='red', fontsize=11, fontweight='bold')

        # Gráfica Peso
        self.ax_peso.clear()
        self.ax_peso.set_title("Peso (g)")
        if v_peso and len(self.hist_peso) > 0:
            self.ax_peso.plot(list(self.hist_peso), color="blue")
        else:
            self.ax_peso.text(0.5, 0.5, "No conectado /\nMal conectado", horizontalalignment='center', verticalalignment='center', transform=self.ax_peso.transAxes, color='red', fontsize=11, fontweight='bold')

        self.fig.tight_layout()
        self.canvas.draw()

    def on_close(self):
        if self.hilo_serial:
            self.hilo_serial.detener()
        self.destroy()


if __name__ == "__main__":
    app = Dashboard()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
