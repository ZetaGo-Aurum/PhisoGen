<div align="center">

# 🎣 PhisoGen v3.0

**Advanced Educational Phishing Framework — By ZetaGo-Aurum**

[![Version](https://img.shields.io/badge/version-3.0-blue?style=for-the-badge)]()
[![Python](https://img.shields.io/badge/Python-3.x-yellow?style=for-the-badge)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Android%20%7C%20macOS%20%7C%20Windows-lightgrey?style=for-the-badge)]()

---

### 🔗 Support & Community

<a href="https://trakteer.id/Aleocrophic/tip" target="_blank"><img src="buttons/trakteer_button.svg" alt="Trakteer Tip" width="250"></a>
<a href="https://chat.whatsapp.com/KwTSsF7t5868ERksMPamyQ" target="_blank"><img src="buttons/community_button.svg" alt="Join Community" width="250"></a>

---

> ⚠️ **DISCLAIMER**: This tool is created **solely for educational and authorized security testing purposes**.  
> Any illegal use is strictly prohibited and is not the responsibility of the creator.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎯 **Location Phishing** | Capture target's GPS coordinates |
| 📝 **Form Phishing** | Fake login form with credential harvesting |
| 📸 **Camera Phishing** | Access victim's camera (with permission) |
| 📁 **File Phishing** | Retrieve files from the target |
| 📋 **Clipboard Phishing** | Capture clipboard data in real-time |
| 🖥️ **Device Info** | Auto-collect browser/OS/screen fingerprint |
| 🔗 **URL Shortener** | Auto-shorten links (TinyURL, is.gd, da.gd) |
| 📱 **QR Code Generator** | Auto-generate QR codes for every link |
| 🌐 **Ngrok Tunnel** | Secure reverse proxy — custom region & port |
| 🔄 **Session Persistence** | Token & settings saved — input once, use many |
| 📢 **Discord Webhook** | Auto-send captured data to Discord channel |
| 📊 **Real-time Monitor** | Live victim data dashboard |
| 📦 **Export to JSON** | Export all captured results to JSON file |
| 🌍 **Multi-language** | English & Bahasa Indonesia |

---

## 📦 Installation

### 1. Install Python 3 & Pip (if not installed)

#### 🐧 Linux (Ubuntu/Debian)
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip git -y
```

#### 🐧 Linux (Arch)
```bash
sudo pacman -S python python-pip git --noconfirm
```

#### 📱 Android (Termux)
```bash
pkg update && pkg upgrade -y
pkg install python python-pip git -y
```

#### 🍎 macOS
```bash
# Using Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python3 git
```

#### 🪟 Windows (WSL)
```bash
# Install WSL first, then open Ubuntu terminal:
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip git -y
```

### 2. Clone & Install Dependencies

```bash
# Clone the repository
git clone https://github.com/ZetaGo-Aurum/PhisoGen.git

# Enter directory
cd PhisoGen

# Install Python dependencies
pip3 install -r requirements.txt
```

> **💡 Tip:** If `pip3` is not found, try `pip install -r requirements.txt` instead.

---

## 🚀 Usage

```bash
python3 start.py
```

1. Select language (English / Indonesia)
2. Enter your **Ngrok Auth Token** (saved to session — only needed once)
3. Choose attack type from menu
4. Enter target URL to clone
5. Send the generated phishing link (+ QR code) to target

### Menu Options

| # | Feature | Description |
|---|---------|-------------|
| 1 | 🎯 Location Phishing | Get victim's GPS location |
| 2 | 📝 Form Phishing | Fake login form |
| 3 | 📸 Camera Phishing | Access victim's camera |
| 4 | 📁 File Phishing | Retrieve files |
| 5 | 📋 Clipboard Phishing | Capture clipboard data |
| 6 | 📊 View Results | Live victim data dashboard |
| 7 | 📦 Export Data | Export results to JSON |
| 8 | ⚙️ Settings | Webhook, region, port config |
| 9 | ❌ Exit | Close program |

### Captured Data

| Type | Saved to |
|------|----------|
| Form/Clipboard/Location data | `phishing_results.txt` |
| Camera captures | `captured_images/` |
| Uploaded files | `uploaded_files/` |
| All data export | `export_<timestamp>.json` |

---

## ⚙️ Settings

Access via menu option **8**:

- **Ngrok Region** — Choose server region (US, EU, AP, AU, SA, JP, IN)
- **Server Port** — Custom port (default: 5000)
- **Discord Webhook** — Set webhook URL to auto-receive captured data
- All settings persist across sessions

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

**Created by [ZetaGo-Aurum](https://github.com/ZetaGo-Aurum)**  
*For educational purposes only*

</div>
