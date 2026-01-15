from flask import Flask, request, jsonify, render_template_string
import subprocess
import os
import uuid
from config import Config

app = Flask(__name__)

# Ensure directories exist
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(Config.OUTPUT_FOLDER, exist_ok=True)
os.makedirs(Config.SNAPSHOT_FOLDER, exist_ok=True)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prometheus Deobfuscator V2</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; color: #00d4ff; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #888; margin-bottom: 30px; }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .discord-banner {
            background: linear-gradient(135deg, #5865F2 0%, #7289da 100%);
            text-align: center;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .discord-banner a {
            color: #fff;
            text-decoration: none;
            font-weight: bold;
            font-size: 18px;
        }
        textarea {
            width: 100%;
            height: 200px;
            padding: 15px;
            border: 2px solid rgba(0,212,255,0.3);
            border-radius: 10px;
            background: rgba(0,0,0,0.3);
            color: #fff;
            font-family: monospace;
        }
        select, input { 
            padding: 12px; 
            border-radius: 8px; 
            background: rgba(0,0,0,0.3); 
            color: #fff; 
            border: 1px solid rgba(255,255,255,0.2); 
            width: 100%;
            margin-bottom: 10px;
        }
        .btn {
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            color: #000;
            border: none;
            padding: 15px 40px;
            font-size: 16px;
            font-weight: bold;
            border-radius: 10px;
            cursor: pointer;
        }
        .btn:hover { transform: translateY(-2px); }
        .result { margin-top: 20px; }
        .success { color: #00ff64; }
        .error { color: #ff6464; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔓 Prometheus Deobfuscator V2</h1>
        <p class="subtitle">Lua Deobfuscation Tool</p>
        
        <div class="discord-banner">
            <a href="YOUR_DISCORD_INVITE_LINK" target="_blank">
                🤖 Use our Discord Bot for easier access!
            </a>
        </div>
        
        <div class="card">
            <h3>📝 Paste Obfuscated Code</h3>
            <textarea id="code" placeholder="Paste your obfuscated Lua code here..."></textarea>
            
            <h3 style="margin-top:15px;">⚙️ Options</h3>
            <select id="trace">
                <option value="off">Trace: Off (Static)</option>
                <option value="prints">Trace: Prints</option>
                <option value="calls">Trace: Calls</option>
                <option value="api">Trace: API</option>
                <option value="debug">Trace: Debug</option>
            </select>
            
            <div style="text-align:center;margin-top:20px;">
                <button class="btn" onclick="deobfuscate()">🚀 Deobfuscate</button>
            </div>
            
            <div class="result" id="result"></div>
        </div>
    </div>
    
    <script>
    async function deobfuscate() {
        const code = document.getElementById('code').value;
        const trace = document.getElementById('trace').value;
        const result = document.getElementById('result');
        
        if (!code.trim()) {
            result.innerHTML = '<p class="error">Please enter code!</p>';
            return;
        }
        
        result.innerHTML = '<p>⏳ Processing...</p>';
        
        try {
            const response = await fetch('/api/deobfuscate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({code, trace, pretty: true})
            });
            
            const data = await response.json();
            
            if (data.success) {
                result.innerHTML = '<p class="success">✅ Success!</p><textarea readonly style="height:300px">' + 
                    data.output.replace(/</g, '&lt;') + '</textarea>';
            } else {
                result.innerHTML = '<p class="error">❌ ' + data.error + '</p>';
            }
        } catch(e) {
            result.innerHTML = '<p class="error">❌ Error: ' + e.message + '</p>';
        }
    }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/deobfuscate', methods=['POST'])
def api_deobfuscate():
    try:
        data = request.json
        code = data.get('code', '')
        trace = data.get('trace', 'off')
        pretty = data.get('pretty', True)
        
        if not code:
            return jsonify({'success': False, 'error': 'No code provided'})
        
        request_id = str(uuid.uuid4())
        input_file = os.path.join(Config.UPLOAD_FOLDER, f'{request_id}.lua')
        output_file = os.path.join(Config.OUTPUT_FOLDER, f'{request_id}.deob.lua')
        
        with open(input_file, 'w') as f:
            f.write(code)
        
        cmd = [
            'lua', 'src/deob/cli.lua', input_file,
            '--out', output_file,
            '--trace', trace,
            '--pretty' if pretty else '--no-pretty'
        ]
        
        result = subprocess.run(
            cmd,
            cwd=Config.DEOBFUSCATOR_PATH,
            capture_output=True,
            text=True,
            timeout=Config.DEOB_TIMEOUT
        )
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                output = f.read()
            
            os.remove(input_file)
            os.remove(output_file)
            
            return jsonify({'success': True, 'output': output})
        else:
            return jsonify({'success': False, 'error': result.stderr or 'Deobfuscation failed'})
    
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Timeout exceeded'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.WEB_PORT)
