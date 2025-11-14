from quart import Quart, jsonify, request, send_file
import requests
import asyncio
import os
import json
import random
import time
import datetime
import aiohttp
import PIL
from PIL import Image, ImageEnhance, ImageFilter
import imageio
import pytesseract
import base64
import sympy as sp
import re
import nltk  # For basic summarization (install with pip install nltk)
from spellchecker import SpellChecker  # New import for spell-checking
spell = SpellChecker()

app = Quart(__name__)
picture = 'kilgore.gif'
imagepath = f'/home/brokslinux/Downloads/kilgore/{picture}'
humandictionarywords = {"hi", "my", "name", "Mika"}

@app.route('/kilgore.gif')
async def serve_gif():
    return await send_file(imagepath, mimetype='image/gif')

def summarize_text(text, max_sentences=2):
    from nltk.tokenize import sent_tokenize
    sentences = sent_tokenize(text)
    return ' '.join(sentences[:max_sentences]) if sentences else text


def preprocess_image(img):
    # Convert to grayscale
    img = img.convert('L')
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)
    # Binarize (threshold) for clearer text
    img = img.point(lambda x: 0 if x < 128 else 255, '1')  # Black/white
    # Resize if too small
    if img.width < 300:
        img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
    return img

def correct_text(text):
    words = text.split()
    corrected = []
    for word in words:
        if word in spell:
            corrected.append(word)
        else:
            suggestions = spell.candidates(word)
            corrected.append(list(suggestions)[0] if suggestions else word)  # Use first suggestion or keep original
    return ' '.join(corrected)

def analyze_image_text(text, confidence):
    if confidence < 40:
        return "OCR confidence low. Please retake screenshot with clearer text."
    
    # Spell-correct first
    corrected_text = correct_text(text)
    
    # Filter words
    original_words = corrected_text.split()
    filtered_words = [word for word in original_words if word.lower() not in humandictionarywords]
    filtered_text = ' '.join(filtered_words)
    
    # If filtering removes too much (>50% of words), use full corrected text
    if len(filtered_words) < len(original_words) * 0.5:
        filtered_text = corrected_text
    
    if not filtered_text.strip():
        return "Insignificant text."
    
    math_pattern = r'[0-9+\-*/=()x^]'
    if re.search(math_pattern, filtered_text):
        try:
            result = sp.sympify(filtered_text)
            search_url = f"https://api.duckduckgo.com/?q={filtered_text}&format=json&no_html=1"
            response = requests.get(search_url, timeout=5)
            data = response.json()
            context = data.get('Abstract', data.get('Answer', 'No additional context.'))
            return f"Math solution: {result}. Context: {context}"
        except:
            return f"Math detected but unable to solve: {filtered_text}"
    
    # Improved summarization: If <3 sentences, extract keywords
    sentences = nltk.sent_tokenize(filtered_text)
    if len(sentences) >= 3:
        return f"Summary: {summarize_text(filtered_text)}"
    else:
        # Keyword extraction
        words = nltk.word_tokenize(filtered_text)
        keywords = [word for word in words if word.isalnum() and len(word) > 3][:5]  # Top 5 long words
        return f"Key topics: {' '.join(keywords)}"


