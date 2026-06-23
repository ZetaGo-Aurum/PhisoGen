<div align="center">

# 🎣 PhisoGen

**Advanced Phishing Framework — Educational Security Testing Tool**

[![Version](https://img.shields.io/badge/version-2.1-blue?style=for-the-badge)]()
[![Python](https://img.shields.io/badge/Python-3.x-yellow?style=for-the-badge)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Android%20%7C%20macOS%20%7C%20Windows-lightgrey?style=for-the-badge)]()

---

### 🔗 Support & Community

<a href="https://trakteer.id/rayhandzaky" target="_blank"><img src="https://img.shields.io/badge/Trakteer-Support%20Me-red?style=for-the-badge&logo=ko-fi" alt="Trakteer"></a>
<a href="https://github.com/ZetaGo-Aurum" target="_blank"><img src="https://img.shields.io/badge/GitHub-Follow-181717?style=for-the-badge&logo=github" alt="GitHub"></a>
<a href="https://t.me/phishgen" target="_blank"><img src="https://img.shields.io/badge/Telegram-Join%20Community-26A5E4?style=for-the-badge&logo=telegram" alt="Telegram"></a>

---

> ⚠️ **DISCLAIMER**: This tool is created **solely for educational and authorized security testing purposes**.  
> Any illegal use is strictly prohibited and is not the responsibility of the creator.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **Location Phishing** | Capture target's GPS coordinates |
| 📝 **Form Phishing** | Deceive login form with credential harvesting |
| 📸 **Camera Phishing** | Access victim's camera (with permission) |
| 📁 **File Phishing** | Retrieve files from the target |
| 🔗 **URL Shortener** | Auto-shorten phishing links (TinyURL, is.gd, da.gd) |
| 🌐 **Ngrok Tunnel** | Secure reverse proxy with public URL |
| 🔄 **Session Token** | Ngrok token saved — input once, use many times |
| 🌍 **Multi-language** | English & Bahasa Indonesia |
| 📊 **Real-time Monitor** | Live victim data dashboard |

---

## 📦 Installation

### Linux / Termux / macOS

```bash
# Clone the repository
git clone https://github.com/ZetaGo-Aurum/PhisoGen.git

# Enter directory
cd PhisoGen

# Install dependencies
pip3 install -r requirements.txt
```

---

## 🚀 Usage

```bash
python3 start.py
```

1. Select language (English / Indonesia)
2. Enter your **Ngrok Auth Token** (saved to session — only needed once)
3. Choose attack type from the menu
4. Enter target URL to clone
5. Send the generated phishing link to target

### Captured Data

| Type | Saved to |
|------|----------|
| Form data | `phishing_results.txt` |
| Camera captures | `captured_images/` |
| Uploaded files | `uploaded_files/` |

---

## 🔧 Ngrok Auth Token

Get your free auth token at: [https://dashboard.ngrok.com](https://dashboard.ngrok.com)

- Token is stored in `.phishgen_session.json` (automatically git-ignored)
- Only required **once** — persists until token expires or session file is deleted

---

## 📱 Compatibility

- ✅ Linux (Ubuntu/Debian/Arch)
- ✅ Android (Termux / Userland)
- ✅ macOS
- ✅ Windows (WSL)

---

## 🧠 For Educational Use Only

This project demonstrates how phishing attacks work so you can better defend against them.  
Understanding these techniques helps security professionals and ethical hackers build stronger defenses.

**Knowledge is power. Use it wisely.**

---

## 📸 Preview

<table>
  <tr>
    <td><img src="Preview/Screenshot%202024-11-07%20182728.png" width="100%"></td>
    <td><img src="Preview/Screenshot%202024-11-07%20182746.png" width="100%"></td>
  </tr>
  <tr>
    <td><img src="Preview/Screenshot%202024-11-07%20182809.png" width="100%"></td>
    <td><img src="Preview/Screenshot%202024-11-07%20182914.png" width="100%"></td>
  </tr>
  <tr>
    <td colspan="2" align="center"><img src="Preview/Screenshot%202024-11-07%20182938.png" width="80%"></td>
  </tr>
</table>

---

### ⭐ Star This Repository

If you find this project useful, **star the repo** to support development!

<div align="center">

**Created by [Rayhan Dzaky Al Mubarok](https://github.com/ZetaGo-Aurum)**  
*For educational purposes only*

</div>
