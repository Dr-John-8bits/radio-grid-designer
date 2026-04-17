#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import os
import re
import signal
import socket
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import unicodedata
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

APP_NAME = "LCN Concepteur de Grille"
BUILD_ID = "20260409-02"
APP_HOST = "127.0.0.1"
APP_PORT = 48267
PORT_SEARCH_SPAN = 20
WEB_DIRNAME = "web"
DATA_DIRNAME = "data"
PRIVATE_DIRNAME = "prive"
RUNTIME_DIRNAME = "run"
RUNTIME_FILENAME = "grille-designer-runtime.json"
CONFIG_FILENAME = "config.local.json"
CONFIG_EXAMPLE_FILENAME = "config.example.json"
JSON_FILENAME = "grille-programmes.json"
JSONL_FILENAME = "grille-programmes.jsonl"
LOCAL_TIMEZONE = "Europe/Paris"
STATE_VERSION = 9
PATH_TEMPLATE_PATTERN = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABELS = {
    "mon": "Lundi",
    "tue": "Mardi",
    "wed": "Mercredi",
    "thu": "Jeudi",
    "fri": "Vendredi",
    "sat": "Samedi",
    "sun": "Dimanche",
}

SOURCE_MODE_OPTIONS = [
    {"id": "playlist_m3u", "label": "Playlist .m3u"},
    {"id": "random_directory", "label": "Mode random"},
]

SCHEDULE_MODE_OPTIONS = [
    {"id": "block", "label": "Bloc continu"},
    {"id": "event", "label": "Événement / émission"},
]

NORMALIZE_MAP = {
    "ambient": "ambiant",
    "Ambient": "ambiant",
    "ambiant": "ambiant",
    "Ambiant": "ambiant",
    "OST": "soundtrack",
    "Soundtrack": "soundtrack",
    "soundtrack": "soundtrack",
    "Indie": "indie-rock",
    "indie": "indie-rock",
    "indie rock": "indie-rock",
    "indie-rock": "indie-rock",
    "indie-roc": "indie-rock",
    "rock indie": "indie-rock",
    "Rock": "rock",
    "rock": "rock",
    "Punk": "punk",
    "punk": "punk",
    "Chanson française": "chanson française",
    "chanson française": "chanson française",
    "Messe Noire": "messe noire",
    "messe noire": "messe noire",
    "texture": "texture",
    "textures": "texture",
    "Electronic": "electronic",
    "electronic": "electronic",
    "Folk": "folk",
    "folk": "folk",
    "Other": "other",
    "Jazz": "jazz",
}

SCHEDULE_DOC_DAY_LABELS = {
    "lundi": "mon",
    "mardi": "tue",
    "mercredi": "wed",
    "jeudi": "thu",
    "vendredi": "fri",
    "samedi": "sat",
    "dimanche": "sun",
}

GROUP_LABEL_BY_CATEGORY = {
    "music_block": "Blocs musicaux",
    "editorial_event": "Émissions",
    "editorial_window": "Fenêtres éditoriales",
}

COLOR_BY_CATEGORY = {
    "music_block": "warm",
    "editorial_event": "event",
    "editorial_window": "window",
}

EVENT_NOMINAL_DURATION_MINUTES = {
    "le-migou": 5,
    "l-instinct-mode": 5,
    "les-transmissions-du-dr-john": 60,
    "console-toi": 30,
    "je-ne-sais-pas-jouer-du-synthe": 15,
    "home-taping-is-killing-music": 60,
    "l-autre-nuit": 20,
    "le-pseudodocumentaire-de-lespace": 20,
}

PREDICATE_SHOW_IDS = {
    "p_migou": "le-migou",
    "p_instinct": "l-instinct-mode",
    "p_transmissions_dr_john": "les-transmissions-du-dr-john",
    "p_console": "console-toi",
    "p_synth": "je-ne-sais-pas-jouer-du-synthe",
    "p_autre_nuit": "l-autre-nuit",
    "p_pseudo": "le-pseudodocumentaire-de-lespace",
    "p_htikm": "home-taping-is-killing-music",
}

SHOW_RULE_OVERRIDES = {
    "traversees": {
        "definitionMode": "duration",
        "definitionLabel": "Bloc défini par durée",
        "definitionSummary": "Bloc court alimenté par des morceaux de 5 à 10 minutes, sans filtre de genre.",
    },
    "fragments": {
        "definitionMode": "duration",
        "definitionLabel": "Bloc défini par durée",
        "definitionSummary": "Bloc court alimenté par des morceaux de 10 à 15 minutes, sans filtre de genre.",
    },
    "trajectoires": {
        "definitionMode": "duration",
        "definitionLabel": "Bloc défini par durée",
        "definitionSummary": "Bloc moyen alimenté par des morceaux de 15 à 30 minutes, sans filtre de genre.",
    },
    "immersion": {
        "definitionMode": "duration",
        "definitionLabel": "Bloc défini par durée",
        "definitionSummary": "Bloc long alimenté par des morceaux de plus de 30 minutes, sans filtre de genre.",
    },
    "les-chats-dans-la-couree": {
        "definitionMode": "random_library",
        "definitionLabel": "RANDOM bibliothèque complète",
        "definitionSummary": "Ce bloc pioche dans toute la bibliothèque Musique, sans filtre de genre ni de durée.",
    },
    "blocsonic": {
        "definitionMode": "directory_window",
        "definitionLabel": "Fenêtre répertoire random",
        "definitionSummary": "Fenêtre musicale dédiée au répertoire blocSonic, relue directement depuis la Documentation.",
    },
    "radio-gadin": {
        "definitionMode": "editorial_pool",
        "definitionLabel": "Pool éditorial / intégrale",
        "definitionSummary": "Bloc défini d'abord par un projet et ses affinités, pas par une famille de tags unique.",
    },
    "when-day-chokes-a-radio": {
        "definitionMode": "editorial_pool",
        "definitionLabel": "Pool éditorial / intégrale",
        "definitionSummary": "Bloc défini d'abord par un projet et ses affinités, pas par une famille de tags unique.",
    },
    "les-ondes-du-chat-noir": {
        "definitionMode": "directory_window",
        "definitionLabel": "Fenêtre répertoire random",
        "definitionSummary": "Fenêtre éditoriale alimentée par le dossier des émissions, sans cartographie de tags musicaux.",
    },
    "console-toi": {
        "definitionMode": "directory_show",
        "definitionLabel": "Émission définie par répertoire",
        "definitionSummary": "Émission ponctuelle alimentée par son répertoire dédié, hors logique de tags musicaux.",
    },
    "je-ne-sais-pas-jouer-du-synthe": {
        "definitionMode": "directory_show",
        "definitionLabel": "Émission définie par répertoire",
        "definitionSummary": "Émission ponctuelle alimentée par son répertoire dédié, hors logique de tags musicaux.",
    },
    "l-autre-nuit": {
        "definitionMode": "directory_show",
        "definitionLabel": "Émission définie par répertoire",
        "definitionSummary": "Émission ponctuelle alimentée par son répertoire dédié, hors logique de tags musicaux.",
    },
    "le-pseudodocumentaire-de-lespace": {
        "definitionMode": "directory_show",
        "definitionLabel": "Émission définie par répertoire",
        "definitionSummary": "Émission ponctuelle alimentée par son répertoire dédié, hors logique de tags musicaux.",
    },
    "les-transmissions-du-dr-john": {
        "definitionMode": "directory_show",
        "definitionLabel": "Émission définie par répertoire",
        "definitionSummary": "Émission ponctuelle alimentée par son répertoire dédié, hors logique de tags musicaux.",
    },
    "l-instinct-mode": {
        "definitionMode": "directory_show",
        "definitionLabel": "Émission définie par répertoire",
        "definitionSummary": "Émission ponctuelle alimentée par son répertoire dédié, hors logique de tags musicaux.",
    },
    "le-migou": {
        "definitionMode": "editorial_event",
        "definitionLabel": "Rendez-vous éditorial court",
        "definitionSummary": "Un morceau de Le Migou, strictement inférieur à 10 minutes, au rendez-vous de 07:00.",
    },
}

SHOW_DEFINITIONS = [
    {
        "id": "la-grande-nuit",
        "title": "La Grande Nuit",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/la-grande-nuit.m3u",
        "description": "Paysages sonores et pièces immersives pour les heures profondes.",
        "color": "night",
    },
    {
        "id": "le-migou",
        "title": "Le Migou",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/migou.m3u",
        "description": "Rendez-vous court de 07:00 : un seul morceau de Le Migou, strictement inférieur à 10 minutes.",
        "color": "event",
    },
    {
        "id": "fragments",
        "title": "Fragments",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/fragments.m3u",
        "description": "Courtes dérives musicales de 10 à 15 minutes.",
        "color": "warm",
    },
    {
        "id": "trajectoires",
        "title": "Trajectoires",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/trajectoires.m3u",
        "description": "Dérives musicales de 15 à 30 minutes.",
        "color": "river",
    },
    {
        "id": "immersion",
        "title": "Immersion",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/immersion.m3u",
        "description": "Longues dérives musicales de plus de 30 minutes.",
        "color": "forest",
    },
    {
        "id": "traversees",
        "title": "Traversées",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/traversees.m3u",
        "description": "Dérives musicales de 5 à 10 minutes.",
        "color": "sky",
    },
    {
        "id": "la-table-du-chat",
        "title": "La table du chat",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/la-table-du-chat.m3u",
        "description": "Chanson, électro douce, ambient léger et respiration de midi.",
        "color": "table",
    },
    {
        "id": "l-instinct-mode",
        "title": "L'instinct mode",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/instinctmode",
        "description": "Chronique du vestiaire by Lady Em, prioritaire au premier point de coupe.",
        "color": "event",
    },
    {
        "id": "rock-de-lapreme",
        "title": "Rock de l'aprème",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/rock-de-lapreme.m3u",
        "description": "On réchauffe le rock'n'roll et ses bords rugueux.",
        "color": "focus",
    },
    {
        "id": "blocsonic",
        "title": "blocSonic",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{musicLibraryRoot}/blocSonic",
        "description": "Fenêtre musicale dédiée au vivier blocSonic.",
        "color": "window",
    },
    {
        "id": "noise-de-lapreme",
        "title": "Noise de l'aprème",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/noise-de-lapreme.m3u",
        "description": "Noise-rock, post-punk et frottements abrasifs.",
        "color": "danger",
    },
    {
        "id": "les-transmissions-du-dr-john",
        "title": "Les Transmissions du Dr. John",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/transmission",
        "description": "Archive aléatoire des Transmissions du Dr. John.",
        "color": "event",
    },
    {
        "id": "home-taping-is-killing-music",
        "title": "Home Taping Is Killing Music",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/HTIKM",
        "description": "Captations pirates, archives live et bootlegs, avec retour au bloc actif après diffusion.",
        "color": "event",
    },
    {
        "id": "les-chats-sauvages",
        "title": "Les chats sauvages",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/les-chats-sauvages.m3u",
        "description": "Le jour des enfants, c'est musique aléatoire et grandes bifurcations.",
        "color": "wild",
    },
    {
        "id": "les-ondes-du-chat-noir",
        "title": "Les Ondes du Chat Noir",
        "category": "editorial_window",
        "groupLabel": "Fenêtres éditoriales",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}",
        "description": "Émissions, fictions et formes radiophoniques choisies au hasard.",
        "color": "window",
    },
    {
        "id": "documents-de-terrain",
        "title": "Documents de terrain",
        "category": "editorial_window",
        "groupLabel": "Fenêtres éditoriales",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/fieldrecordings",
        "description": "Captations de terrain, écoutes situées et paysages sonores documentaires.",
        "color": "window",
    },
    {
        "id": "cinema-pour-les-oreilles",
        "title": "Cinéma pour les oreilles",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/cinema-pour-les-oreilles.m3u",
        "description": "Bandes-son, paysages projetés et dérives cinématographiques.",
        "color": "cinema",
    },
    {
        "id": "radio-gadin",
        "title": "Radio Gadin",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/radio-gadin.m3u",
        "description": "Plongée dans le lore de Flash Dog Duke Silver.",
        "color": "focus",
    },
    {
        "id": "beats-et-flow",
        "title": "Beats & Flow",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/beats-et-flow.m3u",
        "description": "Hip-hop, trip-hop, downtempo, beats et grooves pour le samedi après-midi.",
        "color": "focus",
    },
    {
        "id": "indie-de-lapreme",
        "title": "Indie de l'aprème",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/indie-de-lapreme.m3u",
        "description": "Indie rock, shoegaze, dream pop et brouillard sentimental.",
        "color": "indie",
    },
    {
        "id": "my-favorite-dead-radio",
        "title": "My Favorite Dead Radio",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/my-favorite-dead-radio.m3u",
        "description": "Affinités entre Drive with a dead girl et les lives de My Favorite Everything.",
        "color": "danger",
    },
    {
        "id": "les-chats-dans-la-couree",
        "title": "Les chats dans la courée",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{musicLibraryRoot}",
        "description": "Le grand bazar du chat : surprises, bizarreries et sérendipité totale.",
        "color": "couree",
    },
    {
        "id": "console-toi",
        "title": "Console-toi",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/console-toi",
        "description": "ASMR de l'Atari et poésie 8-bit.",
        "color": "event",
    },
    {
        "id": "je-ne-sais-pas-jouer-du-synthe",
        "title": "Je ne sais pas jouer du synthé",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/jnspjds",
        "description": "On traverse la synthèse analogique par l'essai-erreur.",
        "color": "event",
    },
    {
        "id": "when-day-chokes-a-radio",
        "title": "When Day Chokes a Radio",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/when-day-chokes-a-radio.m3u",
        "description": "Focus intégrale When Day Chokes The Night.",
        "color": "window",
    },
    {
        "id": "le-reveil-lent-du-chat",
        "title": "Le réveil lent du chat",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/le-reveil-lent-du-chat.m3u",
        "description": "Musiques calmes, flottantes et encore ensommeillées.",
        "color": "sky",
    },
    {
        "id": "les-siestes-du-chat",
        "title": "Les siestes du chat",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/les-siestes-du-chat.m3u",
        "description": "Dream pop, lo-fi et formes suspendues pour étirer le dimanche.",
        "color": "table",
    },
    {
        "id": "messe-noire",
        "title": "Messe Noire",
        "category": "music_block",
        "groupLabel": "Blocs musicaux",
        "defaultScheduleMode": "block",
        "defaultSourceMode": "playlist_m3u",
        "defaultSourcePath": "{poolsDir}/messe-noire.m3u",
        "description": "Rituel dominical : musiques dures, sombres, expérimentales et radicales.",
        "color": "ritual",
    },
    {
        "id": "l-autre-nuit",
        "title": "L'Autre Nuit",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/lautre-nuit",
        "description": "Lectures sans centre et machines hésitantes.",
        "color": "event",
    },
    {
        "id": "le-pseudodocumentaire-de-lespace",
        "title": "Le Pseudodocumentaire de l'espace",
        "category": "editorial_event",
        "groupLabel": "Émissions",
        "defaultScheduleMode": "event",
        "defaultSourceMode": "random_directory",
        "defaultSourcePath": "{emissionsDir}/pseudocumentaire",
        "description": "Fiction sonore et dépression verte.",
        "color": "event",
    },
]

