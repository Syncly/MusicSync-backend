#!/usr/bin/env python3

"""
Downloads music from youtube
"""
from concurrent.futures import ThreadPoolExecutor
from sseclient import SSEClient
import json
import youtube_dl
from pprint import pprint

ydl_opts = {
    "format":"172/171/141/140/bestaudio"
}


def download_song(song_id):
    print("downloading song ", song_id)
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.download([song_id])
        pprint(info)

executor = ThreadPoolExecutor(max_workers=4)

print("listening for events")

messages = SSEClient('http://localhost/sub/event')
for msg in messages:
    msg.data = json.loads(msg.data)
    print(msg.event, msg.data["title"])
    if msg.event in ("YoutubeSongAdded", "YoutubeSongReAdded"):
        print("submitting job", msg.data["_id"])
        executor.submit(download_song, msg.data["_id"])
