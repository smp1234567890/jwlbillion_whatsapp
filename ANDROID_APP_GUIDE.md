# JWL — WhatsApp CRM Android App Guide

This guide explains how to build, run, test, and distribute the native Android application for the **WhatsApp CRM**.

---

## Project Architecture

The Android application is built using **Capacitor**, providing a native Android wrapper around the React dashboard with full access to native hardware features:
- **Project Location**: `frontend/android/`
- **Application ID**: `com.jwlbillion.whatsappcrm`
- **App Name**: `WhatsApp CRM`
- **Supported Features**:
  - Live WhatsApp chat interface with push-to-refresh
  - Broadcast campaigns & customer segment messaging
  - Two-Factor Authentication (2FA TOTP & Email recovery)
  - Native Android hardware back-button handling
  - Native Status Bar with emerald branding (`#064e3b`)
  - Seamless support for local development, Android emulator, or live Render cloud deployment

---

## Quick Start: Running the Android App

### Step 1: Open the Project in Android Studio
From the `frontend` directory, run:
```bash
npm run android:open
```
*Or open **Android Studio**, click **Open**, and select the folder:*  
`./frontend/android` (or `<project-root>/frontend/android`)

### Step 2: Sync Gradle and Run
1. Android Studio will automatically sync the Gradle files and download the required Android SDK components.
2. Select your connected Android phone (via USB debugging) or choose an **Android Virtual Device (AVD Emulator)**.
3. Click the green **Run ▶** button (or press `Shift + F10`).

---

## Building an APK File (.apk)

### Option A: From Android Studio (GUI)
1. Open the project in Android Studio.
2. In the top menu, go to **Build** > **Build Bundle(s) / APK(s)** > **Build APK(s)**.
3. Once completed, click the notification popup **locate** to find the output file:
   `frontend/android/app/build/outputs/apk/debug/app-debug.apk`
4. Transfer this `.apk` file directly to any Android smartphone and tap to install!

### Option B: From the Terminal
Ensure `JAVA_HOME` and Android SDK are in your shell path, then run:
```bash
cd frontend/android
./gradlew assembleDebug
```
The APK will be generated at:
`frontend/android/app/build/outputs/apk/debug/app-debug.apk`

---

## Configuring Backend API Connection

The app automatically handles network resolution depending on where it is running:
- **Android Emulator**: Defaults to `http://10.0.2.2:8000` (which routes to your host machine's `localhost:8000`).
- **Physical Phone over Wi-Fi**: Point the app to your computer's local Wi-Fi IP address (e.g., `http://192.168.1.15:8000`).
- **Production Cloud**: Set `VITE_API_URL` to your live Render backend:
  ```env
  VITE_API_URL=https://your-backend-service.onrender.com
  ```
- **Dynamic in-app override**: You can set or change the URL at any time via `localStorage.setItem("mg_custom_api_url", "https://your-api.com")`.

---

## Development Workflow (Making Changes)

Whenever you make changes to the React code in `frontend/src/`:
```bash
cd frontend
npm run android:build
```
This single command:
1. Re-compiles the React application (`vite build`).
2. Synchronizes all assets and plugins to the native Android directory (`cap sync android`).

Then simply click **Run ▶** in Android Studio to instantly test the updated build on your device or emulator!
