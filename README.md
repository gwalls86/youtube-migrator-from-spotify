# Spotify → YouTube Migrator

Una herramienta profesional basada en web diseñada para migrar tus colecciones de música desde **Spotify** hacia **YouTube Music** de forma automatizada. Ahora con una interfaz web moderna, memoria de sincronización inteligente y selector de archivos nativo.

![Versión](https://img.shields.io/badge/version-1.5-green)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.10+-yellow)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🎨 Icono del Proyecto

<p align="center">
  <img src="frontend/icon.png" width="160" alt="Migrator Icon">
</p>

---

## 🚀 Características Principales

### 1. Migración Inteligente
*   **Búsqueda Avanzada**: Algoritmo que prioriza videos oficiales y audios de alta calidad, ignorando "karaokes", "covers" o videos de fans.
*   **Memoria de Progreso**: Guarda el estado de la migración por cada archivo CSV. Si se detiene, continúa exactamente donde se quedó.
*   **Manejo de Duplicados**: No añade canciones que ya estén en la playlist de destino.

### 2. Interfaz Web Premium
*   **Diseño Oscuro y Moderno**: Desarrollado con **Vue 3** y un backend en **FastAPI** para una experiencia fluida.
*   **Selector Nativo**: Abre el diálogo de Windows para seleccionar tus archivos CSV y de credenciales.
*   **Edición Manual**: Permite editar las rutas directamente si lo prefieres (usando el icono ✏️).

---

## 🛠️ Requisitos del Sistema

Esta herramienta está optimizada para **Windows 10/11** y requiere:

1.  **Python 3.10 o superior**.
2.  **Dependencias**: `fastapi`, `uvicorn`, `google-auth`, `google-auth-oauthlib`, `google-api-python-client`, `ytmusicapi`.

---

## 📦 Guía de Uso

### 1. Instalar Dependencias
Abre una terminal en la carpeta del proyecto e instala las librerías necesarias:
```powershell
pip install fastapi uvicorn google-auth google-auth-oauthlib google-api-python-client ytmusicapi
```

### 2. Obtener tu Música de Spotify
1.  Ve a [Exportify](https://exportify.net/).
2.  Inicia sesión con tu cuenta de Spotify.
3.  Descarga el archivo **CSV** de la playlist que deseas migrar.

### 3. Configuración de Credenciales (¡Importante!)
Para que el script pueda interactuar con YouTube, necesitas dos autorizaciones:

#### A. Google Cloud (`client_secrets.json`)
*Necesario para crear la playlist en tu cuenta de YouTube.*
1.  Ve a [Google Cloud Console](https://console.cloud.google.com/).
2.  Crea un nuevo proyecto.
3.  Habilita la **YouTube Data API v3**.
4.  Configura la **Pantalla de consentimiento de OAuth** (Tipo: Externo). **¡IMPORTANTE!** Añade tu propio correo electrónico en "Usuarios de prueba" (Test users). Si no lo haces, recibirás un error de autorización.
5.  En **Credenciales**, crea un **ID de cliente de OAuth** (Tipo: Aplicación de escritorio).
6.  Descarga el JSON, renómbralo a `client_secrets.json` y colócalo en la raíz del proyecto.

#### B. YouTube Music (`ytmusic_auth.json`)
*Necesario para buscar canciones sin límites de cuota.*
1.  Abre una terminal en la carpeta del proyecto y ejecuta:
    ```powershell
    python -m ytmusicapi browser
    ```
2.  Sigue las instrucciones en pantalla para copiar las cabeceras (headers) desde tu navegador.
3.  El comando generará un archivo (usualmente `oauth.json`). Renómbralo a `ytmusic_auth.json` y colócalo en la raíz del proyecto.

---

## 🚀 Iniciar la Aplicación
Simplemente ejecuta el archivo automatizado en la raíz del proyecto:
```powershell
.\start.bat
```
Esto abrirá la interfaz en tu navegador por defecto. Configura las rutas de tus archivos y presiona **Iniciar migración**.

---

## 📝 Créditos y Versión
- **Versión**: 1.5.0
- **Desarrollado por**: **gwalls86**

---
> **Privacidad**: Tus credenciales y archivos CSV están protegidos por el archivo `.gitignore` y nunca se subirán a repositorios públicos si clonas este proyecto.
