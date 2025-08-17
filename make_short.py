import requests, smtplib, os, json
from gtts import gTTS
from email.message import EmailMessage
import subprocess

# --- KONFIGURACJA ---
OPENROUTER_KEY = os.environ['OPENROUTER_KEY']
GMAIL_ADDR = os.environ['GMAIL_ADDR']
GMAIL_APP_PASSWORD = os.environ['GMAIL_APP_PASSWORD']

# 1. Pobierz przykładowy produkt (zamiast skomplikowanego scrapingu — stały link)
PRODUCT_URL = "https://www.aliexpress.com/item/1005006352712345.html"
PRODUCT_TITLE = "Portable Mini Blender USB"

# 2. Poproś OpenRouter o scenariusz shorta
prompt = f"""
Masz link do produktu: {PRODUCT_URL} oraz tytuł: {PRODUCT_TITLE}.
Stwórz DOKŁADNY plan 45-sekundowego YouTube Short (9:16) o tym produkcie.
W odpowiedzi zwróć TYLKO JSON w formacie:
{{ "title": "", "hashtags": ["",""], "narration": "pełna narracja do TTS (ok. 45s)", 
"scenes": [ {{"image_url":"", "duration":4, "text_overlay":"krótki napis"}}, ... ], 
"cta":"wezwanie do akcji" }}
"""
r = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800
    }
)
data = r.json()
text = data['choices'][0]['message']['content']
script = json.loads(text)

# 3. Wygeneruj narrację
tts = gTTS(script['narration'], lang='en')
tts.save("narration.mp3")

# 4. Pobierz obrazy
img_files = []
for i, scene in enumerate(script['scenes']):
    img_url = scene['image_url']
    img_data = requests.get(img_url).content
    fname = f"img{i}.jpg"
    with open(fname, "wb") as f:
        f.write(img_data)
    img_files.append((fname, scene['duration']))

# 5. Zbuduj listę plików dla FFmpeg
with open("inputs.txt", "w") as f:
    for fname, dur in img_files:
        f.write(f"file '{fname}'\n")
        f.write(f"duration {dur}\n")
    f.write(f"file '{img_files[-1][0]}'\n")  # ostatni raz, by zamknąć wideo

# 6. Złóż MP4 w pionie
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "inputs.txt", "-i", "narration.mp3",
    "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
           "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
    "-c:a", "aac", "-b:a", "128k", "-shortest", "output.mp4"
])

# 7. Wyślij e-mail z plikiem
msg = EmailMessage()
msg['Subject'] = f"Twój daily short: {script['title']}"
msg['From'] = GMAIL_ADDR
msg['To'] = GMAIL_ADDR
msg.set_content("Oto Twój short dnia.")

with open("output.mp4", "rb") as f:
    msg.add_attachment(f.read(), maintype="video", subtype="mp4", filename="short.mp4")

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
    smtp.login(GMAIL_ADDR, GMAIL_APP_PASSWORD)
    smtp.send_message(msg)