@app.route('/upload-screenshot', methods=['POST'])
async def upload_screenshot():
    data = await request.get_json()
    image_data = data['image']
    
    header, encoded = image_data.split(',', 1)
    image_bytes = base64.b64decode(encoded)
    
    os.makedirs('screenshots', exist_ok=True)
    filename = f"screenshot_{int(time.time())}.png"
    filepath = os.path.join('screenshots', filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    
    img = Image.open(filepath)
    processed_img = preprocess_image(img)
    # OCR with config
    custom_config = r'--oem 3 --psm 6'
    extracted_text = pytesseract.image_to_string(processed_img, config=custom_config).strip()
    # Get confidence
    data = pytesseract.image_to_data(processed_img, config=custom_config, output_type=pytesseract.Output.DICT)
    confidence = sum([c for c in data['conf'] if c != -1]) / len([c for c in data['conf'] if c != -1]) if data['conf'] else 0
    
    # Fallback if confidence still low
    if confidence < 40:
        custom_config_fallback = r'--oem 3 --psm 3'
        extracted_text = pytesseract.image_to_string(processed_img, config=custom_config_fallback).strip()
        data = pytesseract.image_to_data(processed_img, config=custom_config_fallback, output_type=pytesseract.Output.DICT)
        confidence = sum([c for c in data['conf'] if c != -1]) / len([c for c in data['conf'] if c != -1]) if data['conf'] else 0
    
    analysis = analyze_image_text(extracted_text, confidence)
    
    return jsonify({
        "message": "Screenshot saved and analyzed",
        "filename": filename,
        "analysis": analysis
    }), 200



@app.route('/', methods=['GET'])
async def main_page():
    return f"""
    <!DOCTYPE html>
<html lang="en">
<head>
  <title>kilgore (GIDEON)</title>
  <style>
    body {{
      background-color: black;
      background-size: cover;
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      font-family: 'Courier New', monospace;
      color: #ff00ff;
      margin: 0;
      opacity: 0;
      transition: opacity 0.8s ease;
      overflow: hidden;
    }}

    body.loaded {{
      opacity: 1;
    }}

    #kilgore-gif {{
      position: absolute;
      top: 10px;
      left: 10px;
      width: 200px;
      height: auto;
    }}

        <!-- In the HTML body -->
<div id="black-square">
  <span id="typed-text"></span><span id="cursor">|</span>
</div>

<!-- In the <style> -->
#black-square {{
  width: 300px; /* Back to larger for text display */
  height: 40px; /* Taller for text */
  background-color: #ff00ff;
  border: none;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: flex-start; /* Left-align text */
  font-size: 14px;
  color: black;
  padding: 5px;
  overflow: hidden;
}}

#typed-text {{
  white-space: pre-wrap;
}}

#cursor {{
  animation: blink 1s infinite;
  margin-left: 2px;
}}

@keyframes blink {{
  0%, 50% {{ opacity: 1; }}
  51%, 100% {{ opacity: 0; }}
}}


    #camera-controls {{
      position: absolute;
      top: 20px;
      right: 20px;
      z-index: 3;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }}

    #camera-dropdown {{
      margin-bottom: 10px;
      background-color: #ff00ff;
      color: black;
      border: none;
      padding: 5px;
    }}

    #screenshot-btn {{
      width: 50px;
      height: 50px;
      border-radius: 50%;
      background-color: white;
      border: none;
      display: none;
      cursor: pointer;
      margin-top: 10px;
    }}

    #video {{
      position: absolute;
      bottom: 20px;
      right: 20px;
      width: 300px;
      height: 200px;
      border: 2px solid #ff00ff;
      z-index: 2;
    }}

    #canvas {{
      display: none;
    }}
  </style>
</head>
<body>
  <img id="kilgore-gif" src="/kilgore.gif" alt="Kilgore GIF">
  <div id="black-square">
    <span id="typed-text"></span>
  </div>
  <div id="camera-controls">
    <select id="camera-dropdown">
      <option value="">Select Camera</option>
    </select>
    <button id="screenshot-btn" title="Take Screenshot"></button>
  </div>
  <video id="video" autoplay></video>
  <canvas id="canvas"></canvas>

  <script>
    window.addEventListener('load', () => {{
      document.body.classList.add('loaded');
    }});

    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    const dropdown = document.getElementById('camera-dropdown');
    const screenshotBtn = document.getElementById('screenshot-btn');
    const typedText = document.getElementById('typed-text');

    let currentStream = null;

    async function populateCameras() {{
      try {{
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(device => device.kind === 'videoinput');
        videoDevices.forEach(device => {{
          const option = document.createElement('option');
          option.value = device.deviceId;
          option.text = device.label || `Camera ${{dropdown.options.length}}`;
          dropdown.appendChild(option);
        }});
      }} catch (error) {{
        console.error('Error enumerating devices:', error);
      }}
    }}

    async function startCamera(deviceId) {{
      try {{
        if (currentStream) {{
          currentStream.getTracks().forEach(track => track.stop());
        }}
        const constraints = {{
          video: {{ deviceId: deviceId ? {{ exact: deviceId }} : undefined }}
        }};
        currentStream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = currentStream;
        screenshotBtn.style.display = 'block';
      }} catch (error) {{
        console.error('Error accessing camera:', error);
        screenshotBtn.style.display = 'none';
      }}
    }}

    dropdown.addEventListener('change', () => {{
      const deviceId = dropdown.value;
      if (deviceId) {{
        startCamera(deviceId);
      }} else {{
        if (currentStream) {{
          currentStream.getTracks().forEach(track => track.stop());
          video.srcObject = null;
          screenshotBtn.style.display = 'none';
        }}
      }}
    }});

    // Typing function for summary
    function typeWriter(text, element, speed = 100) {{
      let i = 0;
      element.textContent = '';
      function type() {{
        if (i < text.length) {{
          element.textContent += text.charAt(i);
          i++;
          setTimeout(type, speed);
        }}
      }}
      type();
    }}

    screenshotBtn.addEventListener('click', async () => {{
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0);
      const dataURL = canvas.toDataURL('image/png');
      
      try {{
        const response = await fetch('/upload-screenshot', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
          }},
          body: JSON.stringify({{ image: dataURL }}),
        }});
        const result = await response.json();
        // Type the analysis into the square
        typeWriter(result.analysis, typedText);
      }} catch (error) {{
        console.error('Error uploading screenshot:', error);
        typeWriter('Analysis failed.', typedText);
      }}
    }});

    populateCameras();
  </script>
</body>
</html>
    """

if __name__ == "__main__":
    asyncio.run(app.run_task(host="0.0.0.0", port=8080))

