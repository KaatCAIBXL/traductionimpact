from flask import Flask, request, jsonify, send_from_directory
import tempfile, os
from openai import OpenAI
import deepl
from flask_cors import CORS
import speech_recognition as sr
import pygame
import edge_tts
from dotenv import load_dotenv
from datetime import datetime
import threading
import asyncio

# -------------------- APP CONFIG --------------------
app = Flask("traductionimpact", static_folder="static")
CORS(app)
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
deepl_translator = deepl.Translator(DEEPL_API_KEY)

ENKEL_TEKST_MODUS = False  # False = met stem, True = enkel tekst
vorige_zinnen = []  # wordt gebruikt voor contextuele correctie


# -------------------- ROUTES --------------------
@app.route("/")
def home():
    return send_from_directory("static", "index.html")


# -------------------- CONTEXTUELE CORRECTIE --------------------
def corrigeer_zin_met_context(nieuwe_zin, vorige_zinnen):
    """Corrigeert de nieuwe zin op basis van de laatste drie zinnen (context)."""
    if not nieuwe_zin.strip():
        return nieuwe_zin

    context = " ".join(vorige_zinnen[-3:])

    with open("instructies_correctie.txt", "r", encoding="utf-8") as f:
        woordenlijst = f.read()
    prompt = f"""
    Je bent een taalassistent die controleert of een nieuwe zin logisch is binnen een context.
    Context: "{context}"
    Nieuwe zin: "{nieuwe_zin}"
    If you detect a Bible-vers, a prayer or something like 'pap' or 'bab' look at this file for instructions. 
    {instructies_correctie}

    Gebruik dezelfde taal als de originele zin en behoud de natuurlijke stijl.
    Geef enkel de verbeterde zin terug, zonder uitleg.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        verbeterd = response.choices[0].message.content.strip()
        return verbeterd
    except Exception as e:
        print(f"[!] Fout bij contextuele correctie: {e}")
        return nieuwe_zin


# -------------------- STEMFUNCTIE --------------------
def spreek_tekst_synchroon(tekst, taalcode, spreek_uit=True):
    """Leest de tekst voor als 'spreek_uit' True is, anders enkel tekst."""
    if not spreek_uit:
        return

    stemmap = {
        "nl": "nl-NL-MaartenNeural",
        "fr": "fr-FR-DeniseNeural",
        "PT-BR": "pt-BR-AntonioNeural",
        "ZH-HANS": "zh-CN-XiaoxiaoNeural",
        "es": "es-ES-AlvaroNeural",
        "ln": "sw-KE-ZuriNeural",
        "ar": "ar-EG-SalmaNeural",
        "hi": "hi-IN-MadhurNeural",
        "sv": "sv-SE-MattiasNeural",
        "fi": "fi-FI-SelmaNeural",
        "sw": "sw-KE-ZuriNeural",
        "mg": "pt-BR-AntonioNeural",
        "EN-US": "en-CA-ClaraNeural",
    }

    stem = stemmap.get(taalcode, "en-US-AriaNeural")
    mp3_bestand = "tts_audio.mp3"

    async def async_save_and_play():
        communicate = edge_tts.Communicate(tekst, stem)
        await communicate.save(mp3_bestand)

        pygame.mixer.init()
        pygame.mixer.music.load(mp3_bestand)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.quit()
        os.remove(mp3_bestand)

    asyncio.run(async_save_and_play())


# -------------------- DEEPL HELPER --------------------
def map_vertaling_taalcode_deepl(taalcode):
    """Past taalcodes aan naar het formaat dat DeepL vereist."""
    if taalcode.lower() == "en-us":
        return "EN-US"
    elif taalcode.lower() == "pt-br":
        return "PT-BR"
    elif taalcode.lower() == "zh-hans":
        return "ZH"
    else:
        return taalcode.upper()


# -------------------- HOOFDROUTE: LIVE AUDIO --------------------
@app.route("/api/translate", methods=["POST"])

def vertaal_audio():
    """Hoofdfunctie: ontvangt audio, transcribeert, corrigeert, vertaalt, spreekt uit."""
    global vorige_zinnen

    if "audio" not in request.files:
        return jsonify({"error": "Geen audio ontvangen"}), 400

    audio_file = request.files["audio"]
    bron_taal = request.form.get("from", "fr")
    doel_taal = request.form.get("to", "nl")
    enkel_tekst = request.form.get("textOnly", "false") == "true"

    # tijdelijke opslag
    ext = os.path.splitext(audio_file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        audio_file.save(tmp.name)
        audio_path = tmp.name

    try:
        # 🎧 Stap 1: Transcriberen via Whisper
        with open(audio_path, "rb") as af:
            transcript_response = openai_client.audio.transcriptions.create(
                model="whisper-1", file=af, language=bron_taal
            )
        tekst = transcript_response.text.strip()
        if not tekst:
            return jsonify({"error": "Geen spraak gedetecteerd."}), 400

        # ✍️ Stap 2: Contextuele correctie
        verbeterde_zin = corrigeer_zin_met_context(tekst, vorige_zinnen)
        vorige_zinnen.append(verbeterde_zin)

        # 🌍 Stap 3: Vertalen
        if doel_taal == 'lua':
            with open("instructies_Tshiluba.txt", "r", encoding="utf-8") as f:
                Tshiluba = f.read()
            messages = [
                {"role": "system",
                 "content": f"""
                 You are a translator. Translate from {bron_taal} to Tshiluba. If unsure look at the following file
                 {Tshiluba} if you still dont know a word,use a similar with the same meaning or at least close, otherwise use a French fallback.
                               """},
                {"role": "user", "content": verbeterde_zin},
            ]
            chat_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo", messages=messages, temperature=0.7
            )
            vertaling = chat_response.choices[0].message.content.strip()
            # 📝 Stap 4: Wegschrijven naar live_vertaal.html
            for zin in live_input_stream:
                verbeterde_zin = verbeter(zin)
                vertaling = vertaal(verbeterde_zin)
                tijd = datetime.now().strftime("%H:%M:%S")
                bron_taal = detecteer_bron_taal(zin)
                doel_taal = gekozen_doeltaal

                with open("live_vertaal.html", "a", encoding="utf-8") as f:
                    f.write(f"""
                                <div class="fragment">
                                  <div class="tijd">⏱️ {tijd}</div>
                                  <div class="origineel">
                                    <span class="label">Origineel ({bron_taal}):</span>
                                    <span class="zin">{verbeterde_zin}</span>
                                  </div>
                                  <div class="vertaling">
                                    <span class="label">Vertaling ({doel_taal}):</span>
                                    <span class="zin">{vertaling}</span>
                                  </div>
                                </div>
                                """)

        talen_zonder_deepl_support = ["kg", "dyu", "bci", "ln", "am", "mg", "sw"]
        if doel_taal in talen_zonder_deepl_support:
            messages = [
                {"role": "system",
                 "content": f"You are a translator. Translate from {bron_taal} to {doel_taal}. If unsure, use a French fallback."},
                {"role": "user", "content": verbeterde_zin},
            ]
            chat_response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo", messages=messages, temperature=0.7
            )
            vertaling = chat_response.choices[0].message.content.strip()

            # 📝 Stap 4: Wegschrijven naar live_vertaal.html
            for zin in live_input_stream:
                verbeterde_zin = verbeter(zin)
                vertaling = vertaal(verbeterde_zin)
                tijd = datetime.now().strftime("%H:%M:%S")
                bron_taal = detecteer_bron_taal(zin)
                doel_taal = gekozen_doeltaal

                with open("live_vertaal.html", "a", encoding="utf-8") as f:
                    f.write(f"""
                                    <div class="fragment">
                                      <div class="tijd">⏱️ {tijd}</div>
                                      <div class="origineel">
                                        <span class="label">Origineel ({bron_taal}):</span>
                                        <span class="zin">{verbeterde_zin}</span>
                                      </div>
                                      <div class="vertaling">
                                        <span class="label">Vertaling ({doel_taal}):</span>
                                        <span class="zin">{vertaling}</span>
                                      </div>
                                    </div>
                                    """)

        else:
            doel_taal_code = map_vertaling_taalcode_deepl(doel_taal)
            result = deepl_translator.translate_text(
                verbeterde_zin, source_lang=bron_taal, target_lang=doel_taal_code
            )
            vertaling = result.text
            # 📝 Stap 4: Wegschrijven naar live_vertaal.html
            for zin in live_input_stream:
                verbeterde_zin = verbeter(zin)
                vertaling = vertaal(verbeterde_zin)
                tijd = datetime.now().strftime("%H:%M:%S")
                bron_taal = detecteer_bron_taal(zin)
                doel_taal = gekozen_doeltaal

                with open("live_vertaal.html", "a", encoding="utf-8") as f:
                    f.write(f"""
                                    <div class="fragment">
                                      <div class="tijd">⏱️ {tijd}</div>
                                      <div class="origineel">
                                        <span class="label">Origineel ({bron_taal}):</span>
                                        <span class="zin">{verbeterde_zin}</span>
                                      </div>
                                      <div class="vertaling">
                                        <span class="label">Vertaling ({doel_taal}):</span>
                                        <span class="zin">{vertaling}</span>
                                      </div>
                                    </div>
                                    """)


        # 🔊 Stap 5: Stem afspelen (indien niet enkel tekstmodus)
        play_thread = threading.Thread(
            target=spreek_tekst_synchroon,
            args=(vertaling, doel_taal, not enkel_tekst),
        )
        play_thread.start()

        # 🔁 Stap 6: JSON terug naar browser
        return jsonify({"original": verbeterde_zin, "translation": vertaling})

    except Exception as e:
        print(f"[!] Onverwachte fout: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

@app.route("/resultaat")
def resultaat():
    return send_from_directory(".", "live_vertaal.html")

with open("live_vertaal.html", "a", encoding="utf-8") as f:
    f.write("</body></html>")


# -------------------- START SERVER --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
