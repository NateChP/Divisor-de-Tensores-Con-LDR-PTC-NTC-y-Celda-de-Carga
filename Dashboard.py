import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import queue
from collections import deque
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

MAX_PUNTOS = 100 


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
            self.ser = serial.Serial(self.puerto, self.baudrate, timeout=1)
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
        self.title("Dashboard de Sensores - LDR / NTC / PTC")
        self.geometry("950x650")

        self.cola = queue.Queue()
        self.hilo_serial = None

        # Historial para las gráficas (ahora 2 gráficas: Luz y Temperatura)
        self.hist_ldr = deque(maxlen=MAX_PUNTOS)
        self.hist_ntc = deque(maxlen=MAX_PUNTOS)

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
            ("LDR (ADC)", "ldr_adc"),
            ("LDR (V)", "ldr_v"),
            ("R_LDR (Ω)", "r_ldr"),
            ("NTC (ADC)", "ntc_adc"),
            ("NTC (V)", "ntc_v"),
            ("Temp NTC (°C)", "temp"),
            ("PTC (ADC)", "ptc_adc"),
            ("PTC (V)", "ptc_v"),
            ("R_PTC (Ω)", "r_ptc"),
        ]

        for i, (texto, clave) in enumerate(etiquetas):
            fila, col = divmod(i, 3)
            cont = ttk.LabelFrame(marco, text=texto, padding=6)
            cont.grid(row=fila, column=col, padx=5, pady=5, sticky="nsew")
            var = tk.StringVar(value="--")
            self.vars_valores[clave] = var
            ttk.Label(cont, textvariable=var, font=("Consolas", 14, "bold")).pack()

        for c in range(3):
            marco.grid_columnconfigure(c, weight=1)

    def _crear_graficas(self):
        marco = ttk.Frame(self, padding=10)
        marco.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(8, 4), dpi=90)
        self.ax_luz = self.fig.add_subplot(1, 2, 1)
        self.ax_temp = self.fig.add_subplot(1, 2, 2)

        self.ax_luz.set_title("LDR (V)")
        self.ax_temp.set_title("NTC (°C)")

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
        partes = linea.split(",")
        if len(partes) != 9:
            return  

        try:
            (
                ldr_adc, ldr_v, r_ldr,
                ntc_adc, ntc_v, temp,
                ptc_adc, ptc_v, r_ptc,
            ) = [float(x) for x in partes]
        except ValueError:
            return

        self.vars_valores["ldr_adc"].set(f"{ldr_adc:.0f}")
        self.vars_valores["ldr_v"].set(f"{ldr_v:.3f} V")
        self.vars_valores["r_ldr"].set(f"{r_ldr:.0f}")
        self.vars_valores["ntc_adc"].set(f"{ntc_adc:.0f}")
        self.vars_valores["ntc_v"].set(f"{ntc_v:.3f} V")
        self.vars_valores["temp"].set(f"{temp:.2f} °C")
        self.vars_valores["ptc_adc"].set(f"{ptc_adc:.0f}")
        self.vars_valores["ptc_v"].set(f"{ptc_v:.3f} V")
        self.vars_valores["r_ptc"].set(f"{r_ptc:.0f}")

        self.hist_ldr.append(ldr_v)
        self.hist_ntc.append(temp)

        self._redibujar_graficas()

    def _redibujar_graficas(self):
        self.ax_luz.clear()
        self.ax_luz.set_title("LDR (V)")
        self.ax_luz.plot(list(self.hist_ldr), color="orange")

        self.ax_temp.clear()
        self.ax_temp.set_title("NTC (°C)")
        self.ax_temp.plot(list(self.hist_ntc), color="red")

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