# PhisoGen
Phising Generator

# 🎣 Phishing Generator Tool

Advanced phishing tool with ngrok integration to create phishing pages disguised as target websites.

## 📱 Termux Installation
```bash
# Install required dependencies
pkg update && pkg upgrade
pkg install python3 git

# Clone repository
git clone https://github.com/ZetaGo-Aurum/PhisoGen.git

# Install Python requirements
pip install -r requirements.txt
```

## 💻 Linux Installation (Ubuntu/Debian)
```bash
# Update system
sudo apt update && sudo apt upgrade

# Install Python and Git
sudo apt install python3 python3-pip git

# Clone repository 
git clone https://github.com/ZetaGo-Aurum/PhisoGen.git
# Install Python requirements
pip3 install -r requirements.txt
```

## 🚀 Usage

1. Run the script:
```bash
# On Termux
python phising-maker.py

# On Linux
python3 phising-maker.py
```

2. Select preferred language (English/Indonesia)
3. Tool will automatically create ngrok tunnel
4. Choose phishing attack type:
- Location Phishing - Get victim's GPS location
- Form Phishing - Create fake login form
- Camera Phishing - Access victim's camera
- File Phishing - Get files from victim
5. Enter target URL to mimic
6. Tool will generate shortened phishing link
7. Send the link to target
8. Captured data will be saved in:
- `phishing_results.txt` - All results log
- `captured_images/` - Camera captures
- `uploaded_files/` - Uploaded files

## ⚠️ Disclaimer
This tool is created for educational and security testing purposes only. Any illegal use is not the responsibility of the creator.


## 🔑 Features
- Interactive CLI interface with Rich
- Multi-language support (English & Indonesia)
- Automatic reverse proxy with ngrok
- Integrated URL shortener
- Logging and error handling
- Real-time victim monitoring
- Multiple phishing attack types


## 📱 Compatibility

- Android (Termux)
- Linux (Ubuntu/Debian)
- Windows (WSL)
- macOS


## 🔄 Updates
Check for updates regularly:

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```


# Remember to star ⭐ the repository if you find it useful!

## Preview

![preview1](https://github.com/ZetaGo-Aurum/PhisoGen/blob/main/Preview/Screenshot%202024-11-07%20182728.png)

![preview2](https://github.com/ZetaGo-Aurum/PhisoGen/blob/main/Preview/Screenshot%202024-11-07%20182746.png)