SHOWS_BY_ID = {item["id"]: item for item in SHOW_DEFINITIONS}

DEFAULT_DRESSING = [
    {
        "id": "jingles",
        "label": "Jingles",
        "enabled": True,
        "intervalMinutes": 30,
        "offsetMinutes": 0,
        "catchupMode": "until_next_trigger",
        "priority": 30,
        "sourceMode": "random_directory",
        "sourcePath": "{jinglesDir}",
        "notes": "Cible actuelle : début d'heure et demi-heure, avec rattrapage à la prochaine frontière.",
    },
    {
        "id": "reclames",
        "label": "Réclames",
        "enabled": True,
        "intervalMinutes": 60,
        "offsetMinutes": 15,
        "catchupMode": "until_next_trigger",
        "priority": 40,
        "sourceMode": "random_directory",
        "sourcePath": "{reclamesDir}",
        "notes": "Cible actuelle : autour de la 15e minute de chaque heure.",
    },
]

DEFAULT_RUNTIME = {
    "paths": {
        "musicLibraryRoot": "/path/to/music-library",
        "radioRoot": "/path/to/radio",
        "poolsDir": "/path/to/radio/pools",
        "emissionsDir": "/path/to/radio/emissions",
        "jinglesDir": "/path/to/radio/jingles",
        "reclamesDir": "/path/to/radio/reclames",
        "logsDir": "/path/to/radio/logs",
        "webRoot": "/path/to/web-root",
        "currentShowJson": "/path/to/web-root/current-show.json",
        "nowPlayingJson": "/path/to/web-root/nowplaying.json",
        "historyDir": "/path/to/web-root/history",
    },
    "liveInput": {
        "enabled": True,
        "harborName": "live",
        "port": 8005,
        "password": "",
        "icy": True,
    },
    "outputs": [
        {
            "id": "opus",
            "enabled": True,
            "format": "opus",
            "bitrateKbps": 96,
            "stereo": True,
            "host": "localhost",
            "port": 8000,
            "password": "",
            "mount": "/stream",
            "name": "Le Chat Noir",
            "description": "Laboratoire radiophonique expérimental",
            "genre": "Experimental",
            "url": "http://localhost:8000",
        },
        {
            "id": "mp3",
            "enabled": True,
            "format": "mp3",
            "bitrateKbps": 192,
            "stereo": True,
            "host": "localhost",
            "port": 8000,
            "password": "",
            "mount": "/stream.mp3",
            "name": "Le Chat Noir (Web)",
            "description": "Flux web MP3",
            "genre": "Experimental",
            "url": "http://localhost:8000",
        },
    ],
}

DEFAULT_ROTATION_POLICY = {
    "artistCooldownMinutes": 90,
    "albumCooldownMinutes": 180,
    "trackCooldownMinutes": 1440,
}

SHOW_GENERATION_OVERRIDES = {
    "traversees": {
        "generatorMode": "duration_pool",
        "generatorLabel": "Pool par durée",
        "generatorSummary": "Construit à partir des morceaux de 5 à 10 minutes, sans filtre de genre.",
        "generatorConfig": {
            "poolName": "traversees",
            "durationMinSeconds": 300,
            "durationMaxSeconds": 600,
            "usesProfileTags": False,
        },
    },
    "fragments": {
        "generatorMode": "duration_pool",
        "generatorLabel": "Pool par durée",
        "generatorSummary": "Construit à partir des morceaux de 10 à 15 minutes, sans filtre de genre.",
        "generatorConfig": {
            "poolName": "fragments",
            "durationMinSeconds": 600,
            "durationMaxSeconds": 900,
            "usesProfileTags": False,
        },
    },
    "trajectoires": {
        "generatorMode": "duration_pool",
        "generatorLabel": "Pool par durée",
        "generatorSummary": "Construit à partir des morceaux de 15 à 30 minutes, sans filtre de genre.",
        "generatorConfig": {
            "poolName": "trajectoires",
            "durationMinSeconds": 900,
            "durationMaxSeconds": 1800,
            "usesProfileTags": False,
        },
    },
    "immersion": {
        "generatorMode": "duration_pool",
        "generatorLabel": "Pool par durée",
        "generatorSummary": "Construit à partir des morceaux de plus de 30 minutes, sans filtre de genre.",
        "generatorConfig": {
            "poolName": "immersion",
            "durationMinSeconds": 1800,
            "usesProfileTags": False,
        },
    },
    "les-chats-dans-la-couree": {
        "generatorMode": "library_random",
        "generatorLabel": "Bibliothèque complète",
        "generatorSummary": "Pas de pool généré : Liquidsoap lit directement toute la bibliothèque en mode random.",
        "generatorConfig": {
            "libraryRoot": "{musicLibraryRoot}",
        },
    },
    "blocsonic": {
        "generatorMode": "directory_random",
        "generatorLabel": "Répertoire blocSonic",
        "generatorSummary": "Fenêtre relue directement depuis le dossier blocSonic, sans pool intermédiaire.",
        "generatorConfig": {
            "directoryPath": "{musicLibraryRoot}/blocSonic",
        },
    },
    "radio-gadin": {
        "generatorMode": "artist_focus_pool",
        "generatorLabel": "Pool éditorial artiste",
        "generatorSummary": "Pool généré autour du projet Flash Dog Duke Silver.",
        "generatorConfig": {
            "poolName": "radio-gadin",
            "artistIncludes": ["flash dog duke silver"],
            "usesProfileTags": False,
        },
    },
    "when-day-chokes-a-radio": {
        "generatorMode": "artist_focus_pool",
        "generatorLabel": "Pool éditorial artiste",
        "generatorSummary": "Pool généré autour du projet When Day Chokes the Night.",
        "generatorConfig": {
            "poolName": "when-day-chokes-a-radio",
            "artistIncludes": ["when day chokes the night"],
            "usesProfileTags": False,
        },
    },
    "my-favorite-dead-radio": {
        "generatorMode": "hybrid_pool",
        "generatorLabel": "Pool hybride tags + artistes",
        "generatorSummary": "Pool généré depuis les tags documentaires, enrichi par l’artiste Drive with a dead girl et les replays live dédiés.",
        "generatorConfig": {
            "poolName": "my-favorite-dead-radio",
            "artistIncludes": ["drive with a dead girl"],
            "extraDirectories": ["{emissionsDir}/mfe-live-replay"],
            "usesProfileTags": True,
        },
    },
    "les-ondes-du-chat-noir": {
        "generatorMode": "directory_random",
        "generatorLabel": "Répertoire d'émissions",
        "generatorSummary": "Pas de pool généré : Liquidsoap pioche directement dans le répertoire complet des émissions.",
        "generatorConfig": {
            "directoryPath": "{emissionsDir}",
        },
    },
    "documents-de-terrain": {
        "generatorMode": "directory_random",
        "generatorLabel": "Répertoire de terrain",
        "generatorSummary": "Fenêtre éditoriale alimentée directement par le répertoire field recordings.",
        "generatorConfig": {
            "directoryPath": "{emissionsDir}/fieldrecordings",
        },
    },
    "le-migou": {
        "generatorMode": "artist_duration_pool",
        "generatorLabel": "Pool artiste + durée",
        "generatorSummary": "Pool dédié aux morceaux de Le Migou strictement inférieurs à 10 minutes.",
        "generatorConfig": {
            "poolName": "migou",
            "artistIncludes": ["le migou"],
            "durationMaxSeconds": 600,
            "usesProfileTags": False,
        },
    },
}


class AppError(RuntimeError):
    """Raised when the schedule designer cannot complete a request."""


def slugify(value: str) -> str:
    output = []
    previous_dash = False
    for char in value.lower():
        if char.isalnum():
            output.append(char)
            previous_dash = False
            continue
        if not previous_dash:
            output.append("-")
            previous_dash = True
    return "".join(output).strip("-") or "item"


