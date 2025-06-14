import os
import shutil
import piexif
import json
import hashlib
from PIL import Image
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tqdm import tqdm
import threading
import time

# Configurar geolocalizador global
geolocator = Nominatim(user_agent="picplace_organizer")

# Cache para geocoding
CACHE_FILE = "picplace_geocache.json"
geocache = {}

# Configuraciones por defecto
DEFAULT_CONFIG = {
    "structure": "Lugar/Año/Mes",
    "mode": "Mover",
    "last_src_folder": "",
    "different_folder": False,
    "last_dst_folder": ""
}

def load_geocache():
    """Cargar cache de geocoding desde archivo"""
    global geocache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                geocache = json.load(f)
    except Exception:
        geocache = {}

def save_geocache():
    """Guardar cache de geocoding a archivo"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(geocache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_config():
    """Cargar configuración guardada"""
    try:
        if os.path.exists("picplace_config.json"):
            with open("picplace_config.json", 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Guardar configuración"""
    try:
        with open("picplace_config.json", 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def get_file_hash(filepath):
    """Obtener hash MD5 de un archivo para detectar duplicados"""
    try:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            # Leer en chunks para archivos grandes
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

def get_exif_data(image_path):
    try:
        img = Image.open(image_path)
        exif_dict = piexif.load(img.info['exif'])
        return exif_dict
    except Exception:
        return None

def get_datetime_taken(exif):
    try:
        date_str = exif['Exif'][piexif.ExifIFD.DateTimeOriginal].decode()
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except:
        return None

def get_gps_coords(exif):
    try:
        gps = exif['GPS']
        lat_deg = gps[piexif.GPSIFD.GPSLatitude][0][0] / gps[piexif.GPSIFD.GPSLatitude][0][1]
        lat_min = gps[piexif.GPSIFD.GPSLatitude][1][0] / gps[piexif.GPSIFD.GPSLatitude][1][1]
        lat_sec = gps[piexif.GPSIFD.GPSLatitude][2][0] / gps[piexif.GPSIFD.GPSLatitude][2][1]
        lon_deg = gps[piexif.GPSIFD.GPSLongitude][0][0] / gps[piexif.GPSIFD.GPSLongitude][0][1]
        lon_min = gps[piexif.GPSIFD.GPSLongitude][1][0] / gps[piexif.GPSIFD.GPSLongitude][1][1]
        lon_sec = gps[piexif.GPSIFD.GPSLongitude][2][0] / gps[piexif.GPSIFD.GPSLongitude][2][1]
        
        lat = lat_deg + (lat_min / 60.0) + (lat_sec / 3600.0)
        lon = lon_deg + (lon_min / 60.0) + (lon_sec / 3600.0)
        
        if gps[piexif.GPSIFD.GPSLatitudeRef] == b'S':
            lat = -lat
        if gps[piexif.GPSIFD.GPSLongitudeRef] == b'W':
            lon = -lon

        return lat, lon
    except:
        return None

def get_location_name(coords):
    """Obtener nombre de ubicación con cache"""
    coords_key = f"{coords[0]:.6f},{coords[1]:.6f}"
    
    # Buscar en cache primero
    if coords_key in geocache:
        return geocache[coords_key]
    
    try:
        location = geolocator.reverse(coords, language='en', timeout=10)
        if location is None:
            result = "Unknown"
        else:
            result = location.address.split(',')[0]
        
        # Guardar en cache
        geocache[coords_key] = result
        return result
    except GeocoderTimedOut:
        return "Unknown"

def scan_photos(folder_path):
    """Escanear carpeta y obtener información de fotos"""
    supported_formats = ('.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif')
    photos = []
    duplicates = {}
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(supported_formats):
                filepath = os.path.join(root, file)
                file_hash = get_file_hash(filepath)
                
                if file_hash:
                    if file_hash in duplicates:
                        duplicates[file_hash].append(filepath)
                    else:
                        duplicates[file_hash] = [filepath]
                        photos.append(filepath)
    
    # Identificar duplicados reales
    actual_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
    
    return photos, actual_duplicates

def organize_photos(src, dst, structure, mode, progress_callback=None, status_callback=None):
    """Función principal de organización con callbacks para progreso"""
    if status_callback:
        status_callback("Scanning photos...")
    
    photos, duplicates = scan_photos(src)
    total_photos = len(photos)
    
    if status_callback:
        status_callback(f"Found {total_photos} photos ({len(duplicates)} duplicates)")
    
    organized_count = 0
    error_count = 0
    
    # Crear carpeta para duplicados si existen
    if duplicates and dst != src:
        duplicates_folder = os.path.join(dst, "_PicPlace_Duplicates")
        os.makedirs(duplicates_folder, exist_ok=True)
    
    for i, photo_path in enumerate(photos):
        try:
            if status_callback:
                status_callback(f"Processing: {os.path.basename(photo_path)}")
            
            exif = get_exif_data(photo_path)
            
            if not exif:
                # Mover fotos sin EXIF a carpeta especial
                no_exif_folder = os.path.join(dst, "_PicPlace_NoMetadata")
                os.makedirs(no_exif_folder, exist_ok=True)
                dst_path = os.path.join(no_exif_folder, os.path.basename(photo_path))
            else:
                date_taken = get_datetime_taken(exif)
                coords = get_gps_coords(exif)
                
                year = date_taken.year if date_taken else "Unknown"
                month = date_taken.strftime("%m-%B") if date_taken else "Unknown"
                location = get_location_name(coords) if coords else "Unknown"

                # Define estructura de carpetas
                if structure == "Lugar/Año/Mes":
                    folder_path = os.path.join(dst, location, str(year), month)
                elif structure == "Lugar/Año":
                    folder_path = os.path.join(dst, location, str(year))
                elif structure == "Año/Lugar":
                    folder_path = os.path.join(dst, str(year), location)
                elif structure == "Año/Mes/Lugar":
                    folder_path = os.path.join(dst, str(year), month, location)
                else:
                    folder_path = os.path.join(dst, "Unknown")

                os.makedirs(folder_path, exist_ok=True)
                dst_path = os.path.join(folder_path, os.path.basename(photo_path))

            # Mover o copiar archivo
            if mode == "Copiar":
                shutil.copy2(photo_path, dst_path)
            else:
                shutil.move(photo_path, dst_path)
            
            organized_count += 1
            
        except Exception as e:
            error_count += 1
            print(f"Error processing {photo_path}: {e}")
        
        # Actualizar progreso
        if progress_callback:
            progress_callback(i + 1, total_photos)
    
    # Manejar duplicados
    if duplicates and dst != src:
        duplicate_count = 0
        for file_hash, file_list in duplicates.items():
            if len(file_list) > 1:
                # Mantener el primero, mover el resto a carpeta de duplicados
                for duplicate_path in file_list[1:]:
                    try:
                        dup_dst = os.path.join(duplicates_folder, os.path.basename(duplicate_path))
                        if mode == "Copiar":
                            shutil.copy2(duplicate_path, dup_dst)
                        else:
                            shutil.move(duplicate_path, dup_dst)
                        duplicate_count += 1
                    except Exception:
                        pass
    
    # Guardar cache al final
    save_geocache()
    
    return {
        'total': total_photos,
        'organized': organized_count,
        'errors': error_count,
        'duplicates': len(duplicates)
    }

# Interfaz gráfica
class PicPlaceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PicPlace - Smart Photo Organizer")
        self.geometry("600x550")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # Cargar configuración y cache
        self.config = load_config()
        load_geocache()

        self.src = self.config.get("last_src_folder", "")
        self.dst = self.config.get("last_dst_folder", "")
        self.same_folder = not self.config.get("different_folder", False)
        
        # Variables para preview
        self.photo_count = 0
        self.duplicate_count = 0
        
        self.setup_ui()
        self.load_saved_config()

    def setup_ui(self):
        # Header con logo/nombre
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.pack(pady=10, padx=20, fill="x")
        
        self.logo_label = ctk.CTkLabel(self.header_frame, text="📸 PicPlace", font=("Arial", 24, "bold"))
        self.logo_label.pack(pady=10)
        
        self.subtitle_label = ctk.CTkLabel(self.header_frame, text="Organize your photos by location and date", 
                                         font=("Arial", 12), text_color="gray")
        self.subtitle_label.pack()

        # Información de vista previa
        self.preview_frame = ctk.CTkFrame(self)
        self.preview_frame.pack(pady=10, padx=20, fill="x")
        
        self.preview_label = ctk.CTkLabel(self.preview_frame, text="📊 No folder selected", 
                                        font=("Arial", 12))
        self.preview_label.pack(pady=10)

        # Botón de selección de carpeta origen
        self.src_button = ctk.CTkButton(self, text="📁 Select Photos Folder", command=self.select_src)
        self.src_button.pack(pady=10)

        # Checkbox para carpeta diferente
        self.different_folder_var = ctk.BooleanVar(value=not self.same_folder)
        self.different_folder_checkbox = ctk.CTkCheckBox(self, text="Use different destination folder", 
                                                       variable=self.different_folder_var,
                                                       command=self.toggle_destination_folder)
        self.different_folder_checkbox.pack(pady=5)

        # Botón de carpeta destino (inicialmente oculto)
        self.dst_button = ctk.CTkButton(self, text="📂 Select Destination Folder", command=self.select_dst)
        
        # Opciones de organización
        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(self.options_frame, text="Organization Structure:", font=("Arial", 12, "bold")).pack(pady=5)
        self.structure_option = ctk.CTkOptionMenu(self.options_frame, 
                                                values=["Lugar/Año/Mes", "Lugar/Año", "Año/Lugar", "Año/Mes/Lugar"])
        self.structure_option.set(self.config.get("structure", "Lugar/Año/Mes"))
        self.structure_option.pack(pady=5)

        ctk.CTkLabel(self.options_frame, text="Mode:", font=("Arial", 12, "bold")).pack(pady=5)
        self.mode_option = ctk.CTkOptionMenu(self.options_frame, values=["Mover", "Copiar"])
        self.mode_option.set(self.config.get("mode", "Mover"))
        self.mode_option.pack(pady=5)

        # Progreso
        self.progress_frame = ctk.CTkFrame(self)
        self.progress_frame.pack(pady=10, padx=20, fill="x")
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Ready to organize")
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.pack(pady=5, padx=10, fill="x")
        self.progress_bar.set(0)

        # Botón principal
        self.start_button = ctk.CTkButton(self, text="🚀 Start Organizing", 
                                        command=self.start_organizing,
                                        font=("Arial", 14, "bold"),
                                        height=40)
        self.start_button.pack(pady=20)

        # Footer
        self.footer_label = ctk.CTkLabel(self, text="PicPlace v2.0 - Find the perfect place for every pic", 
                                       font=("Arial", 10), text_color="gray")
        self.footer_label.pack(side="bottom", pady=10)

    def load_saved_config(self):
        """Cargar configuración guardada al inicio"""
        if self.src:
            display_path = self.src if len(self.src) < 40 else f"...{self.src[-37:]}"
            self.src_button.configure(text=display_path)
            self.scan_folder_preview()
        
        if not self.same_folder and self.dst:
            display_path = self.dst if len(self.dst) < 40 else f"...{self.dst[-37:]}"
            self.dst_button.configure(text=display_path)
            self.dst_button.pack(pady=5, before=self.options_frame)

    def scan_folder_preview(self):
        """Escanear carpeta en background para mostrar preview"""
        if not self.src:
            return
            
        def scan_thread():
            try:
                photos, duplicates = scan_photos(self.src)
                self.photo_count = len(photos)
                self.duplicate_count = len(duplicates)
                
                # Actualizar UI en hilo principal
                self.after(0, self.update_preview)
            except Exception as e:
                self.after(0, lambda: self.update_preview_error(str(e)))
        
        threading.Thread(target=scan_thread, daemon=True).start()

    def update_preview(self):
        """Actualizar información de preview en UI"""
        if self.duplicate_count > 0:
            preview_text = f"📊 {self.photo_count} photos found, {self.duplicate_count} duplicates detected"
        else:
            preview_text = f"📊 {self.photo_count} photos found"
        
        self.preview_label.configure(text=preview_text)

    def update_preview_error(self, error):
        """Mostrar error en preview"""
        self.preview_label.configure(text=f"❌ Error scanning folder: {error}")

    def select_src(self):
        folder = filedialog.askdirectory(title="Select folder with photos to organize")
        if folder:
            self.src = folder
            # Si usa misma carpeta, también actualizar destino
            if self.same_folder:
                self.dst = folder
            # Mostrar ruta
            display_path = folder if len(folder) < 40 else f"...{folder[-37:]}"
            self.src_button.configure(text=display_path)
            
            # Escanear para preview
            self.preview_label.configure(text="🔄 Scanning photos...")
            self.scan_folder_preview()

    def select_dst(self):
        folder = filedialog.askdirectory(title="Select destination folder for organized photos")
        if folder:
            self.dst = folder
            display_path = folder if len(folder) < 40 else f"...{folder[-37:]}"
            self.dst_button.configure(text=display_path)

    def toggle_destination_folder(self):
        if self.different_folder_var.get():
            # Activar carpeta diferente
            self.same_folder = False
            self.dst_button.pack(pady=5, before=self.options_frame)
            self.dst = ""
        else:
            # Volver a misma carpeta
            self.same_folder = True
            self.dst_button.pack_forget()
            self.dst = self.src

    def update_progress(self, current, total):
        """Callback para actualizar barra de progreso"""
        progress = current / total if total > 0 else 0
        self.progress_bar.set(progress)
        self.progress_label.configure(text=f"Processing: {current}/{total} photos ({progress:.0%})")

    def update_status(self, status):
        """Callback para actualizar estado"""
        self.progress_label.configure(text=status)

    def start_organizing(self):
        if not self.src:
            messagebox.showerror("PicPlace Error", "Please select a photos folder first.")
            return
        
        # Si usa misma carpeta, asegurar que dst esté configurado
        if self.same_folder:
            self.dst = self.src
        elif not self.dst:
            messagebox.showerror("PicPlace Error", "Please select a destination folder.")
            return

        # Guardar configuración
        self.save_current_config()

        structure = self.structure_option.get()
        mode = self.mode_option.get()

        # Disable button during processing
        self.start_button.configure(state="disabled", text="🔄 Organizing...")
        self.progress_bar.set(0)
        
        thread = threading.Thread(target=self.run_organizer, args=(structure, mode))
        thread.start()

    def save_current_config(self):
        """Guardar configuración actual"""
        self.config.update({
            "structure": self.structure_option.get(),
            "mode": self.mode_option.get(),
            "last_src_folder": self.src,
            "different_folder": self.different_folder_var.get(),
            "last_dst_folder": self.dst if not self.same_folder else ""
        })
        save_config(self.config)

    def run_organizer(self, structure, mode):
        try:
            start_time = time.time()
            result = organize_photos(
                self.src, self.dst, structure, mode,
                progress_callback=self.update_progress,
                status_callback=self.update_status
            )
            end_time = time.time()
            duration = end_time - start_time
            
            # Mensaje de éxito con estadísticas
            success_msg = f"""✅ Organization completed successfully!

📊 Statistics:
• Photos processed: {result['organized']}/{result['total']}
• Duplicates found: {result['duplicates']}
• Errors: {result['errors']}
• Time taken: {duration:.1f} seconds

🎉 Your photos are now perfectly organized!"""
            
            messagebox.showinfo("PicPlace Complete", success_msg)
            
        except Exception as e:
            messagebox.showerror("PicPlace Error", f"An error occurred: {str(e)}")
        finally:
            # Re-enable button
            self.start_button.configure(state="normal", text="🚀 Start Organizing")
            self.progress_bar.set(0)
            self.progress_label.configure(text="Ready to organize")

if __name__ == '__main__':
    app = PicPlaceApp()
    app.mainloop()