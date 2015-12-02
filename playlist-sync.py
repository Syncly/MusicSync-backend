#!/usr/bin/env python3

"""sync a youtube playlist
"""

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
import youtube_dl
from pprint import pprint
import requests
import json
import traceback
from config import *

ydl_opts = {
    "quiet":True
}

pl_url = "https://www.youtube.com/playlist?list=PLB5VrND_o3PgZNzNdohFDWE5BTFIPDImQ"

client = MongoClient()
db = client["MusicSync"]


def gen_event_id(event_name):
    """ generates a constanly increasing stream of numbers
    """
    c = db.counters.find_one_and_update({"_id":event_name},
                                        {"$inc": {"c":1}},
                                        return_document=ReturnDocument.AFTER)
    if c:
        return c["c"]
    else:
        db.counters.insert({"_id": event_name, "c":0})
        return 0

def create_event(event_type, *args, **kwargs):
    """ inserts a event into the event database
    """
    ev = {
        "_id": gen_event_id("events"),
        "event": event_type,
        "data": kwargs
    }
    db["events"].insert_one(ev)
    send_sse_event(ev["_id"], ev["event"], kwargs)
    pprint(ev)

def send_sse_event(event_id, event_type, data):
    """ Pushes a event to nginx push stream publish point
    """
    sse_f = "id:{}\nevent:{}\ndata:{}\n\n"
    r = requests.post(NGINX_EVENTS_PUB, sse_f.format(event_id, event_type, json.dumps(data)))

def get_song_updates(playlist_id):
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(playlist_id, download=False, process=False)
        pl = {
            "_id": info["id"],
            "title": info["title"],
            "type": "YoutubePlaylist"
        }
        try:
            db["playlists"].insert_one(pl)
        except DuplicateKeyError as err:
            pass
        entries = list(info["entries"])
        songs = set()
        for e in entries:
            s = {
                "_id": e["id"],
                "title": e["title"],
                "playlist": info["id"],
                "type":"Youtube",
                "deleted":False
            }
            if not db["songs"].find_one(e["id"]):
                create_event("YoutubeSongAdded", **s)
                db["songs"].insert_one(s)
            elif db["songs"].find_one_and_update({"_id":e["id"], "deleted": True},
                                    {"$set": {"deleted":False}}):
                create_event("YoutubeSongReAdded", **s)
            songs.add(s["_id"])

        for e in db["songs"].find({"playlist":info["id"],"$or":[{"deleted": {"$exists": False}}, {"deleted": False}]}):
            if e["_id"] not in songs:
                s = db["songs"].find_one_and_update({"_id": e["_id"]}, {"$set": {"deleted": True}},
                                                    return_document=ReturnDocument.AFTER)
                create_event("YoutubeSongDeleted", **s)

        #print(len(entries))

def get_playlists():
    return db["playlists"].find({"type":"YoutubePlaylist"})


if __name__ == "__main__":
    from time import sleep
    #send_sse_event(0,"YoutubeSongAdded", {"title":"test", "_id":"FGBhQbmPwH8"})
    #exit()
    print("Syncing Youtube")
    while True:
        for playlist in get_playlists():
            try:
                get_song_updates(playlist["_id"])
            except Exception as e:
                traceback.print_exc()
        else:
            get_song_updates(pl_url)
        sleep(1)
