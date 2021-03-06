#!/usr/bin/env python3

import json
from wsgiref import simple_server

import falcon
import youtube_dl
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from bson.json_util import dumps
from bson.objectid import ObjectId
from bson.errors import InvalidId
from config import *

"""
MusicSync backend http api implementation
"""

class BSONDumps(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)

dumps = BSONDumps().encode

class BaseResponse():
    """Base resource class"""
    def __init__(self, db):
        self.db = db


class PlaylistsCollection(BaseResponse):
    """Operations on playlists collection"""

    def on_get(self, req, resp):
        """Returns list of all playlists"""
        resp.status = falcon.HTTP_200
        resp.body = dumps(list(self.db["playlists"].find()))

    def on_post(self, req, resp):
        """Create a new playlist"""
        data = json.loads(req.stream.read().decode('utf-8'))
        try:
            info = youtube_dl.YoutubeDL({}).extract_info(data["_id"], download=False, process=False)
            pl = {
                "_id": info["id"],
                "title": info["title"],
                "type": "YoutubePlaylist"
            }
        except Exception as ex:
            pl = {
                "title": data["title"],
                "type": "SimplePlaylist"
            }
        result = self.db["playlists"].insert_one(pl)
        pl["_id"] = str(result.inserted_id)
        resp.status = falcon.HTTP_201
        resp.body = json.dumps(pl, indent=2)


class PlaylistResource(BaseResponse):
    """Operations on one playlist"""

    def on_get(self, req, resp, playlist_id):
        """Return a playlist info"""
        try:
            _id = ObjectId(playlist_id)
        except InvalidId:
            _id = playlist_id
        playlist = self.db["playlists"].find_one({"_id":_id})
        if playlist != None:
            resp.body = dumps(playlist)
            resp.status = falcon.HTTP_200
        else:
            resp.status = falcon.HTTP_404

    def on_delete(self, req, resp, playlist_id):
        """Delete this playlist"""
        try:
            _id = ObjectId(playlist_id)
        except InvalidId:
            _id = playlist_id
        playlist = self.db["playlists"].find_one({"_id":_id})
        if playlist != None:
            self.db["songs"].remove({"playlist":_id})
            self.db["playlists"].remove({"_id":_id})
            resp.status = falcon.HTTP_200
        else:
            resp.status = falcon.HTTP_404


class SongsCollection(BaseResponse):
    """Operations on a songs collection in a playlist"""

    def on_get(self, req, resp, playlist_id, extention=".json"):
        """Return list of songs in a playlist"""
        try:
            playlist_id = ObjectId(playlist_id)
        except InvalidId:
            playlist_id = playlist_id
        songs = list(self.db["songs"].find({"playlist":playlist_id}))
        for song in songs:
            song["url"] = "http://s3.storage.ms.wut.ee/"+str(song["_id"])
        if songs != None and len(songs):
            if extention == ".m3u":
                resp.body = "\n".join([song["url"] for song in songs])
                resp.content_type = "audio/mpegurl"
            else:
                resp.body = dumps(songs)
            resp.status = falcon.HTTP_200
        else:
            resp.status = falcon.HTTP_404

    def on_post(self, req, resp, playlist_id):
        """Add a song to a playlist"""
        try:
            playlist_id = ObjectId(playlist_id)
        except InvalidId:
            playlist_id = playlist_id
        data = json.loads(req.stream.read().decode('utf-8'))
        try:
            info = youtube_dl.YoutubeDL({}).extract_info(data["_id"], download=False, process=False)
            pl = {
                "_id": info["id"],
                "title": info["title"],
                "type": "Youtube"
            }
        except Exception as ex:
            pl = {
                "title": data["title"],
                "type": "Simple"
            }
        pl["playlist"] = str(playlist_id)
        result = self.db["songs"].insert_one(pl)
        pl["_id"] = str(result.inserted_id)
        resp.status = falcon.HTTP_201
        resp.body = json.dumps(pl, indent=2)
        
        resp.status = falcon.HTTP_201


class SongResource(BaseResponse):
    """Operations on a one song"""

    def on_get(self, req, resp, playlist_id, song_id):
        """Return a one song"""
        try:
            playlist_id = ObjectId(playlist_id)
        except InvalidId:
            playlist_id = playlist_id
        songs = list(self.db["songs"].find({"playlist":playlist_id, "_id":song_id}))
        for song in songs:
            song["url"] = "http://s3.storage.ms.wut.ee/"+str(song["_id"])
        if songs != None and len(songs):
            resp.body = dumps(songs)
            resp.status = falcon.HTTP_200
        else:
            resp.status = falcon.HTTP_404

    def on_delete(self, req, resp, playlist_id, song_id):
        """Delete that song from playlist"""
        resp.status = falcon.HTTP_204


class GCMResource(BaseResponse):
    """Registration of Google Cloud Messaging clients"""

    def on_post(self, req, resp):
        token = req.stream.read().decode()
        print("Registering device with token ..."+(token[-20:]))
        try:
            self.db["gcm"].insert_one({"_id": token})
        except DuplicateKeyError as err:
            resp.status = falcon.HTTP_409
        else:
            resp.status = falcon.HTTP_201


class ReadOnly():
    """Make everything readonly"""

    allowed_methods = ("GET", "HEAD")

    def __init__(self, readonly=True):
        self.readonly = readonly

    def process_request(self, req, resp):
        if self.readonly and req.method not in self.allowed_methods:
            raise falcon.HTTPMethodNotAllowed(self.allowed_methods)

client = MongoClient()
db = client["MusicSync"]

app = falcon.API(middleware=[ReadOnly(READ_ONLY_API)])
app.add_route('/playlists/', PlaylistsCollection(db))
app.add_route('/playlists/{playlist_id}/', PlaylistResource(db))
app.add_route('/playlists/{playlist_id}/songs/', SongsCollection(db))
app.add_route('/playlists/{playlist_id}/songs{extention}', SongsCollection(db))
app.add_route('/playlists/{playlist_id}/songs/{song_id}', SongResource(db))
app.add_route('/gcm', GCMResource(db))

# a debug server
if __name__ == '__main__':
    httpd = simple_server.make_server('127.0.0.1', 8000, app)
    print("Running a dev server at http://{}:{}".format(*httpd.server_address))
    httpd.serve_forever()

