# 📸 Photo Organizer

Organiza tus fotos automáticamente en carpetas basadas en ubicación y fecha (metadatos EXIF).

## ✨ Características

- **Interfaz moderna y simple** con CustomTkinter
- **Detecta GPS y fecha** de captura automáticamente
- **Múltiples estructuras** de organización:
  - Lugar/Año/Mes
  - Lugar/Año  
  - Año/Lugar
  - Año/Mes/Lugar
- **Detección de duplicados** usando hash MD5
- **Compatible** con Windows, macOS y Linux

## 🚀 Instalación

```bash
git clone https://github.com/yamilpalmiero/photo_organizer.git
cd photo_organizer
pip install -r requirements.txt
python photo_organizer.py
```

## 📁 Dependencias

```
customtkinter>=5.0.0
Pillow>=9.0.0
piexif>=1.1.3
geopy>=2.2.0
tqdm>=4.64.0
```

## 🔧 Uso

1. Ejecuta `python photo_organizer.py`
2. Selecciona la carpeta con tus fotos
3. Elige la estructura de organización
4. Selecciona modo: Copiar o Mover
5. ¡Haz clic en "Start Organizing"!

## 📂 Resultado

Tus fotos se organizarán automáticamente en carpetas como:

```
📁 Paris/
  └── 📁 2023/
      └── 📁 03-March/
          ├── IMG_001.jpg
          ├── IMG_002.jpg
          └── ...
```

## 🔍 Formatos Soportados

JPEG, PNG, TIFF, BMP, GIF

---

⭐ **¡Dale una estrella si te resultó útil!** ⭐