def humanize_name(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip() or value


def canonical_label(value: object) -> str:
    text = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return slugify(ascii_text)


SHOW_IDS_BY_TITLE: dict[str, str] = {}
for item in SHOW_DEFINITIONS:
    canonical_title = canonical_label(item["title"])
    SHOW_IDS_BY_TITLE[canonical_title] = item["id"]
    for prefix in ("le-", "la-", "les-", "l-"):
        if canonical_title.startswith(prefix):
            SHOW_IDS_BY_TITLE.setdefault(canonical_title[len(prefix):], item["id"])


def find_program_grid_doc_path(script_dir: Path) -> Path:
    candidates = [
        script_dir.parent.parent / "LCN-Documentation" / "GRILLE-PROGRAMMES.md",
        script_dir.parent.parent / "LCN-Archive" / "Oldwebsite" / "LAN-WEBSITE - Documentation" / "GRILLE-PROGRAMMES.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def find_liquidsoap_spec_doc_path(script_dir: Path) -> Path:
    candidates = [
        script_dir.parent.parent / "LCN-Documentation" / "SPEC-LCN-LIQUIDSOAP.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def find_radio_liq_doc_path(script_dir: Path) -> Path:
    candidates = [
        script_dir.parent.parent / "LCN-Documentation" / "radio.liq.txt",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def documentation_source_paths(script_dir: Path) -> list[Path]:
    return [
        find_program_grid_doc_path(script_dir),
        find_liquidsoap_spec_doc_path(script_dir),
        find_radio_liq_doc_path(script_dir),
    ]


def build_documentation_fingerprint(script_dir: Path) -> str:
    digest = hashlib.sha1()
    for path in documentation_source_paths(script_dir):
        digest.update(str(path).encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
        else:
            digest.update(b"__missing__")
    return digest.hexdigest()


def normalize_doc_time_token(raw_value: object) -> str:
    cleaned = parse_markdown_cell(str(raw_value or ""))
    match = re.match(r"^(?P<hours>\d{1,2})(?:[:h](?P<minutes>\d{2}))?$", cleaned)
    if not match:
        return normalize_time(cleaned, "00:00")
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes") or "00")
    return normalize_time(f"{hours:02d}:{minutes:02d}", "00:00")


def day_key_from_schedule_heading(label: str) -> str:
    normalized = canonical_label(label)
    for day_label, day_key in SCHEDULE_DOC_DAY_LABELS.items():
        if canonical_label(day_label) == normalized:
            return day_key
    return ""


def extract_schedule_note(raw_value: str) -> str:
    cleaned = parse_markdown_cell(raw_value or "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def parse_radio_liq_metadata(script_dir: Path) -> dict[str, Any]:
    radio_path = find_radio_liq_doc_path(script_dir)
    runtime_paths = load_runtime_defaults(script_dir)["paths"]
    metadata = {
        "sourceDoc": str(radio_path),
        "showsByTitle": {},
        "pendingByShowId": {},
    }
    if not radio_path.is_file():
        return metadata

    tag_show_regex = re.compile(
        r'^\s*(?P<var>[a-zA-Z0-9_]+)\s*=\s*tag_show\("(?P<title>[^"]+)",\s*"(?P<kind>[^"]+)",\s*"[^"]+",\s*(?P<builder>mk_pool|mk_dir_pool)\("(?P<path>[^"]+)"\)\)'
    )
    library_regex = re.compile(
        r'^\s*(?P<var>[a-zA-Z0-9_]+)\s*=\s*tag_show\("(?P<title>[^"]+)",\s*"(?P<kind>[^"]+)",\s*"[^"]+",\s*library_all\)'
    )
    predicate_regex = re.compile(
        r'^\s*(?P<predicate>p_[a-zA-Z0-9_]+)\s*=\s*predicate\.once\(\{.*-(?P<end_hours>\d{1,2})h(?P<end_minutes>\d{2})?\}\)'
    )

    for raw_line in radio_path.read_text(encoding="utf-8").splitlines():
        tag_match = tag_show_regex.match(raw_line)
        if tag_match:
            title = tag_match.group("title")
            category = coerce_text(tag_match.group("kind"), "music_block")
            builder = tag_match.group("builder")
            source_mode = "playlist_m3u" if builder == "mk_pool" else "random_directory"
            metadata["showsByTitle"][canonical_label(title)] = {
                "title": title,
                "category": category,
                "sourceMode": source_mode,
                "sourcePath": tag_match.group("path"),
            }
            continue

        library_match = library_regex.match(raw_line)
        if library_match:
            title = library_match.group("title")
            metadata["showsByTitle"][canonical_label(title)] = {
                "title": title,
                "category": coerce_text(library_match.group("kind"), "music_block"),
                "sourceMode": "random_directory",
                "sourcePath": runtime_paths["musicLibraryRoot"],
            }
            continue

        predicate_match = predicate_regex.match(raw_line)
        if predicate_match:
            show_id = PREDICATE_SHOW_IDS.get(predicate_match.group("predicate"))
            if not show_id:
                continue
            end_hours = int(predicate_match.group("end_hours"))
            end_minutes = int(predicate_match.group("end_minutes") or "00")
            metadata["pendingByShowId"][show_id] = normalize_time(f"{end_hours:02d}:{end_minutes:02d}", "24:00")

    return metadata


def infer_dynamic_slot_seed(show_title: str, schedule_mode: str, radio_metadata: dict[str, Any], script_dir: Path) -> dict[str, str]:
    canonical_title = canonical_label(show_title)
    shows_by_id, title_index = resolve_show_lookup(script_dir)
    show_id = title_index.get(canonical_title, slugify(show_title))
    show = shows_by_id.get(show_id)
    radio_show = radio_metadata.get("showsByTitle", {}).get(canonical_title, {})
    category = (
        show["category"]
        if show
        else coerce_text(radio_show.get("category"), "editorial_event" if schedule_mode == "event" else "music_block")
    )
    source_mode = (
        show["defaultSourceMode"]
        if show
        else coerce_text(radio_show.get("sourceMode"), "random_directory" if category != "music_block" else "playlist_m3u")
    )
    source_path = (
        show["defaultSourcePath"]
        if show
        else coerce_text(radio_show.get("sourcePath"))
    )
    return {
        "id": show_id,
        "title": show["title"] if show else coerce_text(radio_show.get("title"), show_title),
        "description": show["description"] if show else "",
        "category": show["category"] if show else category,
        "color": show["color"] if show else COLOR_BY_CATEGORY.get(category, "warm"),
        "sourceMode": source_mode,
        "sourcePath": source_path,
    }


def make_documented_block(
    script_dir: Path,
    slot_id: str,
    show_title: str,
    start_time: str,
    end_time: str,
    radio_metadata: dict[str, Any],
    notes: str = "",
) -> dict[str, Any]:
    seed = infer_dynamic_slot_seed(show_title, "block", radio_metadata, script_dir)
    return {
        "id": slot_id,
        "showId": seed["id"],
        "title": seed["title"],
        "description": seed["description"],
        "scheduleMode": "block",
        "category": seed["category"],
        "color": seed["color"],
        "startTime": start_time,
        "endTime": end_time,
        "pendingUntil": "",
        "liquidsoapPendingUntil": "",
        "sourceMode": seed["sourceMode"],
        "sourcePath": seed["sourcePath"],
        "notes": notes,
    }


def make_documented_event(
    script_dir: Path,
    slot_id: str,
    show_title: str,
    start_time: str,
    display_until: str,
    liquidsoap_pending_until: str,
    radio_metadata: dict[str, Any],
    notes: str = "",
) -> dict[str, Any]:
    seed = infer_dynamic_slot_seed(show_title, "event", radio_metadata, script_dir)
    return {
        "id": slot_id,
        "showId": seed["id"],
        "title": seed["title"],
        "description": seed["description"],
        "scheduleMode": "event",
        "category": seed["category"],
        "color": seed["color"],
        "startTime": start_time,
        "endTime": "",
        "pendingUntil": display_until,
        "liquidsoapPendingUntil": liquidsoap_pending_until,
        "sourceMode": seed["sourceMode"],
        "sourcePath": seed["sourcePath"],
        "notes": notes,
    }


def minutes_to_time(total_minutes: int) -> str:
    bounded = max(0, min(int(total_minutes), 1440))
    if bounded == 1440:
        return "24:00"
    hours, minutes = divmod(bounded, 60)
    return f"{hours:02d}:{minutes:02d}"


def nominal_event_end_time(show_id: str, start_time: str) -> str:
    start_minutes = time_to_minutes(start_time)
    duration = EVENT_NOMINAL_DURATION_MINUTES.get(show_id, 60)
    return minutes_to_time(min(start_minutes + duration, 1440))


def parse_schedule_spec(script_dir: Path) -> dict[str, list[dict[str, str]]]:
    spec_path = find_liquidsoap_spec_doc_path(script_dir)
    schedule: dict[str, list[dict[str, str]]] = {}
    if not spec_path.is_file():
        return schedule

    in_section = False
    current_day = ""

    for raw_line in spec_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("### 8.7 "):
            in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("### 8.8 ") or stripped.startswith("## 9"):
            break

        heading_match = re.match(r"^####\s+(.+)$", stripped)
        if heading_match:
            current_day = day_key_from_schedule_heading(heading_match.group(1))
            if current_day:
                schedule[current_day] = []
            continue

        if not current_day or not stripped.startswith("- "):
            continue

        body = stripped[2:].strip()
        explicit_match = re.match(r"^`(?P<time>[^`]+)`\s*:\s*`(?P<title>[^`]+)`(?P<rest>.*)$", body)
        if explicit_match:
            time_expr = explicit_match.group("time").strip()
            title = parse_markdown_cell(explicit_match.group("title"))
            notes = extract_schedule_note(explicit_match.group("rest"))
            if "→" in time_expr:
                start_raw, end_raw = [item.strip() for item in time_expr.split("→", 1)]
                schedule[current_day].append(
                    {
                        "kind": "block",
                        "title": title,
                        "startTime": normalize_doc_time_token(start_raw),
                        "endTime": normalize_doc_time_token(end_raw),
                        "notes": notes,
                    }
                )
            else:
                schedule[current_day].append(
                    {
                        "kind": "event",
                        "title": title,
                        "startTime": normalize_doc_time_token(time_expr),
                        "notes": notes,
                    }
                )
            continue

        after_match = re.match(r"^après .+? jusqu[’']à\s+`(?P<end>[^`]+)`\s*:\s*`(?P<title>[^`]+)`(?P<rest>.*)$", body)
        if after_match:
            schedule[current_day].append(
                {
                    "kind": "after",
                    "title": parse_markdown_cell(after_match.group("title")),
                    "endTime": normalize_doc_time_token(after_match.group("end")),
                    "notes": extract_schedule_note(after_match.group("rest")),
                }
            )

    return schedule


def parse_program_grid_doc(script_dir: Path) -> dict[str, list[dict[str, str]]]:
    doc_path = find_program_grid_doc_path(script_dir)
    schedule: dict[str, list[dict[str, str]]] = {}
    if not doc_path.is_file():
        return schedule

    current_day = ""
    for raw_line in doc_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        heading_match = re.match(r"^##\s+.*?([A-Za-zÀ-ÿ]+)$", stripped)
        if heading_match:
            current_day = day_key_from_schedule_heading(heading_match.group(1))
            if current_day:
                schedule[current_day] = []
            continue

        if not current_day or not stripped.startswith("**") or not stripped.endswith("**"):
            continue

        body = parse_markdown_cell(stripped.strip("*"))
        if "—" not in body:
            continue

        left, right = [part.strip() for part in body.split("—", 1)]
        title = right

        if left.lower().startswith("puis"):
            if ":" in title:
                title = title.split(":", 1)[1].strip()
            schedule[current_day].append(
                {
                    "kind": "after",
                    "title": title,
                }
            )
            continue

        if "–" in left:
            start_raw, end_raw = [part.strip() for part in left.split("–", 1)]
            schedule[current_day].append(
                {
                    "kind": "block",
                    "title": title,
                    "startTime": normalize_doc_time_token(start_raw),
                    "endTime": normalize_doc_time_token(end_raw),
                }
            )
            continue

        schedule[current_day].append(
            {
                "kind": "explicit",
                "title": title,
                "startTime": normalize_doc_time_token(left),
            }
        )

    return schedule


def next_documented_anchor(entries: list[dict[str, str]], start_index: int) -> str:
    for entry in entries[start_index + 1:]:
        if entry.get("kind") in {"block", "explicit"} and entry.get("startTime"):
            return normalize_time(entry["startTime"], "24:00")
    return "24:00"


def split_genres(raw: str) -> list[str]:
    if not raw.strip():
        return ["(sans genre)"]

    parts = [raw]
    for separator in [";", ",", "|"]:
        expanded: list[str] = []
        for item in parts:
            expanded.extend(item.split(separator))
        parts = expanded

    cleaned = [item.strip() for item in parts if item.strip()]
    return cleaned if cleaned else ["(sans genre)"]


def normalize_genre_tag(tag: str) -> str:
    cleaned = tag.strip()
    if not cleaned:
        return "(sans genre)"
    return NORMALIZE_MAP.get(cleaned, cleaned)


def unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def format_duration_label(seconds: float) -> str:
    rounded = max(int(round(seconds)), 0)
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def infer_track_labels(filepath: str) -> dict[str, str]:
    path = Path(filepath)
    title = path.stem or path.name
    album = path.parent.name if path.parent != path else ""
    artist = path.parent.parent.name if path.parent.parent != path.parent else ""
    return {
        "filename": path.name,
        "title": title,
        "album": album,
        "artist": artist,
    }


def find_genre_catalog_csv_path(script_dir: Path) -> Path:
    candidates = [
        script_dir / PRIVATE_DIRNAME / "genres_bibliotheque_complete.csv",
        script_dir / PRIVATE_DIRNAME / "genres_durees_musique.csv",
        script_dir / DATA_DIRNAME / "genres_bibliotheque_complete.csv",
        script_dir.parent / "Supervision" / "data" / "genres_bibliotheque_complete.csv",
        script_dir.parent / "Supervision" / "data" / "genres_durees_musique.csv",
        script_dir / DATA_DIRNAME / "genres_durees_musique.csv",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def get_csv_value(row: dict[str, Any], *field_names: str) -> str:
    for field_name in field_names:
        value = row.get(field_name)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def find_genre_cartography_doc_path(script_dir: Path) -> Path:
    candidates = [
        script_dir.parent.parent / "LCN-Documentation" / "LCN-CARTOGRAPHIE-GENRES.md",
        script_dir.parent.parent / "LCN-Archive" / "Oldwebsite" / "LAN-WEBSITE - Documentation" / "LCN-CARTOGRAPHIE-GENRES.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def load_observed_genre_tags(script_dir: Path) -> dict[str, Any]:
    csv_path = find_genre_catalog_csv_path(script_dir)
    raw_counts: dict[str, int] = {}
    normalized_counts: dict[str, dict[str, Any]] = {}
    track_records: list[dict[str, Any]] = []
    tracks_by_tag: dict[str, list[str]] = {}
    track_count = 0

    if not csv_path.is_file():
        return {
            "sourceCsv": str(csv_path),
            "trackCount": 0,
            "rawCounts": {},
            "normalizedCounts": {},
            "trackRecords": [],
            "tracksByTag": {},
        }

    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            track_count += 1
            filepath = get_csv_value(row, "fichier", "filepath", "file", "path")
            try:
                duration_seconds = float(get_csv_value(row, "duree_secondes", "duration") or 0.0)
            except Exception:
                duration_seconds = 0.0
            raw_tags = split_genres(get_csv_value(row, "genre"))
            normalized_tags = unique_preserve([normalize_genre_tag(raw_tag) for raw_tag in raw_tags])

            track_id = filepath or f"track-{track_count:05d}"
            labels = infer_track_labels(filepath)
            artist = get_csv_value(row, "artiste", "artist") or labels["artist"]
            album = get_csv_value(row, "album") or labels["album"]
            track_records.append(
                {
                    "id": track_id,
                    "filepath": filepath,
                    "filename": labels["filename"],
                    "title": labels["title"],
                    "album": album,
                    "artist": artist,
                    "durationSeconds": duration_seconds,
                    "durationLabel": format_duration_label(duration_seconds),
                    "rawGenres": raw_tags,
                    "normalizedGenres": normalized_tags,
                }
            )

            for normalized_tag in normalized_tags:
                tracks_by_tag.setdefault(normalized_tag, []).append(track_id)

            for raw_tag in raw_tags:
                raw_counts[raw_tag] = raw_counts.get(raw_tag, 0) + 1
                normalized_tag = normalize_genre_tag(raw_tag)
                entry = normalized_counts.setdefault(
                    normalized_tag,
                    {"tag": normalized_tag, "occurrences": 0, "rawVariants": []},
                )
                entry["occurrences"] += 1
                if raw_tag not in entry["rawVariants"]:
                    entry["rawVariants"].append(raw_tag)

    for entry in normalized_counts.values():
        entry["rawVariants"].sort(key=lambda item: item.lower())

    return {
        "sourceCsv": str(csv_path),
        "trackCount": track_count,
        "rawCounts": raw_counts,
        "normalizedCounts": normalized_counts,
        "trackRecords": track_records,
        "tracksByTag": tracks_by_tag,
    }


def parse_markdown_cell(value: str) -> str:
    return (
        value.replace("**", "")
        .replace("`", "")
        .replace("\u2019", "'")
        .strip()
    )


def parse_show_titles(value: str) -> list[str]:
    cleaned = parse_markdown_cell(value)
    if not cleaned:
        return []
    return [item.strip() for item in cleaned.split(";") if item.strip()]


def parse_genre_cartography_doc(script_dir: Path) -> dict[str, Any]:
    doc_path = find_genre_cartography_doc_path(script_dir)
    rows: list[dict[str, Any]] = []
    if not doc_path.is_file():
        return {"sourceDoc": str(doc_path), "rows": rows}

    in_table = False
    for line in doc_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("| Tag observé |"):
            in_table = True
            continue

        if not in_table:
            continue

        if not stripped:
            if rows:
                break
            continue

        if not stripped.startswith("|"):
            if rows:
                break
            continue

        if stripped.startswith("|---"):
            continue

        cells = [parse_markdown_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < 6:
            continue

        rows.append(
            {
                "rawTag": cells[0],
                "normalizedTag": cells[1],
                "occurrences": coerce_int(cells[2], 0),
                "primaryShowTitle": cells[3],
                "secondaryShowTitles": parse_show_titles(cells[4]),
                "notes": cells[5],
            }
        )

    return {"sourceDoc": str(doc_path), "rows": rows}


def build_show_title_index(script_dir: Path) -> dict[str, str]:
    index = {}
    for show in resolve_show_definitions(script_dir):
        index[canonical_label(show["title"])] = show["id"]
    return index


def build_default_generator_profile(show: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    if show["defaultSourceMode"] == "playlist_m3u":
        generator_mode = "tag_pool"
        generator_label = "Pool généré depuis la cartographie"
        generator_summary = "Le .m3u est généré à partir du profil documentaire et de la politique de rotation."
        generator_config = {
            "poolName": Path(show["defaultSourcePath"]).stem,
            "sourceMode": show["defaultSourceMode"],
            "sourcePath": show["defaultSourcePath"],
            "usesProfileTags": True,
        }
    else:
        generator_mode = "directory_random"
        generator_label = "Répertoire aléatoire"
        generator_summary = "Pas de pool généré : Liquidsoap lit directement un répertoire en mode random."
        generator_config = {
            "directoryPath": show["defaultSourcePath"],
            "sourceMode": show["defaultSourceMode"],
            "sourcePath": show["defaultSourcePath"],
        }

    override = SHOW_GENERATION_OVERRIDES.get(show["id"], {})
    if override:
        generator_mode = override.get("generatorMode", generator_mode)
        generator_label = override.get("generatorLabel", generator_label)
        generator_summary = override.get("generatorSummary", generator_summary)
        generator_config.update(clone_json(override.get("generatorConfig", {})))

    return generator_mode, generator_label, generator_summary, generator_config


def build_default_show_profile(show: dict[str, Any]) -> dict[str, Any]:
    override = SHOW_RULE_OVERRIDES.get(show["id"], {})
    definition_mode = override.get("definitionMode", "genre")
    definition_label = override.get("definitionLabel", "Bloc défini par genres")
    definition_summary = override.get(
        "definitionSummary",
        "Bloc musical dont la répartition des tags suit la cartographie officielle.",
    )

    if show["category"] in {"editorial_event", "editorial_window"} and show["id"] not in SHOW_RULE_OVERRIDES:
        definition_mode = "directory_show"
        definition_label = "Émission définie par répertoire"
        definition_summary = "Ce créneau repose sur un répertoire éditorial, pas sur un filtre de tags musicaux."

    generator_mode, generator_label, generator_summary, generator_config = build_default_generator_profile(show)

    return {
        "showId": show["id"],
        "showTitle": show["title"],
        "definitionMode": definition_mode,
        "definitionLabel": definition_label,
        "definitionSummary": definition_summary,
        "generatorMode": generator_mode,
        "generatorLabel": generator_label,
        "generatorSummary": generator_summary,
        "generatorConfig": generator_config,
        "primaryTags": {},
        "secondaryTags": {},
    }


def add_profile_tag(bucket: dict[str, dict[str, Any]], normalized_tag: str, occurrences: int) -> None:
    entry = bucket.setdefault(normalized_tag, {"tag": normalized_tag, "occurrences": 0})
    entry["occurrences"] += occurrences


def build_tag_catalog(script_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    observed_data = load_observed_genre_tags(script_dir)
    doc_data = parse_genre_cartography_doc(script_dir)
    shows = resolve_show_definitions(script_dir)
    title_index = build_show_title_index(script_dir)
    runtime_paths = load_runtime_defaults(script_dir)["paths"]

    doc_by_raw = {row["rawTag"]: row for row in doc_data["rows"]}
    show_profiles = {
        show["id"]: build_default_show_profile(show)
        for show in shows
    }
    unmatched_titles: set[str] = set()
    observed_tags: list[dict[str, Any]] = []

    for raw_tag in sorted(observed_data["rawCounts"], key=lambda item: item.lower()):
        occurrences = observed_data["rawCounts"][raw_tag]
        doc_row = doc_by_raw.get(raw_tag)
        normalized_tag = (
            doc_row["normalizedTag"]
            if doc_row and doc_row.get("normalizedTag")
            else normalize_genre_tag(raw_tag)
        )

        primary_show_id = ""
        primary_show_title = ""
        secondary_show_ids: list[str] = []
        secondary_show_titles: list[str] = []
        notes = ""

        if doc_row:
            primary_show_title = doc_row["primaryShowTitle"]
            primary_show_id = title_index.get(canonical_label(primary_show_title), "")
            if primary_show_title and not primary_show_id:
                unmatched_titles.add(primary_show_title)

            for title in doc_row["secondaryShowTitles"]:
                show_id = title_index.get(canonical_label(title), "")
                secondary_show_titles.append(title)
                if show_id:
                    secondary_show_ids.append(show_id)
                elif title:
                    unmatched_titles.add(title)
            notes = doc_row["notes"]

        if primary_show_id:
            add_profile_tag(show_profiles[primary_show_id]["primaryTags"], normalized_tag, occurrences)
        for show_id in secondary_show_ids:
            add_profile_tag(show_profiles[show_id]["secondaryTags"], normalized_tag, occurrences)

        observed_tags.append(
            {
                "rawTag": raw_tag,
                "normalizedTag": normalized_tag,
                "occurrences": occurrences,
                "primaryShowId": primary_show_id,
                "primaryShowTitle": primary_show_title,
                "secondaryShowIds": secondary_show_ids,
                "secondaryShowTitles": secondary_show_titles,
                "notes": notes,
            }
        )

    normalized_tags = sorted(
        observed_data["normalizedCounts"].values(),
        key=lambda item: (-int(item["occurrences"]), item["tag"].lower()),
    )

    finalized_profiles = []
    for show in shows:
        profile = show_profiles[show["id"]]
        profile["primaryTags"] = sorted(
            profile["primaryTags"].values(),
            key=lambda item: (-int(item["occurrences"]), item["tag"].lower()),
        )
        profile["secondaryTags"] = sorted(
            profile["secondaryTags"].values(),
            key=lambda item: (-int(item["occurrences"]), item["tag"].lower()),
        )
        profile["generatorConfig"] = resolve_generator_config_templates(profile["generatorConfig"], runtime_paths)
        finalized_profiles.append(profile)

    tag_library = {
        "sourceCsv": observed_data["sourceCsv"],
        "sourceDoc": doc_data["sourceDoc"],
        "trackCount": observed_data["trackCount"],
        "rawTagCount": len(observed_data["rawCounts"]),
        "normalizedTagCount": len(observed_data["normalizedCounts"]),
        "trackRecords": observed_data["trackRecords"],
        "tracksByTag": observed_data["tracksByTag"],
        "observedTags": observed_tags,
        "normalizedTags": normalized_tags,
        "unmatchedDocTitles": sorted(unmatched_titles),
    }
    return tag_library, finalized_profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Concepteur de grille Le Chat Noir")
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="N'ouvre pas automatiquement l'interface dans le navigateur.",
    )
    return parser.parse_args()


def current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def has_readable_timestamp(value: object) -> bool:
    text = str(value or "").strip()
    return "T" in text and ":" in text


def write_atomic_bytes(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=f"{target.stem}-",
        suffix=target.suffix,
        dir=target.parent,
    )
    try:
        with os.fdopen(handle, "wb") as temp_file:
            temp_file.write(content)
        Path(temp_name).replace(target)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def runtime_file_path(script_dir: Path) -> Path:
    return script_dir / PRIVATE_DIRNAME / RUNTIME_DIRNAME / RUNTIME_FILENAME


def read_runtime_state(runtime_file: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(runtime_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def write_runtime_state(runtime_file: Path, payload: dict[str, Any]) -> None:
    write_atomic_bytes(
        runtime_file,
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
    )


def clear_runtime_state(runtime_file: Path, expected_url: str | None = None) -> None:
    if not runtime_file.exists():
        return

    if expected_url:
        state = read_runtime_state(runtime_file)
        current_url = str(state.get("base_url") or "").strip() if state else ""
        if current_url and current_url != expected_url:
            return

    runtime_file.unlink(missing_ok=True)


def current_tty() -> str:
    for fd in (0, 1, 2):
        try:
            if os.isatty(fd):
                return os.ttyname(fd)
        except OSError:
            continue
    return ""


def fetch_json(url: str, timeout: float = 2.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise AppError("Réponse JSON inattendue.")
    return payload


def ping_existing_instance(base_url: str) -> bool:
    try:
        payload = fetch_json(f"{base_url}/api/status")
    except Exception:
        return False

    build_id = str(payload.get("build_id") or payload.get("buildId") or "").strip()
    return payload.get("app") == APP_NAME and build_id == BUILD_ID


def resolve_running_base_url(runtime_file: Path) -> str:
    state = read_runtime_state(runtime_file)
    candidate_url = str(state.get("base_url") or "").strip() if state else ""

    if candidate_url and ping_existing_instance(candidate_url):
        return candidate_url

    clear_runtime_state(runtime_file)

    for candidate in range(APP_PORT, APP_PORT + PORT_SEARCH_SPAN + 1):
        base_url = f"http://{APP_HOST}:{candidate}"
        if not ping_existing_instance(base_url):
            continue
        write_runtime_state(
            runtime_file,
            {
                "app": APP_NAME,
                "build_id": BUILD_ID,
                "base_url": base_url,
                "host": APP_HOST,
                "port": candidate,
                "updated_at": current_timestamp(),
            },
        )
        return base_url

    return ""


def normalize_time(value: object, default: str = "00:00") -> str:
    raw = str(value or "").strip()
    if len(raw) != 5 or raw[2] != ":":
        return default
    hours = raw[:2]
    minutes = raw[3:]
    if not hours.isdigit() or not minutes.isdigit():
        return default
    hour_value = int(hours)
    minute_value = int(minutes)
    if hour_value == 24 and minute_value == 0:
        return "24:00"
    if hour_value < 0 or hour_value > 23 or minute_value < 0 or minute_value > 59:
        return default
    return f"{hour_value:02d}:{minute_value:02d}"


def time_to_minutes(value: object) -> int:
    normalized = normalize_time(value)
    hours = int(normalized[:2])
    minutes = int(normalized[3:])
    return (hours * 60) + minutes


def coerce_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def coerce_int(value: object, default: int, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = default
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def coerce_text(value: object, default: str = "") -> str:
    return str(value or default).strip()


def scan_playlist_options(script_dir: Path) -> list[dict[str, str]]:
    filenames: dict[str, str] = {}
    shows = resolve_show_definitions(script_dir)
    pools_dir = load_runtime_defaults(script_dir)["paths"]["poolsDir"]
    scan_dirs = [
        script_dir / DATA_DIRNAME / "playlists",
        script_dir.parent / "Supervision" / "data" / "playlists",
    ]

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue
        for path in scan_dir.glob("*.m3u"):
            filenames[path.name] = humanize_name(path.stem)

    for show in shows:
        if show["defaultSourceMode"] != "playlist_m3u":
            continue
        filename = Path(show["defaultSourcePath"]).name
        filenames.setdefault(filename, humanize_name(Path(filename).stem))

    options = []
    for filename in sorted(filenames):
        remote_path = str(Path(pools_dir) / filename)
        options.append(
            {
                "id": slugify(Path(filename).stem),
                "label": filenames[filename],
                "filename": filename,
                "path": remote_path,
            }
        )
    return options


def build_random_source_options(script_dir: Path) -> list[dict[str, str]]:
    runtime_paths = load_runtime_defaults(script_dir)["paths"]
    shows = resolve_show_definitions(script_dir)
    items = [
        {"id": "library-all", "label": "Bibliothèque globale", "path": runtime_paths["musicLibraryRoot"]},
        {"id": "jingles", "label": "Dossier jingles", "path": runtime_paths["jinglesDir"]},
        {"id": "reclames", "label": "Dossier réclames", "path": runtime_paths["reclamesDir"]},
        {"id": "emissions-all", "label": "Toutes les émissions", "path": runtime_paths["emissionsDir"]},
    ]

    seen = {item["path"] for item in items}
    for show in shows:
        if show["defaultSourceMode"] != "random_directory":
            continue
        path = show["defaultSourcePath"]
        if path in seen:
            continue
        seen.add(path)
        items.append(
            {
                "id": slugify(show["id"]),
                "label": show["title"],
                "path": path,
            }
        )
    return items


def build_catalog(script_dir: Path) -> dict[str, Any]:
    shows = resolve_show_definitions(script_dir)
    tag_library, show_profiles = build_tag_catalog(script_dir)
    return {
        "shows": shows,
        "sourceModes": SOURCE_MODE_OPTIONS,
        "scheduleModes": SCHEDULE_MODE_OPTIONS,
        "playlists": scan_playlist_options(script_dir),
        "randomSources": build_random_source_options(script_dir),
        "tagLibrary": tag_library,
        "showProfiles": show_profiles,
    }


def make_block(script_dir: Path, slot_id: str, show_id: str, start_time: str, end_time: str, notes: str = "") -> dict[str, Any]:
    show = resolve_show_lookup(script_dir)[0][show_id]
    return {
        "id": slot_id,
        "showId": show_id,
        "title": show["title"],
        "description": show["description"],
        "scheduleMode": "block",
        "category": show["category"],
        "color": show["color"],
        "startTime": start_time,
        "endTime": end_time,
        "pendingUntil": "",
        "sourceMode": show["defaultSourceMode"],
        "sourcePath": show["defaultSourcePath"],
        "notes": notes,
    }


def make_event(script_dir: Path, slot_id: str, show_id: str, start_time: str, pending_until: str, notes: str = "") -> dict[str, Any]:
    show = resolve_show_lookup(script_dir)[0][show_id]
    return {
        "id": slot_id,
        "showId": show_id,
        "title": show["title"],
        "description": show["description"],
        "scheduleMode": "event",
        "category": show["category"],
        "color": show["color"],
        "startTime": start_time,
        "endTime": "",
        "pendingUntil": pending_until,
        "sourceMode": show["defaultSourceMode"],
        "sourcePath": show["defaultSourcePath"],
        "notes": notes,
    }


def build_legacy_default_week(script_dir: Path) -> dict[str, Any]:
    return {
        "mon": {
            "label": DAY_LABELS["mon"],
            "blocks": [
                make_block(script_dir, "mon-block-001", "la-grande-nuit", "00:00", "07:00"),
                make_block(script_dir, "mon-block-002", "fragments", "07:05", "12:00"),
                make_block(script_dir, "mon-block-003", "la-table-du-chat", "12:00", "14:00"),
                make_block(script_dir, "mon-block-004", "rock-de-lapreme", "14:05", "24:00"),
            ],
            "events": [
                make_event(script_dir, "mon-event-001", "le-migou", "07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                make_event(script_dir, "mon-event-002", "l-instinct-mode", "14:00", "14:05", "Chronique courte à 14:00."),
                make_event(script_dir, "mon-event-003", "l-autre-nuit", "23:40", "23:59"),
            ],
        },
        "tue": {
            "label": DAY_LABELS["tue"],
            "blocks": [
                make_block(script_dir, "tue-block-001", "la-grande-nuit", "00:00", "07:00"),
                make_block(script_dir, "tue-block-002", "trajectoires", "07:05", "12:00"),
                make_block(script_dir, "tue-block-003", "la-table-du-chat", "12:00", "14:00"),
                make_block(script_dir, "tue-block-004", "noise-de-lapreme", "14:05", "24:00"),
            ],
            "events": [
                make_event(script_dir, "tue-event-001", "le-migou", "07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                make_event(script_dir, "tue-event-002", "l-instinct-mode", "14:00", "14:05", "Chronique courte à 14:00."),
                make_event(script_dir, "tue-event-003", "le-pseudodocumentaire-de-lespace", "23:40", "23:59"),
            ],
        },
        "wed": {
            "label": DAY_LABELS["wed"],
            "blocks": [
                make_block(script_dir, "wed-block-001", "la-grande-nuit", "00:00", "07:00"),
                make_block(script_dir, "wed-block-002", "immersion", "07:05", "12:00"),
                make_block(script_dir, "wed-block-003", "la-table-du-chat", "12:00", "14:00"),
                make_block(script_dir, "wed-block-004", "les-chats-sauvages", "15:00", "22:00"),
                make_block(script_dir, "wed-block-005", "les-ondes-du-chat-noir", "22:00", "24:00"),
            ],
            "events": [
                make_event(script_dir, "wed-event-001", "le-migou", "07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                make_event(script_dir, "wed-event-002", "les-transmissions-du-dr-john", "14:00", "15:00", "Émission courte du mercredi après-midi."),
            ],
        },
        "thu": {
            "label": DAY_LABELS["thu"],
            "blocks": [
                make_block(script_dir, "thu-block-001", "la-grande-nuit", "00:00", "07:00"),
                make_block(script_dir, "thu-block-002", "traversees", "07:05", "12:00"),
                make_block(script_dir, "thu-block-003", "la-table-du-chat", "12:00", "14:00"),
                make_block(script_dir, "thu-block-004", "cinema-pour-les-oreilles", "14:05", "18:00"),
                make_block(script_dir, "thu-block-005", "radio-gadin", "18:00", "24:00"),
            ],
            "events": [
                make_event(script_dir, "thu-event-001", "le-migou", "07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                make_event(script_dir, "thu-event-002", "l-instinct-mode", "14:00", "14:05", "Chronique courte à 14:00."),
                make_event(script_dir, "thu-event-003", "le-pseudodocumentaire-de-lespace", "23:40", "23:59"),
            ],
        },
        "fri": {
            "label": DAY_LABELS["fri"],
            "blocks": [
                make_block(script_dir, "fri-block-001", "la-grande-nuit", "00:00", "07:00"),
                make_block(script_dir, "fri-block-002", "fragments", "07:05", "12:00"),
                make_block(script_dir, "fri-block-003", "la-table-du-chat", "12:00", "14:00"),
                make_block(script_dir, "fri-block-004", "indie-de-lapreme", "14:05", "18:00"),
                make_block(script_dir, "fri-block-005", "my-favorite-dead-radio", "18:00", "24:00"),
            ],
            "events": [
                make_event(script_dir, "fri-event-001", "le-migou", "07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                make_event(script_dir, "fri-event-002", "l-instinct-mode", "14:00", "14:05", "Chronique courte à 14:00."),
                make_event(script_dir, "fri-event-003", "l-autre-nuit", "23:40", "23:59"),
            ],
        },
        "sat": {
            "label": DAY_LABELS["sat"],
            "blocks": [
                make_block(script_dir, "sat-block-001", "la-grande-nuit", "00:00", "07:00"),
                make_block(script_dir, "sat-block-002", "les-chats-dans-la-couree", "07:00", "12:00"),
                make_block(script_dir, "sat-block-003", "la-table-du-chat", "12:00", "14:00"),
                make_block(script_dir, "sat-block-004", "les-chats-dans-la-couree", "14:05", "18:00"),
                make_block(script_dir, "sat-block-005", "when-day-chokes-a-radio", "18:00", "24:00"),
            ],
            "events": [
                make_event(script_dir, "sat-event-001", "console-toi", "10:00", "10:30", "Émission courte du samedi matin."),
                make_event(script_dir, "sat-event-002", "je-ne-sais-pas-jouer-du-synthe", "11:45", "12:00", "Émission courte juste avant la table du chat."),
                make_event(script_dir, "sat-event-003", "l-instinct-mode", "14:00", "14:05", "Chronique courte à 14:00."),
                make_event(script_dir, "sat-event-004", "le-pseudodocumentaire-de-lespace", "23:40", "23:59"),
            ],
        },
        "sun": {
            "label": DAY_LABELS["sun"],
            "blocks": [
                make_block(script_dir, "sun-block-001", "la-grande-nuit", "00:00", "07:00"),
                make_block(script_dir, "sun-block-002", "le-reveil-lent-du-chat", "07:00", "12:00"),
                make_block(script_dir, "sun-block-003", "la-table-du-chat", "12:00", "14:00"),
                make_block(script_dir, "sun-block-004", "les-ondes-du-chat-noir", "14:00", "15:00"),
                make_block(script_dir, "sun-block-005", "les-siestes-du-chat", "15:00", "18:00"),
                make_block(script_dir, "sun-block-006", "messe-noire", "18:00", "24:00"),
            ],
            "events": [],
        },
    }


def build_default_week(script_dir: Path) -> dict[str, Any]:
    legacy_week = build_legacy_default_week(script_dir)
    parsed_schedule = parse_program_grid_doc(script_dir)
    if len(parsed_schedule) != len(DAY_ORDER):
        parsed_schedule = parse_schedule_spec(script_dir)
    if len(parsed_schedule) != len(DAY_ORDER):
        return legacy_week

    radio_metadata = parse_radio_liq_metadata(script_dir)
    documented_week: dict[str, Any] = {}

    try:
        for day_index, day_key in enumerate(DAY_ORDER, start=1):
            entries = parsed_schedule.get(day_key, [])
            if not entries:
                return legacy_week

            blocks: list[dict[str, Any]] = []
            events: list[dict[str, Any]] = []
            block_count = 0
            event_count = 0
            cursor_time = "00:00"

            for index, entry in enumerate(entries):
                entry_kind = entry.get("kind")
                show_title = coerce_text(entry.get("title"))
                notes = coerce_text(entry.get("notes"))
                next_anchor = next_documented_anchor(entries, index)

                if entry_kind == "explicit":
                    start_time = normalize_time(entry.get("startTime"), cursor_time)
                    show_id = resolve_show_lookup(script_dir)[1].get(canonical_label(show_title), slugify(show_title))
                    seed = infer_dynamic_slot_seed(show_title, "event", radio_metadata, script_dir)
                    if seed["category"] != "editorial_event":
                        entry_kind = "explicit_block"
                    else:
                        display_until = nominal_event_end_time(show_id, start_time)
                        liquidsoap_pending_until = normalize_time(
                            radio_metadata.get("pendingByShowId", {}).get(show_id),
                            display_until,
                        )
                        event_count += 1
                        events.append(
                            make_documented_event(
                                script_dir,
                                f"{day_key}-event-{event_count:03d}",
                                show_title,
                                start_time,
                                display_until,
                                liquidsoap_pending_until,
                                radio_metadata,
                                notes,
                            )
                        )
                        cursor_time = display_until
                        continue

                if entry_kind == "event":
                    show_id = resolve_show_lookup(script_dir)[1].get(canonical_label(show_title), slugify(show_title))
                    start_time = normalize_time(entry.get("startTime"), cursor_time)
                    display_until = nominal_event_end_time(show_id, start_time)
                    liquidsoap_pending_until = normalize_time(
                        radio_metadata.get("pendingByShowId", {}).get(show_id),
                        display_until,
                    )
                    event_count += 1
                    events.append(
                        make_documented_event(
                            script_dir,
                            f"{day_key}-event-{event_count:03d}",
                            show_title,
                            start_time,
                            display_until,
                            liquidsoap_pending_until,
                            radio_metadata,
                            notes,
                        )
                    )
                    cursor_time = display_until
                    continue

                if entry_kind == "block":
                    start_time = normalize_time(entry.get("startTime"), cursor_time)
                    end_time = normalize_time(entry.get("endTime"), start_time)
                elif entry_kind == "after":
                    start_time = cursor_time
                    end_time = next_anchor
                else:
                    start_time = normalize_time(entry.get("startTime"), cursor_time)
                    end_time = next_anchor

                if end_time == "00:00" and time_to_minutes(start_time) > 0:
                    end_time = "24:00"

                block_count += 1
                blocks.append(
                    make_documented_block(
                        script_dir,
                        f"{day_key}-block-{block_count:03d}",
                        show_title,
                        start_time,
                        end_time,
                        radio_metadata,
                        notes,
                    )
                )
                cursor_time = end_time

            documented_week[day_key] = {
                "index": day_index,
                "id": day_key,
                "label": DAY_LABELS[day_key],
                "blocks": blocks,
                "events": events,
            }
    except Exception:
        return legacy_week

    return documented_week


def build_default_state(script_dir: Path) -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "version": STATE_VERSION,
        "timezone": LOCAL_TIMEZONE,
        "savedAt": "",
        "catalog": build_catalog(script_dir),
        "settings": {
            "minuteHeight": 0.62,
            "dressing": resolve_dressing_templates(script_dir),
        },
        "runtime": clone_json(load_runtime_defaults(script_dir)),
        "rotationPolicy": clone_json(DEFAULT_ROTATION_POLICY),
        "documentationFingerprint": build_documentation_fingerprint(script_dir),
        "week": build_default_week(script_dir),
    }


def clone_json(data: Any) -> Any:
    return json.loads(json.dumps(data))


def merge_json_objects(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = clone_json(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_json_objects(merged[key], value)
        else:
            merged[key] = clone_json(value)
    return merged


def config_example_path(script_dir: Path) -> Path:
    return script_dir / CONFIG_EXAMPLE_FILENAME


def config_local_path(script_dir: Path) -> Path:
    return script_dir / PRIVATE_DIRNAME / CONFIG_FILENAME


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_runtime_defaults(script_dir: Path) -> dict[str, Any]:
    runtime = clone_json(DEFAULT_RUNTIME)

    example_path = config_example_path(script_dir)
    if example_path.is_file():
        runtime = merge_json_objects(runtime, read_json_file(example_path).get("runtime", {}))

    local_path = config_local_path(script_dir)
    if local_path.is_file():
        runtime = merge_json_objects(runtime, read_json_file(local_path).get("runtime", {}))

    return normalize_runtime(runtime, DEFAULT_RUNTIME)


def resolve_path_template(value: object, runtime_paths: dict[str, str]) -> str:
    text = coerce_text(value)
    if not text:
        return ""
    return PATH_TEMPLATE_PATTERN.sub(
        lambda match: runtime_paths.get(match.group(1), match.group(0)),
        text,
    )


def resolve_show_definition(show: dict[str, Any], runtime_paths: dict[str, str]) -> dict[str, Any]:
    resolved = clone_json(show)
    resolved["defaultSourcePath"] = resolve_path_template(show.get("defaultSourcePath"), runtime_paths)
    return resolved


def resolve_show_definitions(script_dir: Path) -> list[dict[str, Any]]:
    runtime_paths = load_runtime_defaults(script_dir)["paths"]
    return [resolve_show_definition(show, runtime_paths) for show in SHOW_DEFINITIONS]


def resolve_show_lookup(script_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    shows = resolve_show_definitions(script_dir)
    shows_by_id = {item["id"]: item for item in shows}
    title_index = {}
    for item in shows:
        canonical_title = canonical_label(item["title"])
        title_index[canonical_title] = item["id"]
        for prefix in ("le ", "la ", "les ", "l'", "l’"):
            if canonical_title.startswith(prefix):
                title_index.setdefault(canonical_title[len(prefix):], item["id"])
    return shows_by_id, title_index


def resolve_generator_config_templates(payload: Any, runtime_paths: dict[str, str]) -> Any:
    if isinstance(payload, dict):
        return {
            key: resolve_generator_config_templates(value, runtime_paths)
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [resolve_generator_config_templates(value, runtime_paths) for value in payload]
    if isinstance(payload, str):
        return resolve_path_template(payload, runtime_paths)
    return payload


def resolve_dressing_templates(script_dir: Path) -> list[dict[str, Any]]:
    runtime_paths = load_runtime_defaults(script_dir)["paths"]
    resolved_items = []
    for item in DEFAULT_DRESSING:
        resolved = clone_json(item)
        resolved["sourcePath"] = resolve_path_template(item.get("sourcePath"), runtime_paths)
        resolved_items.append(resolved)
    return resolved_items


def default_slot_for_mode(schedule_mode: str, script_dir: Path) -> dict[str, Any]:
    runtime_paths = load_runtime_defaults(script_dir)["paths"]
    if schedule_mode == "event":
        return {
            "id": "",
            "showId": "",
            "title": "Nouvelle émission",
            "description": "",
            "scheduleMode": "event",
            "category": "editorial_event",
            "color": "event",
            "startTime": "14:00",
            "endTime": "",
            "pendingUntil": "15:00",
            "liquidsoapPendingUntil": "15:00",
            "sourceMode": "random_directory",
            "sourcePath": runtime_paths["emissionsDir"],
            "notes": "",
        }
    return {
        "id": "",
        "showId": "",
        "title": "Nouveau bloc",
        "description": "",
        "scheduleMode": "block",
        "category": "music_block",
        "color": "warm",
        "startTime": "00:00",
        "endTime": "01:00",
        "pendingUntil": "",
        "liquidsoapPendingUntil": "",
        "sourceMode": "playlist_m3u",
        "sourcePath": "",
        "notes": "",
    }


def normalize_slot(slot: dict[str, Any], schedule_mode: str, day_key: str, index: int, script_dir: Path) -> dict[str, Any]:
    base = default_slot_for_mode(schedule_mode, script_dir)
    base.update(slot or {})
    show = resolve_show_lookup(script_dir)[0].get(coerce_text(base.get("showId")))

    start_time = normalize_time(base.get("startTime"), base["startTime"])
    if schedule_mode == "block":
        end_time = normalize_time(base.get("endTime"), base["endTime"])
        if time_to_minutes(end_time) <= time_to_minutes(start_time):
            end_time = start_time
        pending_until = ""
        liquidsoap_pending_until = ""
    else:
        end_time = ""
        pending_until = normalize_time(base.get("pendingUntil"), base["pendingUntil"])
        if time_to_minutes(pending_until) < time_to_minutes(start_time):
            pending_until = start_time
        liquidsoap_pending_until = normalize_time(
            base.get("liquidsoapPendingUntil"),
            pending_until,
        )
        if time_to_minutes(liquidsoap_pending_until) < time_to_minutes(start_time):
            liquidsoap_pending_until = pending_until

    source_mode = coerce_text(base.get("sourceMode"), show["defaultSourceMode"] if show else base["sourceMode"])
    if source_mode not in {"playlist_m3u", "random_directory"}:
        source_mode = "playlist_m3u"

    default_path = show["defaultSourcePath"] if show else base.get("sourcePath", "")
    title = coerce_text(base.get("title"), show["title"] if show else base["title"])
    description = coerce_text(base.get("description"), show["description"] if show else base["description"])

    normalized = {
        "id": coerce_text(base.get("id")) or f"{day_key}-{schedule_mode}-{index:03d}",
        "showId": coerce_text(base.get("showId")),
        "title": title or ("Nouvelle émission" if schedule_mode == "event" else "Nouveau bloc"),
        "description": description,
        "scheduleMode": schedule_mode,
        "category": coerce_text(base.get("category"), show["category"] if show else base["category"]),
        "color": coerce_text(base.get("color"), show["color"] if show else base["color"]),
        "startTime": start_time,
        "endTime": end_time,
        "pendingUntil": pending_until,
        "liquidsoapPendingUntil": liquidsoap_pending_until,
        "sourceMode": source_mode,
        "sourcePath": coerce_text(base.get("sourcePath"), default_path),
        "notes": coerce_text(base.get("notes")),
    }
    return normalized


def normalize_dressing_item(item: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    catchup_mode = coerce_text(item.get("catchupMode"), template["catchupMode"])
    if catchup_mode not in {"until_next_trigger", "fixed_window"}:
        catchup_mode = template["catchupMode"]
    return {
        "id": template["id"],
        "label": template["label"],
        "enabled": coerce_bool(item.get("enabled"), template["enabled"]),
        "intervalMinutes": coerce_int(item.get("intervalMinutes"), template["intervalMinutes"], minimum=1, maximum=360),
        "offsetMinutes": coerce_int(item.get("offsetMinutes"), template["offsetMinutes"], minimum=0, maximum=359),
        "catchupMode": catchup_mode,
        "priority": coerce_int(item.get("priority"), template["priority"], minimum=1, maximum=999),
        "sourceMode": coerce_text(item.get("sourceMode"), template["sourceMode"]),
        "sourcePath": coerce_text(item.get("sourcePath"), template["sourcePath"]),
        "notes": coerce_text(item.get("notes"), template["notes"]),
    }


def normalize_runtime_paths(raw_paths: dict[str, Any], template_paths: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, default_value in template_paths.items():
        normalized[key] = coerce_text(raw_paths.get(key), default_value)
    return normalized


def normalize_runtime_live_input(raw_live: dict[str, Any], template_live: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": coerce_bool(raw_live.get("enabled"), template_live["enabled"]),
        "harborName": coerce_text(raw_live.get("harborName"), template_live["harborName"]),
        "port": coerce_int(raw_live.get("port"), template_live["port"], minimum=1, maximum=65535),
        "password": coerce_text(raw_live.get("password"), template_live["password"]),
        "icy": coerce_bool(raw_live.get("icy"), template_live["icy"]),
    }


def normalize_runtime_output(raw_output: dict[str, Any], template_output: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": template_output["id"],
        "enabled": coerce_bool(raw_output.get("enabled"), template_output["enabled"]),
        "format": coerce_text(raw_output.get("format"), template_output["format"]),
        "bitrateKbps": coerce_int(raw_output.get("bitrateKbps"), template_output["bitrateKbps"], minimum=16, maximum=1024),
        "stereo": coerce_bool(raw_output.get("stereo"), template_output["stereo"]),
        "host": coerce_text(raw_output.get("host"), template_output["host"]),
        "port": coerce_int(raw_output.get("port"), template_output["port"], minimum=1, maximum=65535),
        "password": coerce_text(raw_output.get("password"), template_output["password"]),
        "mount": coerce_text(raw_output.get("mount"), template_output["mount"]),
        "name": coerce_text(raw_output.get("name"), template_output["name"]),
        "description": coerce_text(raw_output.get("description"), template_output["description"]),
        "genre": coerce_text(raw_output.get("genre"), template_output["genre"]),
        "url": coerce_text(raw_output.get("url"), template_output["url"]),
    }


def normalize_runtime(raw_runtime: dict[str, Any] | None, template: dict[str, Any] | None = None) -> dict[str, Any]:
    template = clone_json(template or DEFAULT_RUNTIME)
    source = raw_runtime if isinstance(raw_runtime, dict) else {}
    raw_paths = source.get("paths", {}) if isinstance(source.get("paths"), dict) else {}
    raw_live = source.get("liveInput", {}) if isinstance(source.get("liveInput"), dict) else {}
    raw_outputs = {
        item.get("id"): item for item in source.get("outputs", [])
        if isinstance(item, dict) and item.get("id")
    }
    return {
        "paths": normalize_runtime_paths(raw_paths, template["paths"]),
        "liveInput": normalize_runtime_live_input(raw_live, template["liveInput"]),
        "outputs": [
            normalize_runtime_output(raw_outputs.get(template_output["id"], {}), template_output)
            for template_output in template["outputs"]
        ],
    }


def normalize_rotation_policy(raw_policy: dict[str, Any] | None) -> dict[str, int]:
    source = raw_policy if isinstance(raw_policy, dict) else {}
    return {
        "artistCooldownMinutes": coerce_int(
            source.get("artistCooldownMinutes"),
            DEFAULT_ROTATION_POLICY["artistCooldownMinutes"],
            minimum=0,
            maximum=10080,
        ),
        "albumCooldownMinutes": coerce_int(
            source.get("albumCooldownMinutes"),
            DEFAULT_ROTATION_POLICY["albumCooldownMinutes"],
            minimum=0,
            maximum=10080,
        ),
        "trackCooldownMinutes": coerce_int(
            source.get("trackCooldownMinutes"),
            DEFAULT_ROTATION_POLICY["trackCooldownMinutes"],
            minimum=0,
            maximum=10080,
        ),
    }


def same_visible_text(left: object, right: object) -> bool:
    return canonical_label(left) == canonical_label(right)


def refresh_slot_copy(slot: dict[str, Any], script_dir: Path) -> None:
    show = resolve_show_lookup(script_dir)[0].get(coerce_text(slot.get("showId")))
    if show:
        if not slot.get("title") or same_visible_text(slot.get("title"), show["title"]):
            slot["title"] = show["title"]
        if not slot.get("description") or same_visible_text(slot.get("description"), show["description"]):
            slot["description"] = show["description"]
        return

    if not slot.get("title") or same_visible_text(slot.get("title"), "Nouvelle émission"):
        slot["title"] = "Nouvelle émission"


def refresh_dressing_copy(state: dict[str, Any]) -> None:
    templates = {item["id"]: item for item in DEFAULT_DRESSING}
    for item in state.get("settings", {}).get("dressing", []):
        template = templates.get(item.get("id"))
        if not template:
            continue
        if not item.get("label") or same_visible_text(item.get("label"), template["label"]):
            item["label"] = template["label"]
        if not item.get("notes") or same_visible_text(item.get("notes"), template["notes"]):
            item["notes"] = template["notes"]


def migrate_legacy_schedule(state: dict[str, Any], legacy_version: int, script_dir: Path) -> None:
    schedule_targets = {
        "mon": {
            "events": {
                "le-migou": ("07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                "l-instinct-mode": ("14:00", "14:05", "Chronique courte à 14:00."),
            },
            "blocks": {"fragments": ("07:00", "07:05"), "rock-de-lapreme": ("14:00", "14:05")},
        },
        "tue": {
            "events": {
                "le-migou": ("07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                "l-instinct-mode": ("14:00", "14:05", "Chronique courte à 14:00."),
            },
            "blocks": {"trajectoires": ("07:00", "07:05"), "noise-de-lapreme": ("14:00", "14:05")},
        },
        "wed": {
            "events": {
                "le-migou": ("07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                "les-transmissions-du-dr-john": ("14:00", "15:00", "Émission courte du mercredi après-midi."),
            },
            "blocks": {"immersion": ("07:00", "07:05"), "les-chats-sauvages": ("14:00", "15:00")},
        },
        "thu": {
            "events": {
                "le-migou": ("07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                "l-instinct-mode": ("14:00", "14:05", "Chronique courte à 14:00."),
            },
            "blocks": {"traversees": ("07:00", "07:05"), "cinema-pour-les-oreilles": ("14:00", "14:05")},
        },
        "fri": {
            "events": {
                "le-migou": ("07:00", "07:05", "1 morceau de Le Migou, strictement inférieur à 10 minutes."),
                "l-instinct-mode": ("14:00", "14:05", "Chronique courte à 14:00."),
            },
            "blocks": {"fragments": ("07:00", "07:05"), "indie-de-lapreme": ("14:00", "14:05")},
        },
        "sat": {
            "events": {
                "console-toi": ("10:00", "10:30", "Émission courte du samedi matin."),
                "je-ne-sais-pas-jouer-du-synthe": ("11:45", "12:00", "Émission courte juste avant la table du chat."),
                "l-instinct-mode": ("14:00", "14:05", "Chronique courte à 14:00."),
            },
            "blocks": {"les-chats-dans-la-couree": ("14:00", "14:05")},
        },
    }

    if legacy_version < 3:
        for day_key, targets in schedule_targets.items():
            day = state["week"].get(day_key)
            if not day:
                continue

            for event in day.get("events", []):
                show_id = event.get("showId")
                if show_id not in targets["events"]:
                    continue
                start_time, pending_until, notes = targets["events"][show_id]
                event["startTime"] = start_time
                event["pendingUntil"] = pending_until
                if not event.get("notes") or same_visible_text(event.get("notes"), notes):
                    event["notes"] = notes

            for block in day.get("blocks", []):
                show_id = block.get("showId")
                if show_id in targets["blocks"]:
                    old_start, new_start = targets["blocks"][show_id]
                    if block.get("startTime") == old_start:
                        block["startTime"] = new_start

    if legacy_version < 4:
        for day in state.get("week", {}).values():
            for slot in day.get("blocks", []) + day.get("events", []):
                refresh_slot_copy(slot, script_dir)

        for day_key, targets in schedule_targets.items():
            day = state["week"].get(day_key)
            if not day:
                continue

            for event in day.get("events", []):
                show_id = event.get("showId")
                if show_id not in targets["events"]:
                    continue
                notes = targets["events"][show_id][2]
                if not event.get("notes") or same_visible_text(event.get("notes"), notes):
                    event["notes"] = notes

        refresh_dressing_copy(state)

    if legacy_version < 5:
        refresh_dressing_copy(state)

    if legacy_version < 6:
        refresh_dressing_copy(state)


def normalize_state(raw_state: dict[str, Any] | None, script_dir: Path) -> dict[str, Any]:
    default_state = build_default_state(script_dir)
    state = clone_json(raw_state or {})
    legacy_version = coerce_int(state.get("version"), 0)
    documentation_fingerprint = coerce_text(
        state.get("documentationFingerprint")
    )
    documentation_is_current = (
        documentation_fingerprint == default_state["documentationFingerprint"]
        and legacy_version == STATE_VERSION
    )
    normalized = {
        "app": APP_NAME,
        "version": STATE_VERSION,
        "timezone": coerce_text(state.get("timezone"), LOCAL_TIMEZONE) or LOCAL_TIMEZONE,
        "savedAt": coerce_text(state.get("savedAt")),
        "documentationFingerprint": default_state["documentationFingerprint"],
        "catalog": build_catalog(script_dir),
        "settings": {
            "minuteHeight": float(state.get("settings", {}).get("minuteHeight") or default_state["settings"]["minuteHeight"]),
            "dressing": [],
        },
        "runtime": normalize_runtime(state.get("runtime"), load_runtime_defaults(script_dir)),
        "rotationPolicy": normalize_rotation_policy(state.get("rotationPolicy")),
        "week": {},
    }

    dressing_by_id = {
        item["id"]: item for item in state.get("settings", {}).get("dressing", [])
        if isinstance(item, dict)
    }
    for template in resolve_dressing_templates(script_dir):
        normalized["settings"]["dressing"].append(
            normalize_dressing_item(dressing_by_id.get(template["id"], {}), template)
        )

    raw_week = state.get("week", {}) if documentation_is_current else default_state["week"]
    for day_index, day_key in enumerate(DAY_ORDER, start=1):
        default_day = default_state["week"][day_key]
        source_day = raw_week.get(day_key, {}) if isinstance(raw_week, dict) else {}
        blocks = source_day.get("blocks", default_day["blocks"]) if isinstance(source_day, dict) else default_day["blocks"]
        events = source_day.get("events", default_day["events"]) if isinstance(source_day, dict) else default_day["events"]
        normalized_blocks = [
            normalize_slot(item, "block", day_key, index, script_dir)
            for index, item in enumerate(blocks if isinstance(blocks, list) else [], start=1)
        ]
        normalized_events = [
            normalize_slot(item, "event", day_key, index, script_dir)
            for index, item in enumerate(events if isinstance(events, list) else [], start=1)
        ]
        normalized_blocks.sort(key=lambda item: (time_to_minutes(item["startTime"]), item["title"].lower()))
        normalized_events.sort(key=lambda item: (time_to_minutes(item["startTime"]), item["title"].lower()))
        normalized["week"][day_key] = {
            "index": day_index,
            "id": day_key,
            "label": coerce_text(source_day.get("label"), DAY_LABELS[day_key]) if isinstance(source_day, dict) else DAY_LABELS[day_key],
            "blocks": normalized_blocks,
            "events": normalized_events,
        }

    if documentation_is_current:
        migrate_legacy_schedule(normalized, legacy_version, script_dir)

    return normalized


def state_to_json_bytes(state: dict[str, Any]) -> bytes:
    return (json.dumps(state, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def state_to_jsonl_text(state: dict[str, Any]) -> str:
    lines = []
    for show in state.get("catalog", {}).get("shows", []):
        payload = {"recordType": "show"}
        payload.update(show)
        lines.append(json.dumps(payload, ensure_ascii=False))

    for profile in state.get("catalog", {}).get("showProfiles", []):
        payload = {"recordType": "show_profile"}
        payload.update(profile)
        lines.append(json.dumps(payload, ensure_ascii=False))

    for tag in state.get("catalog", {}).get("tagLibrary", {}).get("observedTags", []):
        payload = {"recordType": "tag"}
        payload.update(tag)
        lines.append(json.dumps(payload, ensure_ascii=False))

    for track in state.get("catalog", {}).get("tagLibrary", {}).get("trackRecords", []):
        payload = {"recordType": "track"}
        payload.update(track)
        lines.append(json.dumps(payload, ensure_ascii=False))

    for dressing in state.get("settings", {}).get("dressing", []):
        payload = {"recordType": "dressing"}
        payload.update(dressing)
        lines.append(json.dumps(payload, ensure_ascii=False))

    runtime = state.get("runtime", {})
    if runtime.get("paths"):
        payload = {"recordType": "runtime_paths"}
        payload.update(runtime["paths"])
        lines.append(json.dumps(payload, ensure_ascii=False))

    if runtime.get("liveInput"):
        payload = {"recordType": "runtime_live_input"}
        payload.update(runtime["liveInput"])
        lines.append(json.dumps(payload, ensure_ascii=False))

    for output in runtime.get("outputs", []):
        payload = {"recordType": "runtime_output"}
        payload.update(output)
        lines.append(json.dumps(payload, ensure_ascii=False))

    rotation_policy = state.get("rotationPolicy", {})
    if rotation_policy:
        payload = {"recordType": "rotation_policy"}
        payload.update(rotation_policy)
        lines.append(json.dumps(payload, ensure_ascii=False))

    for day_key in DAY_ORDER:
        day = state.get("week", {}).get(day_key, {})
        for slot in day.get("blocks", []):
            payload = {"recordType": "slot", "day": day_key, "dayLabel": day.get("label", DAY_LABELS[day_key])}
            payload.update(slot)
            lines.append(json.dumps(payload, ensure_ascii=False))
        for slot in day.get("events", []):
            payload = {"recordType": "slot", "day": day_key, "dayLabel": day.get("label", DAY_LABELS[day_key])}
            payload.update(slot)
            lines.append(json.dumps(payload, ensure_ascii=False))

    return "\n".join(lines) + "\n"


class DesignerService:
    def __init__(self, script_dir: Path) -> None:
        self.script_dir = script_dir
        self.static_dir = script_dir / WEB_DIRNAME
        self.private_dir = script_dir / PRIVATE_DIRNAME
        self.legacy_data_dir = script_dir / DATA_DIRNAME
        self.state_path = self.private_dir / JSON_FILENAME
        self.jsonl_path = self.private_dir / JSONL_FILENAME
        self.legacy_state_path = self.legacy_data_dir / JSON_FILENAME
        self.legacy_jsonl_path = self.legacy_data_dir / JSONL_FILENAME
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.state = self._load_or_initialize()

    def _load_or_initialize(self) -> dict[str, Any]:
        for candidate_path in (self.state_path, self.legacy_state_path):
            if not candidate_path.is_file():
                continue
            try:
                raw_state = json.loads(candidate_path.read_text(encoding="utf-8"))
                state = normalize_state(raw_state, self.script_dir)
                if (
                    not has_readable_timestamp(state.get("savedAt"))
                    or coerce_int(raw_state.get("version"), 0) != STATE_VERSION
                ):
                    state["savedAt"] = current_timestamp()
                self._write_state_files(state)
                return state
            except Exception:
                continue

        state = normalize_state(build_default_state(self.script_dir), self.script_dir)
        state["savedAt"] = current_timestamp()
        self._write_state_files(state)
        return state

    def _write_state_files(self, state: dict[str, Any]) -> None:
        state["catalog"] = build_catalog(self.script_dir)
        if not state.get("savedAt"):
            state["savedAt"] = current_timestamp()
        write_atomic_bytes(self.state_path, state_to_json_bytes(state))
        write_atomic_bytes(self.jsonl_path, state_to_jsonl_text(state).encode("utf-8"))

    def resolve_public_file(self, requested_path: str) -> Path | None:
        raw_path = requested_path or "/"
        relative = "index.html" if raw_path in {"", "/"} else raw_path.lstrip("/")
        candidate = (self.static_dir / relative).resolve()
        try:
            candidate.relative_to(self.static_dir.resolve())
        except ValueError:
            return None
        return candidate

    def payload(self, message: str = "") -> dict[str, Any]:
        return {
            "ok": True,
            "app": APP_NAME,
            "buildId": BUILD_ID,
            "message": message,
            "paths": {
                "json": str(self.state_path),
                "jsonl": str(self.jsonl_path),
            },
            "state": self.state,
        }

    def status_payload(self, base_url: str) -> dict[str, Any]:
        return {
            "ok": True,
            "app": APP_NAME,
            "build_id": BUILD_ID,
            "base_url": base_url,
            "saved_at": self.state.get("savedAt") or None,
            "state_version": self.state.get("version") or STATE_VERSION,
            "paths": {
                "json": str(self.state_path),
                "jsonl": str(self.jsonl_path),
            },
        }

    def save_state(self, raw_state: dict[str, Any]) -> dict[str, Any]:
        normalized = normalize_state(raw_state, self.script_dir)
        normalized["savedAt"] = current_timestamp()
        self.state = normalized
        self._write_state_files(self.state)
        return self.payload("Grille sauvegardée sur disque.")

    def reset_state(self) -> dict[str, Any]:
        self.state = normalize_state(build_default_state(self.script_dir), self.script_dir)
        self.state["savedAt"] = current_timestamp()
        self._write_state_files(self.state)
        return self.payload("Modèle initial restauré.")


class DesignerHTTPServer(ThreadingHTTPServer):
    service: DesignerService
    base_url: str


class DesignerRequestHandler(BaseHTTPRequestHandler):
    server: DesignerHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)

        if parsed.path == "/api/status":
            self.send_json(200, self.server.service.status_payload(self.server.base_url))
            return

        if parsed.path == "/api/state":
            self.send_json(200, self.server.service.payload())
            return

        if parsed.path == "/api/export.json":
            self.send_download("grille-programmes.json", "application/json; charset=utf-8", state_to_json_bytes(self.server.service.state))
            return

        if parsed.path == "/api/export.jsonl":
            self.send_download("grille-programmes.jsonl", "application/x-ndjson; charset=utf-8", state_to_jsonl_text(self.server.service.state).encode("utf-8"))
            return

        target = self.server.service.resolve_public_file(parsed.path)
        if not target or not target.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        self.send_file(target)

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in {"/api/status", "/api/state", "/api/export.json", "/api/export.jsonl"}:
            self.send_response(200)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        target = self.server.service.resolve_public_file(parsed.path)
        if not target or not target.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(target.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/api/save":
            raw_payload = self.read_json_body()
            raw_state = raw_payload.get("state")
            if not isinstance(raw_state, dict):
                self.send_json(400, {"ok": False, "message": "Charge utile invalide."})
                return
            try:
                payload = self.server.service.save_state(raw_state)
            except Exception as error:
                self.send_json(500, {"ok": False, "message": str(error)})
                return
            self.send_json(200, payload)
            return

        if parsed.path == "/api/reset":
            try:
                payload = self.server.service.reset_state()
            except Exception as error:
                self.send_json(500, {"ok": False, "message": str(error)})
                return
            self.send_json(200, payload)
            return

        self.send_error(404, "Route inconnue")

    def read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            return {}
        body = self.rfile.read(content_length)
        if not body:
            return {}
        try:
            parsed = json.loads(body.decode("utf-8"))
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def send_file(self, target: Path) -> None:
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_download(self, filename: str, content_type: str, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def find_available_port(host: str, preferred_port: int, span: int) -> int:
    for candidate in range(preferred_port, preferred_port + span + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if sock.connect_ex((host, candidate)) != 0:
                return candidate
    raise AppError("Aucun port local libre n'a été trouvé.")


def serve_forever(server: DesignerHTTPServer) -> None:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()


def wait_forever(server: DesignerHTTPServer) -> None:
    stop = threading.Event()

    def handle_stop(_signum: int, _frame: object) -> None:
        stop.set()

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            signal.signal(sig, handle_stop)

    try:
        while not stop.is_set():
            time.sleep(0.5)
    finally:
        server.shutdown()
        server.server_close()


def main() -> int:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    runtime_file = runtime_file_path(script_dir)
    existing_url = resolve_running_base_url(runtime_file)

    if existing_url:
        print(f"{APP_NAME} deja pret sur {existing_url}", flush=True)
        if not args.no_open:
            webbrowser.open(existing_url)
        return 0

    service = DesignerService(script_dir)
    port = find_available_port(APP_HOST, APP_PORT, PORT_SEARCH_SPAN)
    server = DesignerHTTPServer((APP_HOST, port), DesignerRequestHandler)
    server.service = service
    url = f"http://{APP_HOST}:{port}/"
    server.base_url = url.rstrip("/")

    write_runtime_state(
        runtime_file,
        {
            "app": APP_NAME,
            "build_id": BUILD_ID,
            "base_url": server.base_url,
            "host": APP_HOST,
            "port": port,
            "pid": os.getpid(),
            "tty": current_tty(),
            "updated_at": current_timestamp(),
        },
    )

    print(f"{APP_NAME} pret sur {url}", flush=True)

    serve_forever(server)

    if not args.no_open:
        webbrowser.open(url)

    try:
        wait_forever(server)
    finally:
        clear_runtime_state(runtime_file, server.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
