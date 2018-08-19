#!/usr/bin/env python3
import sys
from blitzloop import songlist

song_database = songlist.SongDatabase(sys.argv[1])

def fm(m):
    if not m:
        return ""
    elif "l" in m:
        return "%s (%s)" % (m[None], m["l"])
    else:
        return m[None]

for song in song_database.songs:
    print("=== %s ===" % fm(song.meta["title"]))
    print("By %s - %s" % (fm(song.meta["artist"]), fm(song.meta.get("album",""))))
    if "seenon" in song.meta:
        print("From %s" % fm(song.meta["seenon"]))
    print()
