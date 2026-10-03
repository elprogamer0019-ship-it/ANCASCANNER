import os
import sys
import zipfile
import subprocess

def build_installer():
    # Detectar automáticamente si la carpeta de salida es 'dist/app' o 'dist/AncaScanner'
    dist_dir = os.path.join("dist", "app")
    if not os.path.exists(dist_dir):
        dist_dir = os.path.join("dist", "AncaScanner")

    if not os.path.exists(dist_dir):
        print("❌ Error: No existe la carpeta dist/app ni dist/AncaScanner. Compila primero con PyInstaller.")
        return

    print(f"📦 Empaquetando distribución desde '{dist_dir}'...")
    payload_zip = "payload.zip"
    with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(dist_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, dist_dir)
                zipf.write(file_path, arcname)

    # Código del instalador usando solo librerías estándar nativas de Python
    installer_code = '''import os
import sys
import zipfile
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

class InstallerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Instalador - AncaScanner Pro")
        self.geometry("480x230")
        self.resizable(False, False)

        tk.Label(self, text="Seleccione la carpeta de instalación:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 5))

        frame_path = tk.Frame(self)
        frame_path.pack(fill="x", padx=20)

        default_dir = os.path.join(os.environ.get("ProgramFiles", "C:\\\\Program Files"), "AncaScanner Pro")
        self.entry_path = tk.Entry(frame_path, font=("Segoe UI", 9))
        self.entry_path.insert(0, default_dir)
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 5))

        tk.Button(frame_path, text="Examinar...", command=self.browse_folder).pack(side="right")

        self.chk_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Crear acceso directo en el Escritorio", variable=self.chk_var).pack(anchor="w", padx=20, pady=10)

        tk.Button(self, text="Instalar", bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"), height=2, command=self.run_install).pack(fill="x", padx=20, pady=10)

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder)

    def create_shortcut_natively(self, target_exe, icon_path, dest_folder):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        shortcut_path = os.path.join(desktop, "AncaScanner Pro.lnk")
        
        # Script PowerShell nativo sin librerías externas
        ps_script = f"""
        $WshShell = New-Object -ComObject WScript.Shell
        \(Shortcut =\)WshShell.CreateShortcut('{shortcut_path}')
        $Shortcut.TargetPath = '{target_exe}'
        $Shortcut.WorkingDirectory = '{dest_folder}'
        if (Test-Path '{icon_path}') {{
            $Shortcut.IconLocation = '{icon_path}'
        }}
        $Shortcut.Save()
        """
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def run_install(self):
        dest_dir = self.entry_path.get().strip()
        if not dest_dir:
            return

        try:
            os.makedirs(dest_dir, exist_ok=True)
            payload_path = os.path.join(getattr(sys, '_MEIPASS', os.path.abspath(".")), "payload.zip")

            with zipfile.ZipFile(payload_path, 'r') as zip_ref:
                zip_ref.extractall(dest_dir)

            if self.chk_var.get():
                target_exe = os.path.join(dest_dir, "app.exe")
                if not os.path.exists(target_exe):
                    target_exe = os.path.join(dest_dir, "AncaScanner.exe")
                icon_path = os.path.join(dest_dir, "logo.ico")
                self.create_shortcut_natively(target_exe, icon_path, dest_dir)

            messagebox.showinfo("Éxito", "¡AncaScanner Pro se ha instalado correctamente!")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error en la instalación:\\n{e}")

if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
'''

    # Forzar la sobrescritura del archivo temporal installer_gui.py
    with open("installer_gui.py", "w", encoding="utf-8") as f:
        f.write(installer_code)

    print("🔨 Compilando ejecutable del instalador...")
    cmd = [
        "pyinstaller", "--noconfirm", "--onefile", "--windowed",
        "--name=AncaScannerPro_Setup",
        "--add-data=payload.zip;.",
        "installer_gui.py"
    ]

    # Incluir el icono de forma segura si el archivo realmente existe
    if os.path.exists("logo.ico"):
        cmd.insert(4, "--icon=logo.ico")
        cmd.insert(5, "--add-data=logo.ico;.")

    subprocess.run(cmd, check=True)

    # Limpieza de archivos temporales post-compilado
    if os.path.exists("payload.zip"):
        os.remove("payload.zip")
    if os.path.exists("installer_gui.py"):
        os.remove("installer_gui.py")

    print("\n✅ ¡Instalador creado con éxito en dist/AncaScannerPro_Setup.exe!")

if __name__ == "__main__":
    build_installer()