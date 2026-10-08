#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بوت أخبار تلكرام - نسخة بايثون
التشغيل مرة وحدة:      python bot.py
التشغيل بشكل متكرر:    python bot.py --loop 300     (كل 300 ثانية)
المتطلبات:             pip install requests
"""
import fcntl
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

# ================== الإعدادات ==================
TOKEN = os.environ.get("TG_TOKEN", "8802244586:AAGIC6ffEBEUhGQ7La10DWZ4XKAelbGRmrs")   # توكن البوت (يفضل من متغير بيئة)
CHAT = os.environ.get("TG_CHAT", "-1004269793711")         # رقم القناة
MAX_SEND = 6                                               # أقصى عدد رسائل بالدورة الواحدة

KW = re.compile(
    r"\b(iran|iranian|tehran|iraq|baghdad|syria|damascus|lebanon|beirut|israel|israeli|netanyahu|gaza|hamas|"
    r"hezbollah|palestinian|west bank|jordan|egypt|turkey|erdogan|libya|sudan|saudi|riyadh|yemen|yemeni|houthi|"
    r"houthis|red sea|gulf|qatar|doha|kuwait|bahrain|oman|uae|emirates|dubai|middle east|trump|idf|irgc|"
    r"ceasefire|war|conflict|invasion|troops|military|attack|attacks|strike|strikes|airstrike|airstrikes|"
    r"missile|missiles|rocket|drone|drones|explosion|blast|bomb|killed|casualties|clashes|hostage|hostages|"
    r"terror|nuclear|sanctions|breaking|urgent|just in)\b",
    re.I,
)

UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
DIR = Path(__file__).resolve().parent / "data"
MRSS = "http://search.yahoo.com/mrss/"


# ================== دوال ==================
def http_get(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=10, allow_redirects=True)
        return r.text
    except Exception:
        return ""


def tg(method, params):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", data=params, timeout=25)
        j = r.json()
    except Exception as e:
        print(f"tg {method} error: {e}")
        return False
    if not j.get("ok"):
        print(f"tg {method} error: {r.text[:150]}")
    return bool(j.get("ok"))


def tr_ar(text):
    text = (text or "").strip()
    if not text:
        return ""
    # 1) Google
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "ar", "dt": "t", "q": text},
            headers={"User-Agent": UA},
            timeout=10,
        )
        j = r.json()
        out = "".join((p[0] or "") for p in j[0] if p)
        if out:
            return out
    except Exception:
        pass
    # 2) MyMemory
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"langpair": "en|ar", "q": text[:450]},
            headers={"User-Agent": UA},
            timeout=10,
        )
        t = r.json().get("responseData", {}).get("translatedText", "")
        return t or text
    except Exception:
        return text


def clean(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def send_item(cap, img):
    cap = cap[:1000]
    if img:
        gif = bool(re.search(r"\.gif(\?|$)", img, re.I))
        ok = tg(
            "sendAnimation" if gif else "sendPhoto",
            {"chat_id": CHAT, ("animation" if gif else "photo"): img, "caption": cap},
        )
        if ok:
            return
    tg("sendMessage", {"chat_id": CHAT, "text": cap})


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def ns_of(tag):
    return tag[1:].split("}", 1)[0] if isinstance(tag, str) and tag.startswith("{") else ""


# قراءة RSS أو Atom
def parse_feed(xml):
    if not xml:
        return []
    try:
        root = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except ET.ParseError:
        return []
    out = []
    for n in root.iter():
        if local(n.tag) not in ("item", "entry"):
            continue
        link = author = img = title = desc = summ = cont = ""
        for c in n:
            nm, ns = local(c.tag), ns_of(c.tag)
            txt = (c.text or "").strip()
            if nm == "link":
                h = c.get("href", "")
                if h and not link and c.get("rel", "alternate") == "alternate":
                    link = h
                elif not h and txt and not link:
                    link = txt
            elif nm == "title":
                title = txt
            elif nm == "author":
                name = next((x for x in c if local(x.tag) == "name"), None)
                author = (name.text or "").strip() if name is not None else txt
            elif nm == "creator" and not author:
                author = txt
            elif ns == MRSS and nm == "content" and not img:
                img = c.get("url", "")
            elif ns == MRSS and nm == "thumbnail" and not img:
                img = c.get("url", "")
            elif nm == "description":
                desc = txt
            elif nm == "summary":
                summ = txt
            elif nm == "content" and ns != MRSS:
                cont = txt
        if not link:
            continue
        out.append({
            "link": link,
            "title": clean(title),
            "summary": clean(desc or summ or cont),
            "author": author,
            "img": img,
        })
    return out


# ================== المصادر ==================
def src_axios():
    return parse_feed(http_get("https://api.axios.com/feed/top/"))


def src_reuters():
    x = http_get("https://www.reuters.com/arc/outboundfeeds/news-sitemap/?outputType=xml")
    out = []
    for b in re.findall(r"<url>(.*?)</url>", x, re.S):
        l = re.search(r"<loc>(.*?)</loc>", b, re.S)
        t = re.search(r"<news:title>(.*?)</news:title>", b, re.S)
        if not l or not t:
            continue
        title = clean(t.group(1).replace("<![CDATA[", "").replace("]]>", ""))
        i = re.search(r"<image:loc>(.*?)</image:loc>", b, re.S)
        img = html.unescape(i.group(1).strip()) if i else ""
        out.append({"link": l.group(1).strip(), "title": title, "summary": "", "author": "", "img": img})
    return out


def src_afp():
    from urllib.parse import quote_plus
    q = '"Agence France-Presse" OR "(AFP)" when:1d'
    items = parse_feed(http_get("https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=en-US&gl=US&ceid=US:en"))
    for it in items:
        it["title"] = re.sub(r"\s+-\s+[^-]+$", "", it["title"]).strip()
        it["summary"] = ""
    return items


SOURCES = {"Axios": src_axios, "Reuters": src_reuters, "AFP": src_afp}

# مصادر RSS مباشرة: ضيف اي مصدر جديد بسطر واحد
RSS = {
    "WaPo": "https://feeds.washingtonpost.com/rss/world",
    "BBC": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "AlJazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "NYTimes": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "Guardian": "https://www.theguardian.com/world/rss",
    "SkyNews": "https://feeds.skynews.com/feeds/rss/world.xml",
    "France24": "https://www.france24.com/en/rss",
    "TimesOfIsrael": "https://www.timesofisrael.com/feed/",
}
for _n, _u in RSS.items():
    SOURCES[_n] = (lambda u=_u: parse_feed(http_get(u)))

EMOJI = {"Axios": "🟣", "Reuters": "🟠", "AFP": "🔵"}


# ================== التشغيل ==================
def run_once():
    DIR.mkdir(parents=True, exist_ok=True)
    lock = open(DIR / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("busy")
        return

    state_file = DIR / "state.json"
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}
    seen = state.get("seen", {})
    init = state.get("init", {})

    sent = 0
    for name, fn in SOURCES.items():
        try:
            items = fn()
        except Exception as e:
            print(f"{name} error: {e}")
            continue
        if not items:
            print(f"{name}: no items")
            continue
        is_init = not init.get(name)

        for it in reversed(items):
            id_ = it["link"]
            if id_ in seen:
                continue
            if is_init:
                seen[id_] = time.time()
                continue

            rv = "ravid" in it["author"].lower()
            match = rv or KW.search(it["title"] + " " + it["summary"])
            tkey = "t:" + hashlib.md5(re.sub(r"\W+", "", it["title"].lower()).encode("utf-8")).hexdigest()[:16]

            if not match or tkey in seen:
                seen[id_] = time.time()
                continue
            if sent >= MAX_SEND:
                break  # الباقي ينرسل بالدورة الجاية

            cap = ("🔴 باراك رافيد | " if rv else "") + EMOJI.get(name, "⚪") + f" [{name}] " + tr_ar(it["title"])
            if name == "Axios" and it["summary"]:
                cap += "\n\n" + tr_ar(it["summary"][:300])
            cap = cap[:900] + "\n\n" + it["link"]

            send_item(cap, it["img"])
            seen[id_] = time.time()
            seen[tkey] = time.time()
            sent += 1
            time.sleep(1)
        if is_init:
            init[name] = True
            print(f"{name}: initialized")

    # حفظ
    seen = dict(sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:3000])
    state_file.write_text(json.dumps({"seen": seen, "init": init}), encoding="utf-8")
    print(f"done, sent {sent}")


def main():
    if "--test" in sys.argv:
        tg("sendMessage", {"chat_id": CHAT, "text": "test"})
        print("test sent")
        return
    if "--loop" in sys.argv:
        i = sys.argv.index("--loop")
        every = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 300
        while True:
            run_once()
            time.sleep(every)
    else:
        run_once()


if __name__ == "__main__":
    main()
