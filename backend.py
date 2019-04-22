# -*- coding: utf-8 -*-
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser  # to open link on browser
from urllib import request

import requests

import services as s

if sys.platform == "win32":
    import win32process
    import psutil
    import win32gui
elif sys.platform == "linux":
    import dbus
else:
    pass


class Song:
    name = ""
    artist = ""
    album = "UNKNOWN"
    year = -1
    genre = "UNKNOWN"

    cycles_per_minute = -1
    beats_per_minute = -1
    dances = []

    def __init__(self, artist, name):
        self.artist = artist
        self.name = name
        self.dances = []

    @classmethod
    def get_from_string(cls, songstring):
        artist, name = "", ""
        if songstring.count(" - ") == 1:
            artist, name = songstring.rsplit(" - ", 1)
        if songstring.count(" - ") == 2:
            artist, name, garbage = songstring.rsplit(" - ", 2)
        if " / " in name:
            name, garbage = name.rsplit(" / ", 1)
        name = re.sub(r' \(.*?\)', '', name, flags=re.DOTALL)
        name = re.sub(r' \[.*?\]', '', name, flags=re.DOTALL)
        return cls(artist, name)

    def __str__(self):
        return "%s: %s (%d) \nGenre: %s\nAlbum: %s\n" \
               "Cycles per minute: %d\nBeats per minute: %d\nDances: %s\n" \
               % (
                   self.artist, self.name, self.year, self.genre, self.album,
                   self.cycles_per_minute, self.beats_per_minute, self.dances)


# With Sync.
services_list1 = [s._local, s._minilyrics]

# Without Sync.
services_list2 = [s._wikia, s._musixmatch, s._songmeanings, s._songlyrics, s._genius, s._versuri]

services_list3 = [s._ultimateguitar, s._cifraclub, s._songsterr]

'''
current_service is used to store the current index of the list.
Useful to change the lyrics with the button "Next Lyric" if
the service returned a wrong song
'''
current_service = -1


def load_lyrics(song, sync=False):
    global current_service

    if current_service == len(services_list2) - 1: current_service = -1

    if sync:
        temp_lyrics = []
        for service_synced in services_list1:
            lyrics, url, service_name, timed = service_synced(song)
            if lyrics != s.ERROR:
                if timed:
                    break
                else:
                    temp_lyrics = lyrics, url, service_name, timed
        if not timed and temp_lyrics and temp_lyrics[0] != s.ERROR:
            lyrics, url, service_name, timed = temp_lyrics
        current_service = -1

    if sync and lyrics == s.ERROR or sync is False:
        timed = False
        for i in range(current_service + 1, len(services_list2)):
            lyrics, url, service_name = services_list2[i](song)
            current_service = i
            if lyrics != s.ERROR:
                lyrics = lyrics.replace("&amp;", "&").replace("`", "'").strip()
                break
    if lyrics == s.ERROR:
        service_name = "---"

    # return "Error: Could not find lyrics."  if the for loop doesn't find any lyrics
    return lyrics, url, service_name, timed


def load_infos(song: Song):
    threading.Thread(target=s._tanzmusikonline, args=(song,)).start()
    threading.Thread(target=s._welchertanz, args=(song,)).start()


def get_lyrics(song: Song, sync=False):
    global current_service
    current_service = -1

    return load_lyrics(song, sync)


def next_lyrics(song: Song):
    global current_service
    return load_lyrics(song)


def load_chords(song: Song):
    for i in services_list3:
        urls = i(song)
        for url in urls:
            webbrowser.open(url)


def get_window_title() -> str:
    if sys.platform == "win32":
        spotify_pids = []
        for proc in psutil.process_iter():
            if proc:
                try:
                    if proc.name() == 'Spotify.exe':
                        spotify_pids.append(proc.pid)
                except psutil.NoSuchProcess:
                    print("Process does not exist anymore")

        def enum_window_callback(hwnd, pid):
            tid, current_pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == current_pid and win32gui.IsWindowVisible(hwnd):
                windows.append(hwnd)

        windows = []
        window_name = ''

        try:
            for pid in spotify_pids:
                win32gui.EnumWindows(enum_window_callback, pid)
                for item in windows:
                    if win32gui.GetWindowText(item) != '':
                        window_name = win32gui.GetWindowText(item)
                        raise StopIteration
        except StopIteration:
            pass

    elif sys.platform == "darwin":
        window_name = ''
        try:
            command = "osascript getCurrentSong.AppleScript"
            window_name = subprocess.check_output(["/bin/bash", "-c", command]).decode("utf-8")
        except Exception:
            pass
    else:
        window_name = ''
        try:
            session = dbus.SessionBus()
            spotify_dbus = session.get_object("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2")
            spotify_interface = dbus.Interface(spotify_dbus, "org.freedesktop.DBus.Properties")
            metadata = spotify_interface.Get("org.mpris.MediaPlayer2.Player", "Metadata")
        except Exception:
            pass
        try:
            command = "xwininfo -tree -root"
            windows = subprocess.check_output(["/bin/bash", "-c", command]).decode("utf-8")
            spotify = ''
            for line in windows.splitlines():
                if '("spotify" "Spotify")' in line:
                    if " - " in line:
                        spotify = line
                        break
                spotify = 'Spotify Lyrics'
            if spotify == '':
                window_name = 'Spotify'
        except Exception:
            pass
        if window_name not in ('Spotify', 'Spotify Lyrics'):
            try:
                window_name = "%s - %s" % (metadata['xesam:artist'][0], metadata['xesam:title'])
            except Exception:
                pass
    if "—" in window_name:
        window_name = window_name.replace("—", "-")
    if "Spotify - " in window_name:
        window_name = window_name.strip("Spotify - ")
    return window_name


def check_version() -> bool:
    proxy = request.getproxies()
    try:
        return float(get_version()) >= float(
            json.loads(requests.get("https://api.github.com/repos/SimonIT/spotifylyrics/tags",
                                    timeout=5, proxies=proxy).text)[0]["name"])
    except Exception:
        return True


def get_version():
    version = "1.23"
    return version


def open_spotify():
    if sys.platform == "win32":
        if get_window_title() == "":
            path = os.getenv("APPDATA") + '\\Spotify\\Spotify.exe'
            subprocess.Popen(path)
        else:
            pass
    elif sys.platform == "linux":
        if get_window_title() == "":
            subprocess.Popen("spotify")
        else:
            pass
    elif sys.platform == "darwin":
        # I don't have a mac so I don't know if this actually works
        # If it does, please let me know, if it doesn't please fix it :)
        if get_window_title() == "":
            subprocess.Popen("open -a Spotify")
        else:
            pass
    else:
        pass


def main():
    if os.name == "nt":
        os.system("chcp 65001")

    def clear():
        if os.name == "nt":
            os.system("cls")
        else:
            os.system("clear")

    clear()
    old_song_name = ""
    while True:
        song_name = get_window_title()
        if old_song_name != song_name:
            if song_name != "Spotify":
                old_song_name = song_name
                clear()
        time.sleep(1)


if __name__ == '__main__':
    main()
