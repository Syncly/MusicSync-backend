#!/usr/bin/env python3

"""
Downloads music from youtube
"""
from boto3.session import Session
from concurrent.futures import ThreadPoolExecutor
from sseclient import SSEClient
from pprint import pprint
import json
import io
import binascii

file_objects = {}

from config import *

session = Session(aws_access_key_id=S3_ACCESS_KEY,
                  aws_secret_access_key=S3_SECRET_KEY,
                  region_name=S3_REGION)

storage = session.resource("s3").Bucket(S3_BUCKET)

def fake_close():
    return

## Monkeypatch downloader
import youtube_dl.downloader.http
orig_sanitize_open = youtube_dl.downloader.http.sanitize_open
def fake_sanitize_open(file_name, open_mode):
    #stream, new_filename = orig_sanitize_open(file_name, open_mode)
    #print(stream, file_name, new_filename)
    stream = io.BytesIO()
    stream.real_close = stream.close
    stream.close = fake_close
    file_objects[file_name] = stream
    new_filename = file_name
    print(stream, new_filename)
    return (stream, new_filename)
youtube_dl.downloader.http.sanitize_open = fake_sanitize_open

import youtube_dl

ydl_opts = {
    "format":"172/171/141/140/bestaudio",
    "outtmpl": "%(id)s",
    "nopart": True, # disable file rename
    "verbose": True
}

def download_song(song_id):
    print("downloading song ", song_id)
    print(youtube_dl.downloader.http.sanitize_open)
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.download([song_id])
        pprint(info)
    stream = file_objects.get(song_id)
    print(song_id)
    if not stream:
        print("[download] failed for", song_id)
        return
    else:
        print("[upload] Starting")
        stream = io.BytesIO(stream.getvalue())
        del file_objects[song_id]
        try:
            storage.put_object(Key=song_id, ACL='public-read', Body=stream)
            print("[upload] Done")
        except Exception as err:
            import traceback
            traceback.print_exc()
            print("[upload] Failed")


executor = ThreadPoolExecutor(max_workers=4)

print("listening for events")

messages = SSEClient('http://localhost/sub/event')
for msg in messages:
    msg.data = json.loads(msg.data)
    print(msg.event, msg.data["title"])
    if msg.event in ("YoutubeSongAdded", "YoutubeSongReAdded"):
        print("submitting job", msg.data["_id"])
        executor.submit(download_song, msg.data["_id"])
