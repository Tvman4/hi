import os
import zipfile
import re
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/')
index():
    return render_template('index.html')

@app.route('/api/patch', methods=['POST'])
def patch_apk():
    if 'apk' not in request.files or 'dll' not in request.files:
        return jsonify({'error': 'Missing APK or DLL file'}), 400
    
    apk_file = request.files['apk']
    dll_file = request.files['dll']
    
    apk_path = os.path.join(UPLOAD_FOLDER, apk_file.filename)
    dll_path = os.path.join(UPLOAD_FOLDER, dll_file.filename)
    apk_file.save(apk_path)
    dll_file.save(dll_path)
    
    output_apk_name = f"patched_{apk_file.filename}"
    output_apk_path = os.path.join(OUTPUT_FOLDER, output_apk_name)
    
    try:
        # Unity APK structure handling: Replace DLL inside managed assets
        with zipfile.ZipFile(apk_path, 'r') as zin:
            with zipfile.ZipFile(output_apk_path, 'w') as zout:
                dll_replaced = False
                for item in zin.infolist():
                    buffer = zin.read(item.filename)
                    # Look for Unity managed folder path inside APK structure
                    if 'assets/bin/Data/Managed/' in item.filename and item.filename.endswith('.dll'):
                        if os.path.basename(item.filename).lower() == os.path.basename(dll_path).lower():
                            with open(dll_path, 'rb') as f_dll:
                                buffer = f_dll.read()
                            dll_replaced = True
                    zout.writestr(item, buffer)
                
                # If standard path wasn't found directly, inject it explicitly
                if not dll_replaced:
                    with open(dll_path, 'rb') as f_dll:
                        zout.writestr(f"assets/bin/Data/Managed/{os.path.basename(dll_path)}", f_dll.read())
                        
        return jsonify({'success': True, 'download_url': f'/api/download/{output_apk_name}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/extract', methods=['POST'])
def extract_ids():
    if 'apk' not in request.files:
        return jsonify({'error': 'Missing APK file'}), 400
    
    apk_file = request.files['apk']
    apk_path = os.path.join(UPLOAD_FOLDER, apk_file.filename)
    apk_file.save(apk_path)
    
    playfab_ids = set()
    photon_ids = set()
    
    try:
        with zipfile.ZipFile(apk_path, 'r') as zin:
            for item in zin.infolist():
                if item.filename.endswith('.dll') or item.filename.endswith('.json') or 'assets/bin/Data/' in item.filename:
                    try:
                        data = zin.read(item.filename)
                        # Search patterns for PlayFab ( genellikle 4-5 uppercase alphanumeric chars) and Photon Guids
                        text_content = data.decode('latin-1', errors='ignore')
                        
                        # Regex match examples for typical App/Title structures
                        pf_matches = re.findall(r'\b[A-F0-9]{4,6}\b', text_content)
                        pt_matches = re.findall(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', text_content, re.IGNORECASE)
                        
                        for m in pf_matches:
                            if len(m) == 5: # Common length for PlayFab Title ID
                                playfab_ids.add(m)
                        for m in pt_matches:
                            photon_ids.add(m)
                    except:
                        continue
                        
        return jsonify({
            'success': True,
            'playfab': list(playfab_ids)[:5], # limit output clutter
            'photon': list(photon_ids)[:5]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
