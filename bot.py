import feedparser, requests, time, os, re
from deep_translator import GoogleTranslator
TOKEN = "8802244586:AAGIC6ffEBEUhGQ7La10DWZ4XKAelbGRmrs"
CHAT = "-1004269793711"
FEEDS = ["https://api.axios.com/feed/top/"]
K = r"\b(iran|trump|netanyahu|israel|gaza|hamas|hezbollah|houthi|lebanon|syria|iraq|yemen|saudi|qatar|ceasefire|missile|airstrike|war|nuclear|middle east|breaking|urgent)\b"
URL = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
seen = set(open("seen.txt").read().split()) if os.path.exists("seen.txt") else set()
first = True
while True:
    for f in FEEDS:
        try:
            for e in reversed(feedparser.parse(f).entries):
                if e.link in seen:
                    continue
                seen.add(e.link)
                open("seen.txt", "a").write(e.link + "\n")
                t = e.title + " " + e.get("summary", "")
                rv = "ravid" in e.get("author", "").lower()
                if not first and (rv or re.search(K, t.lower())):
                    try:
                        ar = GoogleTranslator(source="auto", target="ar").translate(e.title)
                    except Exception:
                        ar = e.title
                    requests.post(URL, data={"chat_id": CHAT, "text": ("🔴 باراك رافيد | " if rv else "") + ar + "\n" + e.link})
        except Exception as ex:
            print(ex)
    first = False
    time.sleep(10)
