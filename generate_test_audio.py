import os
from gtts import gTTS

os.makedirs("test_audio", exist_ok=True)

tests = {
    "telugu": ("te", "మెషిన్ దగ్గర నేలపై నూనె పడింది. కార్మికులు జారిపడే ప్రమాదం ఉంది."),
    "hindi": ("hi", "मशीन के पास फर्श पर तेल गिरा हुआ है और काम करने वाले लोग फिसल सकते हैं।"),
    "assamese": ("bn", "মেছিনৰ ওচৰত মজিয়াত তেল পৰি আছে। শ্ৰমিকসকল পিছলি পৰাৰ আশংকা আছে।"), # gTTS doesn't have Assamese, using Bengali accent as proxy
    "english": ("en", "There is an exposed electrical wire near the machine.")
}

for name, (lang, text) in tests.items():
    tts = gTTS(text, lang=lang)
    filepath = f"test_audio/{name}_test.mp3"
    tts.save(filepath)
    print(f"Generated {filepath}")

