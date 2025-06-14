import os
import shutil
import piexif
from PIL import Image
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tqdm import tqdm
import threading

# Configurar geolocalizador global
geolocator = Nominatim(user_agent="photo_organizer")

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
    try:
        location = geolocator.reverse(coords, language='en', timeout=10)
        if location is None:
            return "Unknown"
        return location.address.split(',')[0]
    except GeocoderTimedOut:
        return "Unknown"

def organize_photos(src, dst, structure, mode):
    images = [f for f in os.listdir(src) if f.lower().endswith(('jpg', 'jpeg', 'png'))]

    for img in tqdm(images, desc="Organizing"):
        src_path = os.path.join(src, img)
        exif = get_exif_data(src_path)
        
        if not exif:
            continue

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
            folder_path = os.path.join(dst, "Desconocido")

        os.makedirs(folder_path, exist_ok=True)
        dst_path = os.path.join(folder_path, img)

        if mode == "Copiar":
            shutil.copy2(src_path, dst_path)
        else:
            shutil.move(src_path, dst_path)

# Interfaz gráfica
class PhotoOrganizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Photo Organizer GPS + Fecha")
        self.geometry("500x400")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.src = ""
        self.dst = ""

        self.label = ctk.CTkLabel(self, text="Organizador de Fotos", font=("Arial", 20))
        self.label.pack(pady=20)

        self.src_button = ctk.CTkButton(self, text="Seleccionar carpeta origen", command=self.select_src)
        self.src_button.pack(pady=10)

        self.dst_button = ctk.CTkButton(self, text="Seleccionar carpeta destino", command=self.select_dst)
        self.dst_button.pack(pady=10)

        self.structure_option = ctk.CTkOptionMenu(self, values=["Lugar/Año/Mes", "Lugar/Año", "Año/Lugar", "Año/Mes/Lugar"])
        self.structure_option.set("Lugar/Año/Mes")
        self.structure_option.pack(pady=10)

        self.mode_option = ctk.CTkOptionMenu(self, values=["Mover", "Copiar"])
        self.mode_option.set("Mover")
        self.mode_option.pack(pady=10)

        self.start_button = ctk.CTkButton(self, text="Organizar Fotos", command=self.start_organizing)
        self.start_button.pack(pady=20)

    def select_src(self):
        self.src = filedialog.askdirectory()

    def select_dst(self):
        self.dst = filedialog.askdirectory()

    def start_organizing(self):
        if not self.src or not self.dst:
            messagebox.showerror("Error", "Debes seleccionar ambas carpetas.")
            return

        structure = self.structure_option.get()
        mode = self.mode_option.get()

        thread = threading.Thread(target=self.run_organizer, args=(structure, mode))
        thread.start()

    def run_organizer(self, structure, mode):
        organize_photos(self.src, self.dst, structure, mode)
        messagebox.showinfo("Completado", "Organización finalizada correctamente.")

if __name__ == '__main__':
    app = PhotoOrganizerApp()
    app.mainloop()
