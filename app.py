import os
import io
import shutil
import json
import re
import base64
import threading
import requests
from datetime import datetime
import customtkinter as ctk
from PIL import Image, ImageTk
import img2pdf

# Configuración de tema
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"

# --- VENTANA EMERGENTE DE EDICIÓN Y VERIFICACIÓN MANUSCRITA ---
class EditDialog(ctk.CTkToplevel):
    def __init__(self, parent, image_path, data, on_save_callback):
        super().__init__(parent)
        self.title("✏ Editar y Verificar Reporte - AncaScanner Pro")
        self.geometry("950x600")
        self.minsize(800, 500)
        self.grab_set()

        self.image_path = image_path
        self.data = data
        self.on_save_callback = on_save_callback

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # Panel Izquierdo: Foto
        frame_img = ctk.CTkFrame(self, fg_color="#111827", corner_radius=10)
        frame_img.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        try:
            pil_img = Image.open(image_path)
            pil_img.thumbnail((500, 550))
            self.tk_img = ImageTk.PhotoImage(pil_img)
            lbl_img = ctk.CTkLabel(frame_img, image=self.tk_img, text="")
            lbl_img.pack(expand=True, fill="both", padx=10, pady=10)
        except Exception as e:
            ctk.CTkLabel(frame_img, text=f"Error cargando imagen:\n{e}").pack(expand=True)

        # Panel Derecho: Formulario de edición
        frame_data = ctk.CTkFrame(self, fg_color="#111827", corner_radius=10)
        frame_data.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)

        ctk.CTkLabel(frame_data, text="Verificar / Corregir Datos", font=("Segoe UI", 14, "bold")).pack(pady=(15, 10))

        ctk.CTkLabel(frame_data, text="Nº Reporte:", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=(5, 0))
        self.ent_reporte = ctk.CTkEntry(frame_data)
        self.ent_reporte.insert(0, str(data.get("reporte", "")))
        self.ent_reporte.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkLabel(frame_data, text="Fecha (AAAA-MM-DD):", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=(5, 0))
        self.ent_fecha = ctk.CTkEntry(frame_data)
        self.ent_fecha.insert(0, str(data.get("fecha", "")))
        self.ent_fecha.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkLabel(frame_data, text="Nombre del Equipo:", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=(5, 0))
        self.ent_equipo = ctk.CTkEntry(frame_data)
        self.ent_equipo.insert(0, str(data.get("equipo", "")))
        self.ent_equipo.pack(fill="x", padx=15, pady=(0, 5))

        ctk.CTkLabel(frame_data, text="Activos (1 por línea):", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=(5, 0))
        self.txt_activos = ctk.CTkTextbox(frame_data, height=140)
        self.txt_activos.insert("1.0", "\n".join(data.get("activos", [])))
        self.txt_activos.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        btn_save = ctk.CTkButton(
            frame_data, text="💾 Guardar Cambios", fg_color="#2563eb", hover_color="#1d4ed8",
            font=("Segoe UI", 12, "bold"), command=self.save
        )
        btn_save.pack(fill="x", padx=15, pady=(0, 15))

    def save(self):
        raw_txt = self.txt_activos.get("1.0", "end-1c")
        activos_updated = [line.strip() for line in raw_txt.splitlines() if line.strip()]

        updated_data = {
            "reporte": self.ent_reporte.get().strip(),
            "fecha": self.ent_fecha.get().strip(),
            "equipo": self.ent_equipo.get().strip(),
            "activos": activos_updated
        }

        self.on_save_callback(updated_data)
        self.destroy()


class AncaScannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AncaScanner Pro - Ancamedica S.A.")
        self.geometry("1280x760")
        self.minsize(1100, 680)
        self.configure(fg_color="#0b1120")

        # Cargar configuración persistente
        self.config_data = self.load_config()
        self.ollama_ip = self.config_data.get("ollama_ip", "10.147.19.170")
        self.ollama_port = self.config_data.get("ollama_port", "11434")
        self.ollama_model = self.config_data.get("ollama_model", "qwen2.5vl:7b")

        self.loaded_images = []
        self.export_format_var = ctk.StringVar(value="PDF")

        self._build_ui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"ollama_ip": "10.147.19.170", "ollama_port": "11434", "ollama_model": "qwen2.5vl:7b"}

    def save_config(self):
        data = {
            "ollama_ip": self.ollama_ip,
            "ollama_port": self.ollama_port,
            "ollama_model": self.ollama_model
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error guardando configuración: {e}")

    @property
    def ollama_url(self):
        return f"http://{self.ollama_ip}:{self.ollama_port}/api/generate"

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=3)
        self.grid_columnconfigure(2, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # 1. SIDEBAR
        sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#111827")
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(8, weight=1)

        lbl_title = ctk.CTkLabel(sidebar, text="AncaScanner Pro", font=("Segoe UI", 16, "bold"), text_color="#ffffff")
        lbl_title.grid(row=0, column=0, padx=20, pady=(20, 2), sticky="w")
        
        lbl_sub = ctk.CTkLabel(sidebar, text="Ancamedica S.A.", font=("Segoe UI", 11), text_color="#6b7280")
        lbl_sub.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        btn_cargar = ctk.CTkButton(sidebar, text="📤   Cargar Imagen", height=38, corner_radius=8, font=("Segoe UI", 12, "bold"), fg_color="#2563eb", hover_color="#1d4ed8", anchor="w", command=self.load_images)
        btn_cargar.grid(row=2, column=0, padx=16, pady=5, sticky="ew")

        self.btn_analizar = ctk.CTkButton(sidebar, text="✨   Analizar con IA", height=38, corner_radius=8, font=("Segoe UI", 12, "bold"), fg_color="#065f46", hover_color="#047857", text_color="#a7f3d0", anchor="w", command=self.start_analysis_thread)
        self.btn_analizar.grid(row=3, column=0, padx=16, pady=5, sticky="ew")

        # Selector de formato de exportación
        lbl_export = ctk.CTkLabel(sidebar, text="Formato de salida:", font=("Segoe UI", 10, "bold"), text_color="#9ca3af")
        lbl_export.grid(row=4, column=0, padx=16, pady=(10, 0), sticky="w")
        
        opt_export = ctk.CTkOptionMenu(sidebar, values=["PDF", "Original Image"], variable=self.export_format_var, fg_color="#1f2937", button_color="#374151")
        opt_export.grid(row=5, column=0, padx=16, pady=(2, 5), sticky="ew")

        btn_escanear = ctk.CTkButton(sidebar, text="⚡   Escanear y Guardar", height=38, corner_radius=8, font=("Segoe UI", 12, "bold"), fg_color="#d97706", hover_color="#b45309", text_color="#fef3c7", anchor="w", command=self.export_processed_files)
        btn_escanear.grid(row=6, column=0, padx=16, pady=5, sticky="ew")

        btn_limpiar = ctk.CTkButton(sidebar, text="🗑️   Limpiar lote de fotos", height=38, corner_radius=8, font=("Segoe UI", 12, "bold"), fg_color="#371b1e", hover_color="#581c24", text_color="#fca5a5", anchor="w", command=self.clear_batch)
        btn_limpiar.grid(row=7, column=0, padx=16, pady=5, sticky="ew")

        btn_config = ctk.CTkButton(sidebar, text="⚙️   Configuración", height=38, corner_radius=8, font=("Segoe UI", 12, "bold"), fg_color="#1f2937", hover_color="#374151", text_color="#e5e7eb", anchor="w", command=self.open_config_window)
        btn_config.grid(row=8, column=0, padx=16, pady=5, sticky="ew")

        card_server = ctk.CTkFrame(sidebar, corner_radius=10, fg_color="#030712")
        card_server.grid(row=9, column=0, padx=14, pady=(10, 10), sticky="sew")

        self.lbl_serv_dot = ctk.CTkLabel(card_server, text=f"🟢  Servidor: {self.ollama_ip}", font=("Segoe UI", 11, "bold"), text_color="#d1d5db")
        self.lbl_serv_dot.pack(anchor="w", padx=12, pady=(10, 2))

        self.lbl_serv_mod = ctk.CTkLabel(card_server, text=f"Modelo: {self.ollama_model}", font=("Segoe UI", 10), text_color="#6b7280")
        self.lbl_serv_mod.pack(anchor="w", padx=12, pady=(0, 2))

        lbl_serv_status = ctk.CTkLabel(card_server, text="● Conectado", font=("Segoe UI", 11, "bold"), text_color="#10b981")
        lbl_serv_status.pack(anchor="w", padx=12, pady=(0, 10))

        # 2. PANEL CENTRAL
        center_panel = ctk.CTkFrame(self, fg_color="transparent")
        center_panel.grid(row=0, column=1, sticky="nsew", padx=(15, 10), pady=15)
        center_panel.grid_columnconfigure(0, weight=1)
        center_panel.grid_rowconfigure(1, weight=1)

        lbl_sub_top = ctk.CTkLabel(center_panel, text="Convierte documentos en información útil con Inteligencia Artificial.", font=("Segoe UI", 12), text_color="#9ca3af")
        lbl_sub_top.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.drop_zone = ctk.CTkFrame(center_panel, corner_radius=12, fg_color="#111827", border_width=1, border_color="#1f2937")
        self.drop_zone.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        self.drop_zone.grid_columnconfigure(0, weight=1)
        self.drop_zone.grid_rowconfigure(0, weight=1)

        frame_drop_inner = ctk.CTkFrame(self.drop_zone, fg_color="transparent")
        frame_drop_inner.grid(row=0, column=0)

        lbl_dz_icon = ctk.CTkLabel(frame_drop_inner, text="🖼️", font=("Segoe UI", 42))
        lbl_dz_icon.pack(pady=(0, 8))

        lbl_dz_title = ctk.CTkLabel(frame_drop_inner, text="Carga imágenes de reportes de servicio", font=("Segoe UI", 14, "bold"), text_color="#e5e7eb")
        lbl_dz_title.pack()

        btn_dz_load = ctk.CTkButton(frame_drop_inner, text="📤   Cargar Imagen", command=self.load_images, height=36, corner_radius=8, fg_color="#2563eb", hover_color="#1d4ed8", font=("Segoe UI", 12, "bold"))
        btn_dz_load.pack(pady=(12, 12))

        card_system_status = ctk.CTkFrame(center_panel, corner_radius=10, fg_color="#111827")
        card_system_status.grid(row=2, column=0, sticky="ew")

        frame_sys_header = ctk.CTkFrame(card_system_status, fg_color="transparent")
        frame_sys_header.pack(fill="x", padx=14, pady=(10, 4))

        lbl_sys_title = ctk.CTkLabel(frame_sys_header, text="⚙️  Estado del sistema", font=("Segoe UI", 12, "bold"), text_color="#ffffff")
        lbl_sys_title.pack(side="left")

        self.lbl_sys_serv = ctk.CTkLabel(card_system_status, text=f"📂   Servidor Ollama:     {self.ollama_ip}", font=("Segoe UI", 11), text_color="#d1d5db")
        self.lbl_sys_serv.pack(anchor="w", padx=16, pady=1)

        self.lbl_sys_mod = ctk.CTkLabel(card_system_status, text=f"🧬   Modelo activo:       {self.ollama_model}", font=("Segoe UI", 11), text_color="#d1d5db")
        self.lbl_sys_mod.pack(anchor="w", padx=16, pady=1)

        self.lbl_sys_state = ctk.CTkLabel(card_system_status, text="Esperando archivos...", font=("Segoe UI", 11), text_color="#6b7280")
        self.lbl_sys_state.pack(anchor="w", padx=16, pady=(1, 10))

        # 3. PANEL DERECHO
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(10, 15), pady=15)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        lbl_pv_header = ctk.CTkLabel(right_panel, text="Vista previa", font=("Segoe UI", 14, "bold"), text_color="#ffffff")
        lbl_pv_header.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.scroll_preview = ctk.CTkScrollableFrame(right_panel, corner_radius=12, fg_color="#111827", border_width=1, border_color="#1f2937")
        self.scroll_preview.grid(row=1, column=0, sticky="nsew", pady=(0, 12))

    def open_config_window(self):
        config_win = ctk.CTkToplevel(self)
        config_win.title("Configuración del Servidor")
        config_win.geometry("400x320")
        config_win.resizable(False, False)
        config_win.grab_set()

        lbl_cfg_title = ctk.CTkLabel(config_win, text="⚙️ Configuración de Red Ollama", font=("Segoe UI", 14, "bold"))
        lbl_cfg_title.pack(pady=(16, 12))

        lbl_ip = ctk.CTkLabel(config_win, text="Dirección IP Servidor:", font=("Segoe UI", 11, "bold"))
        lbl_ip.pack(anchor="w", padx=30, pady=(4, 0))
        entry_ip = ctk.CTkEntry(config_win, width=340)
        entry_ip.insert(0, self.ollama_ip)
        entry_ip.pack(padx=30, pady=(2, 10))

        lbl_port = ctk.CTkLabel(config_win, text="Puerto Ollama:", font=("Segoe UI", 11, "bold"))
        lbl_port.pack(anchor="w", padx=30, pady=(4, 0))
        entry_port = ctk.CTkEntry(config_win, width=340)
        entry_port.insert(0, self.ollama_port)
        entry_port.pack(padx=30, pady=(2, 10))

        lbl_model = ctk.CTkLabel(config_win, text="Modelo de IA:", font=("Segoe UI", 11, "bold"))
        lbl_model.pack(anchor="w", padx=30, pady=(4, 0))
        entry_model = ctk.CTkEntry(config_win, width=340)
        entry_model.insert(0, self.ollama_model)
        entry_model.pack(padx=30, pady=(2, 16))

        def save_and_close():
            self.ollama_ip = entry_ip.get().strip()
            self.ollama_port = entry_port.get().strip()
            self.ollama_model = entry_model.get().strip()

            self.save_config()

            self.lbl_serv_dot.configure(text=f"🟢  Servidor: {self.ollama_ip}")
            self.lbl_serv_mod.configure(text=f"Modelo: {self.ollama_model}")
            self.lbl_sys_serv.configure(text=f"📂   Servidor Ollama:     {self.ollama_ip}")
            self.lbl_sys_mod.configure(text=f"🧬   Modelo activo:       {self.ollama_model}")

            config_win.destroy()

        btn_save = ctk.CTkButton(config_win, text="💾 Guardar Cambios", fg_color="#2563eb", hover_color="#1d4ed8", font=("Segoe UI", 11, "bold"), command=save_and_close)
        btn_save.pack(pady=10)

    def load_images(self):
        files = ctk.filedialog.askopenfilenames(
            title="Seleccionar imágenes",
            filetypes=[("Archivos de Imagen", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        if files:
            for f in files:
                img_obj = Image.open(f)
                img_obj.thumbnail((120, 80))
                thumb = ImageTk.PhotoImage(img_obj)

                item = {
                    'path': f,
                    'thumb': thumb,
                    'data': {
                        'fecha': 'Pendiente...',
                        'reporte': 'Pendiente...',
                        'equipo': 'Pendiente...',
                        'activos': []
                    }
                }
                self.loaded_images.append(item)
            self.refresh_preview_panel()

    def refresh_preview_panel(self):
        for widget in self.scroll_preview.winfo_children():
            widget.destroy()

        for idx, item in enumerate(self.loaded_images):
            card = ctk.CTkFrame(self.scroll_preview, fg_color="#030712", corner_radius=8)
            card.pack(fill="x", pady=6, padx=6)

            btn_red_thumb = ctk.CTkButton(
                card, image=item['thumb'], text="", width=120, height=80,
                fg_color="#1f2937", hover_color="#374151", corner_radius=6,
                command=lambda p=item['path']: self.open_image_viewer(p)
            )
            btn_red_thumb.pack(side="left", padx=10, pady=10)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

            header_card = ctk.CTkFrame(info_frame, fg_color="transparent")
            header_card.pack(anchor="w", fill="x")

            lbl_fnum = ctk.CTkLabel(header_card, text=f"FOTO #{idx + 1}", font=("Segoe UI", 11, "bold"), text_color="#ffffff")
            lbl_fnum.pack(side="left")

            btn_edit = ctk.CTkButton(
                header_card, text="✏️ Editar", width=70, height=24, font=("Segoe UI", 10, "bold"),
                fg_color="#2563eb", hover_color="#1d4ed8",
                command=lambda item_ref=item: self.open_edit_dialog(item_ref)
            )
            btn_edit.pack(side="right", padx=(0, 5))

            grid_meta = ctk.CTkFrame(info_frame, fg_color="transparent")
            grid_meta.pack(anchor="w", fill="x", pady=(4, 0))

            f_data = item['data']
            activos_str = ", ".join(f_data['activos']) if f_data['activos'] else "Pendiente"

            lbl_col1 = ctk.CTkLabel(
                grid_meta, 
                text=f"FECHA:\n{f_data['fecha']}\n\nNOMBRE DEL EQUIPO:\n{f_data['equipo']}", 
                font=("Segoe UI", 10), text_color="#9ca3af", justify="left"
            )
            lbl_col1.pack(side="left", anchor="nw", padx=(0, 20))

            lbl_col2 = ctk.CTkLabel(
                grid_meta, 
                text=f"REPORTE:\n{f_data['reporte']}\n\nACTIVOS ENCONTRADOS:\n{activos_str}", 
                font=("Segoe UI", 10), text_color="#9ca3af", justify="left"
            )
            lbl_col2.pack(side="left", anchor="nw")

        self.lbl_sys_state.configure(text=f"Listo ({len(self.loaded_images)} fotos cargadas)", text_color="#10b981")

    def open_edit_dialog(self, item):
        def on_save(updated_data):
            item['data'] = updated_data
            self.refresh_preview_panel()

        EditDialog(self, item['path'], item['data'], on_save)

    def open_image_viewer(self, img_path):
        viewer = ctk.CTkToplevel(self)
        viewer.title("Vista previa ampliada")
        viewer.geometry("700x700")
        viewer.grab_set()

        img = Image.open(img_path)
        img.thumbnail((660, 660))
        photo = ImageTk.PhotoImage(img)

        lbl = ctk.CTkLabel(viewer, image=photo, text="")
        lbl.image = photo
        lbl.pack(expand=True, fill="both", padx=10, pady=10)

    def start_analysis_thread(self):
        if not self.loaded_images:
            self.lbl_sys_state.configure(text="⚠️ Carga imágenes primero.", text_color="#ef4444")
            return

        self.btn_analizar.configure(state="disabled")
        threading.Thread(target=self.analyze_with_qwen, daemon=True).start()

    def analyze_with_qwen(self):
        prompt_schema = (
            "Analiza este Reporte de Servicio Técnico de Ancamedica S.A. y extrae los datos en un JSON estricto:\n"
            "{\n"
            '  "fecha": "YYYY-MM-DD",\n'
            '  "reporte": "NUMERO_DE_REPORTE",\n'
            '  "equipo": "NOMBRE_DEL_EQUIPO",\n'
            '  "activos": ["NUMERO_1", "NUMERO_2"]\n'
            "}\n\n"
            "REGLAS OBLIGATORIAS DE LECTURA MANUSCRITA:\n"
            "1. Para 'fecha': Combina DD, MM y AAAA en formato AAAA-MM-DD.\n"
            "2. Para 'reporte': Lee solo los números en rojo del extremo superior derecho (ej. 034220).\n"
            "3. Para 'activos': Extrae CADA número manuscrito de 7 dígitos en la sección de Observaciones.\n"
            "4. REGLA ESPECIAL DE ACTIVOS: Si el campo 'Activo:' dice 'Varios' o 'Varias', IGNORA esa palabra. Busca inmediatamente en 'OBSERVACIONES Y DESCRIPCIÓN DEL TRABAJO' los números manuscritos reales.\n"
            "5. DESAMBIGUACIÓN DE TRAZOS MANUSCRITOS:\n"
            "   - Pon atención al número 4: si las líneas superiores no se unen por completo o el trazo horizontal es corto, no lo confundas con un 9.\n"
            "   - Pon atención al número 8: no lo confundas con un 9 ni con un 2.\n"
            "6. JAMÁS agregues las palabras 'Varios', 'Varias' o 'N/A' dentro de la lista 'activos'. Retorna únicamente cadenas con números de activos.\n"
            "Responde ÚNICAMENTE con el JSON."
        )

        for idx, item in enumerate(self.loaded_images):
            self.lbl_sys_state.configure(text=f"Analizando foto #{idx + 1}...", text_color="#fde047")

            try:
                img_temp = Image.open(item['path'])
                img_temp.thumbnail((1024, 1024))

                buffer = io.BytesIO()
                img_temp.convert("RGB").save(buffer, format="JPEG", quality=85)
                encoded_string = base64.b64encode(buffer.getvalue()).decode('utf-8')

                payload = {
                    "model": self.ollama_model,
                    "prompt": prompt_schema,
                    "images": [encoded_string],
                    "stream": False,
                    "options": {
                        "num_predict": 256,
                        "temperature": 0.1
                    }
                }

                response = requests.post(self.ollama_url, json=payload, timeout=40)
                if response.status_code == 200:
                    raw_text = response.json().get("response", "").strip()
                    if "```json" in raw_text:
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        raw_text = raw_text.split("```")[1].strip()

                    parsed_data = json.loads(raw_text)

                    # Sanitizar número de reporte
                    raw_rep = parsed_data.get('reporte', 'N/A')
                    clean_rep = re.sub(r'\D', '', str(raw_rep).replace('D', '0').replace('O', '0'))

                    # Sanitizar lista de activos
                    raw_activos = parsed_data.get('activos', [])
                    clean_activos = []
                    for act in raw_activos:
                        act_str = str(act).strip()
                        clean_num = re.sub(r'\D', '', act_str)
                        if clean_num:
                            clean_activos.append(clean_num)

                    item['data']['fecha'] = parsed_data.get('fecha', 'N/A')
                    item['data']['reporte'] = clean_rep if clean_rep else 'N/A'
                    item['data']['equipo'] = parsed_data.get('equipo', 'N/A')
                    item['data']['activos'] = clean_activos

            except Exception as e:
                print(f"Error procesando imagen #{idx+1}: {e}")
                item['data']['fecha'] = 'Error'
                item['data']['reporte'] = 'Error'
                item['data']['equipo'] = 'Error'
                item['data']['activos'] = []

        self.after(0, self._on_analysis_complete)

    def _on_analysis_complete(self):
        self.btn_analizar.configure(state="normal")
        self.refresh_preview_panel()
        self.lbl_sys_state.configure(text="✔ Análisis completado", text_color="#10b981")

    def export_processed_files(self):
        if not self.loaded_images:
            self.lbl_sys_state.configure(text="⚠️ Carga imágenes antes de exportar.", text_color="#ef4444")
            return

        target_dir = ctk.filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not target_dir:
            return

        export_type = self.export_format_var.get()
        total_created = 0

        for item in self.loaded_images:
            data = item['data']
            fecha = data.get('fecha', 'SIN_FECHA')
            reporte = data.get('reporte', 'SIN_REPORTE')
            equipo = data.get('equipo', 'EQUIPO').upper()
            activos = data.get('activos', [])

            if not activos:
                activos = ["SIN_ACTIVO"]

            for activo in activos:
                base_name = f"{fecha} {reporte} {equipo} {activo}"
                safe_name = "".join([c for c in base_name if c.isalnum() or c in (' ', '-', '_')]).strip()

                if export_type == "PDF":
                    out_path = os.path.join(target_dir, f"{safe_name}.pdf")
                    try:
                        # Convertir a JPEG en memoria para garantizar compatibilidad con img2pdf
                        img_obj = Image.open(item['path']).convert("RGB")
                        pdf_bytes = io.BytesIO()
                        img_obj.save(pdf_bytes, format="JPEG")
                        pdf_bytes.seek(0)
                        
                        with open(out_path, "wb") as f:
                            f.write(img2pdf.convert(pdf_bytes.read()))
                    except Exception as e:
                        print(f"Error convirtiendo a PDF: {e}")
                        continue
                else:
                    ext = os.path.splitext(item['path'])[1]
                    out_path = os.path.join(target_dir, f"{safe_name}{ext}")
                    shutil.copy(item['path'], out_path)

                total_created += 1

        self.lbl_sys_state.configure(text=f"🎉 Exportados {total_created} archivos correctamente.", text_color="#10b981")

    def clear_batch(self):
        self.loaded_images.clear()
        self.refresh_preview_panel()
        self.lbl_sys_state.configure(text="Lote limpiado.", text_color="#6b7280")

if __name__ == "__main__":
    app = AncaScannerApp()
    app.mainloop()