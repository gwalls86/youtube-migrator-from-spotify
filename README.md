# 🚀 Spotify → YouTube Migrator Web

Una herramienta potente y elegante diseñada para migrar tus colecciones de música desde **Spotify** hacia **YouTube Music** de forma automatizada. Ahora con una interfaz web moderna y memoria de sincronización inteligente.

![Versión](https://img.shields.io/badge/version-1.2-green)
![Platform](https://img.shields.io/badge/platform-Windows-blue)

---

## 🎨 Icono del Proyecto

<p align="center">
  <img src="frontend/icon.png" width="150" alt="Spotify to YouTube Migrator Icon">
</p>

---

## 🚀 Características Principales

*   **INTERFAZ WEB**: Experiencia visual premium y moderna desarrollada con **Vue 3** y un backend en **FastAPI**.
*   **SELECTOR DE ARCHIVOS NATIVO**: Permite seleccionar archivos CSV y JSON directamente usando el diálogo del sistema operativo.
*   **BÚSQUEDA INTELIGENTE**: Algoritmo que prioriza **Videos Oficiales (OMV)** y Audios de alta calidad, filtrando versiones "karaoke", "covers" o "letras".
*   **MEMORIA DE SINCRONIZACIÓN**: El sistema recuerda el progreso por cada archivo CSV. Si reanudas una migración, el script sabrá exactamente dónde continuar.
*   **AUTO-INICIO**: Incluye un script `start.bat` para iniciar el servidor y abrir la interfaz con un solo clic.

---

## 🛠️ Requisitos Previos

1.  **Python 3.10 o superior**: [Descargar aquí](https://www.python.org/downloads/). (Marca "Add Python to PATH").
2.  **Exportify**: Ve a [Exportify](https://exportify.net/), conéctate con Spotify y descarga el archivo **CSV** de las playlists que quieras migrar.
3.  **Dependencias**:
    ```bash
    pip install fastapi uvicorn google-auth google-auth-oauthlib google-api-python-client ytmusicapi
    ```

---

## 📦 Configuración de Credenciales

Para que el script funcione, necesitas dos archivos de autorización en la carpeta del proyecto (o seleccionarlos desde la interfaz):

### 1. Google Cloud (`client_secrets.json`)
Permite al script crear playlists en tu cuenta de YouTube.
1.  Crea un proyecto en [Google Cloud Console](https://console.cloud.google.com/).
2.  Habilita la **YouTube Data API v3**.
3.  En "Credenciales", crea un **ID de cliente de OAuth** de tipo **App de escritorio**.
4.  Descarga el JSON, renómbralo a `client_secrets.json` y ponlo en la carpeta raíz.

### 2. YouTube Music (`ytmusic_auth.json`)
Permite buscar canciones sin consumir cuota de API.
1.  Abre una terminal y ejecuta:
    ```bash
    python -m ytmusicapi browser
    ```
2.  Sigue las instrucciones para copiar tus "headers" desde el navegador.
3.  El archivo generado se llamará `oauth.json`. Renómbralo a `ytmusic_auth.json` y ponlo en la carpeta raíz.

---

## 🎮 Guía de Uso

1.  **Ejecuta el script**:
    Doble clic en `start.bat` en la raíz del proyecto.
2.  **Uso de la Interfaz**:
    *   Se abrirá la interfaz en tu navegador.
    *   Haz clic en los campos para seleccionar tu archivo CSV de Exportify y los archivos de credenciales (si no están en la raíz).
    *   Pulsa **Iniciar migración**.
3.  **Autorización**: La primera vez se abrirá el navegador para autorizar tu cuenta de Google.

---

## 🏗️ Estructura de Archivos

*   `backend/main.py`: Servidor FastAPI.
*   `frontend/index.html`: Interfaz de usuario (Vue 3).
*   `start.bat`: Script de inicio rápido.

---

> **Privacidad**: Tus archivos de credenciales (`client_secrets.json`, `ytmusic_auth.json`) y tokens están incluidos en el `.gitignore` para que nunca se suban a la nube.

---
*Desarrollado por **gwalls86***
