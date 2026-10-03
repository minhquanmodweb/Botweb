from Data.Module import *
import urllib.parse
import os
import io
import sys
import re
from uuid import uuid4
import json
import shutil
import zipfile
import uuid
import random
import string
import struct
import time
import multiprocessing
import hashlib
import tempfile
import threading
import asyncio
import subprocess
from pathlib import Path
from io import BytesIO
from queue import Queue
from datetime import datetime, timedelta
from concurrent.futures import (
    ThreadPoolExecutor,
    ProcessPoolExecutor,
    as_completed,
    wait
)
from colorama import init, Fore, Style
init(autoreset=True)

import aiohttp
import aiofiles
import pyzstd
from unidecode import unidecode
from colorama import init, Fore, Back, Style

import xml.etree.ElementTree as ET
from xml.dom import minidom

from telegram import (
    Update,
    InputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    WebAppInfo,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove
)

from aiohttp import web as aioweb
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from telegram.error import TimedOut, NetworkError
import logging

from telegram import Update
from telegram.ext import ContextTypes

from telegram.request import HTTPXRequest
from telegram.error import NetworkError

from telegram import Bot
from telegram.error import TelegramError

VUOTLINK_API = os.environ.get("VUOTLINK_API", "")
VUOTLINK_API_URL = "https://vuotlink.xyz/api"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise RuntimeError("Thiếu biến môi trường BOT_TOKEN. Hãy set BOT_TOKEN trong Railway Variables.")
FILE_USERS = "Data/Json/users.json"
FILE_BLOCKED = "Data/Json/blocked_users.json"
RESOURCES_FILE = "Data/Json/resources.json"
FIXRESET_FILE = "Data/Json/fixreset.json"
BUTTON_FILE = "Data/Json/button.json"
MOD_HISTORY_FILE = "Data/Json/mod_history.json"
KEY_FILE = "Data/Json/key.json"
KEYVIP_FILE = "Data/Json/keyvip.json"
FALLBACK_SERVERS = [
    "store1",
    "store2",
    "store3",
    "store4",
    "store5",
    "store6",
    "store7",
    "store8",
    "store9",
    "store10",
    
    "store-eu-gra",
    "store-eu-gra-1",
    "store-eu-gra-2",

    "store-eu-fra",
    "store-eu-fra-1",

    "store-eu-ams",
    "store-eu-ams-1",

    "store-na-iad",
    "store-na-iad-1",

    "store-na-sjc",
    "store-na-sjc-1",

    "store-na-dfw",

    "store-ap-sgp",
    "store-ap-sgp-1",
    "store-ap-sgp-2",

    "store-ap-hkg",
    "store-ap-hkg-1",

    "store-ap-nrt",

    "store-ap-icn",

    "store-sa-gru",

    "store-me-dxb",
]
ADMIN_ID = [8287067985]
SKINS = {}
PAGE_SIZE = 35

WEBAPP_URL = os.environ.get("WEBAPP_URL", "")
WEBAPP_PORT = int(os.environ.get("PORT", 8080))

IOS_DOWNLOADS = {}
IOS_DOWNLOAD_TTL = 3600

def _is_ios_context(context) -> bool:
    return str(context.user_data.get("device") or "").strip().lower() == "ios"

def _public_origin() -> str:
    try:
        p = urllib.parse.urlsplit(WEBAPP_URL)
        if p.scheme and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    except Exception:
        pass
    return ""

def _register_ios_download(file_path: str):
    origin = _public_origin()
    if not origin:
        return None, None
    token = uuid4().hex
    IOS_DOWNLOADS[token] = {
        "path": os.path.abspath(file_path),
        "expires": time.time() + IOS_DOWNLOAD_TTL,
    }
    return f"{origin}/download/ios/{token}", token

async def _cleanup_ios_download(token: str):
    await asyncio.sleep(IOS_DOWNLOAD_TTL)
    info = IOS_DOWNLOADS.pop(token, None)
    if info:
        try:
            os.remove(info["path"])
        except Exception:
            pass

async def ios_download_handler(request):
    token = request.match_info.get("token", "")
    info = IOS_DOWNLOADS.get(token)
    if not info:
        raise aioweb.HTTPNotFound(text="Link tải đã hết hạn.")
    if time.time() > info["expires"]:
        IOS_DOWNLOADS.pop(token, None)
        raise aioweb.HTTPGone(text="Link tải đã hết hạn.")
    file_path = info["path"]
    if not os.path.isfile(file_path):
        IOS_DOWNLOADS.pop(token, None)
        raise aioweb.HTTPNotFound(text="File không còn tồn tại.")

    response = aioweb.FileResponse(path=file_path)
    response.headers["Content-Type"] = "application/zip"
    response.headers["Content-Disposition"] = 'attachment; filename="iOS.zip"'
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

WEBAPP_DATA_CACHE = None


def hero_icon_url(any_skin_id: str) -> str:
    code = any_skin_id[:3] + "0"
    return f"https://dl.ops.kgvn.garenanow.com/hok/VN/HeroHeadPath/30{code}head.jpg"


def hero_icon_url_fallback(any_skin_id: str) -> str:
    code = any_skin_id[:3] + "0"
    return f"https://dl.ops.kgvn.garenanow.com/hok/VN/HeroHeadPath/30{code}.jpg"


def skin_icon_url(skin_id: str) -> str:
    if len(skin_id) == 5 and skin_id[3] == "0":
        code = skin_id[:3] + skin_id[4]
    else:
        code = skin_id
    return f"https://dl.ops.kgvn.garenanow.com/hok/VN/HeroHeadPath/30{code}head.jpg"


def skin_icon_url_fallback(skin_id: str) -> str:
    if len(skin_id) == 5 and skin_id[3] == "0":
        code = skin_id[:3] + skin_id[4]
    else:
        code = skin_id
    return f"https://dl.ops.kgvn.garenanow.com/hok/VN/HeroHeadPath/30{code}.jpg"


WEBAPP_ICON_URL_CACHE = {}
WEBAPP_ICON_CHECK_SEMAPHORE = asyncio.Semaphore(20)

WEBAPP_HEROES_CACHE = None
WEBAPP_HERO_SKINS_CACHE = {}

def _webapp_hero_summary(hero_name: str, skin_dict: dict) -> dict:
    first_id = str(next(iter(skin_dict.values()))) if skin_dict else ""
    return {
        "name": hero_name,
        "icon": hero_icon_url(first_id) if first_id else "",
        "skinCount": len(skin_dict),
    }

async def build_webapp_heroes_payload():
    global WEBAPP_HEROES_CACHE
    if WEBAPP_HEROES_CACHE is not None:
        return WEBAPP_HEROES_CACHE
    heroes = [
        _webapp_hero_summary(hero_name, skin_dict)
        for hero_name, skin_dict in SKINS.items()
        if skin_dict
    ]
    heroes.sort(key=lambda h: unidecode(h["name"]).upper())
    WEBAPP_HEROES_CACHE = {
        "heroes": heroes,
        "totalHeroes": len(heroes),
        "totalSkins": sum(h["skinCount"] for h in heroes),
    }
    return WEBAPP_HEROES_CACHE

async def build_webapp_hero_skins_payload(hero_name: str):
    if hero_name in WEBAPP_HERO_SKINS_CACHE:
        return WEBAPP_HERO_SKINS_CACHE[hero_name]
    skin_dict = SKINS.get(hero_name)
    if not skin_dict:
        return None
    payload = {
        "name": hero_name,
        "skins": [
            {
                "name": skin_name,
                "id": str(skin_id),
                "icon": skin_icon_url(str(skin_id)),
                "icon_fallback": skin_icon_url_fallback(str(skin_id)),
            }
            for skin_name, skin_id in skin_dict.items()
        ],
    }
    WEBAPP_HERO_SKINS_CACHE[hero_name] = payload
    return payload

async def search_webapp_payload(query: str):
    q = unidecode((query or "").strip()).lower()
    if not q:
        return {"heroes": []}
    matches = []
    for hero_name, skin_dict in SKINS.items():
        hero_hit = q in unidecode(hero_name).lower()
        skin_hit = any(q in unidecode(skin_name).lower() for skin_name in skin_dict)
        if hero_hit or skin_hit:
            matches.append(_webapp_hero_summary(hero_name, skin_dict))
        if len(matches) >= 30:
            break
    matches.sort(key=lambda h: unidecode(h["name"]).upper())
    return {"heroes": matches}


async def _resolve_icon_url(session, primary_url: str, fallback_url: str) -> str:
    if primary_url in WEBAPP_ICON_URL_CACHE:
        return WEBAPP_ICON_URL_CACHE[primary_url]

    resolved = primary_url
    async with WEBAPP_ICON_CHECK_SEMAPHORE:
        try:
            async with session.head(primary_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status != 200:
                    resolved = fallback_url
        except Exception:
            resolved = fallback_url

    WEBAPP_ICON_URL_CACHE[primary_url] = resolved
    return resolved


async def build_webapp_payload():
    global WEBAPP_DATA_CACHE
    if WEBAPP_DATA_CACHE is not None:
        return WEBAPP_DATA_CACHE

    heroes = []
    for hero_name, skin_dict in SKINS.items():
        if not skin_dict:
            continue
        first_id = next(iter(skin_dict.values()))
        heroes.append({
            "name": hero_name,
            "icon": hero_icon_url(first_id),
            "icon_fallback": hero_icon_url_fallback(first_id),
            "skins": [
                {
                    "name": skin_name,
                    "id": skin_id,
                    "icon": skin_icon_url(skin_id),
                    "icon_fallback": skin_icon_url_fallback(skin_id),
                }
                for skin_name, skin_id in skin_dict.items()
            ],
        })
    heroes.sort(key=lambda h: unidecode(h["name"]).upper())

    async with aiohttp.ClientSession() as session:
        tasks = []
        for h in heroes:
            tasks.append(_resolve_icon_url(session, h["icon"], h["icon_fallback"]))
            for s in h["skins"]:
                tasks.append(_resolve_icon_url(session, s["icon"], s["icon_fallback"]))

        resolved = await asyncio.gather(*tasks)

    i = 0
    for h in heroes:
        h["icon"] = resolved[i]; i += 1
        h.pop("icon_fallback", None)
        for s in h["skins"]:
            s["icon"] = resolved[i]; i += 1
            s.pop("icon_fallback", None)

    WEBAPP_DATA_CACHE = {
        "heroes": heroes,
        "totalHeroes": len(heroes),
        "totalSkins": sum(len(h["skins"]) for h in heroes),
    }
    return WEBAPP_DATA_CACHE

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else ""

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    users = load_json(FILE_USERS)
    users[user_id] = {
        "first_name": user.first_name,
        "last_name": user.last_name or "",
        "username": user.username
    }
    save_json(FILE_USERS, users)

    # 4 nút giới thiệu như giao diện cũ.
    inline_keyboard = [
        [InlineKeyboardButton("Tham Gia Group", url="https://t.me/modmapfree")],
        [InlineKeyboardButton("Cách Tạo File Mod", url="https://t.me/modmapfree/223")],
        [InlineKeyboardButton("Cách Cài Mod Android", url="https://t.me/modmapfree/16")],
        [InlineKeyboardButton("Cách Cài Mod iOS", url="https://t.me/modmapfree/216")],
    ]
    inline_markup = InlineKeyboardMarkup(inline_keyboard)

    if int(user_id) in ADMIN_ID:
        msg = f"👑 Chào ADMIN {full_name}!"
    else:
        msg = (
            f"👋 Xin Chào {full_name}!\n"
            f"➢ Username: {username}\n"
            f"➢ ID User: {user_id}"
        )

    # Nút WebApp luôn tồn tại dưới bàn phím Telegram.
    skin_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🟢 CHỌN SKIN", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )

    await update.message.reply_text(msg, reply_markup=inline_markup)
    await update.message.reply_text(
        "✨ GIAO DIỆN CHỌN SKIN ĐÃ SẴN SÀNG\n"
        "Bấm 🟢 CHỌN SKIN bên dưới để chọn skin ngay.",
        reply_markup=skin_keyboard
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_ID:
        return

    msg = update.message.text.split(" ", 1)[1]
    if not msg:
        await update.message.reply_text("❌ Dùng: /all nội_dung")
        return

    users = load_json(FILE_USERS)
    blocked = load_json(FILE_BLOCKED)
    sent = 0

    for uid in users:
        if uid in blocked:
            continue
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"📢 THÔNG BÁO TỪ ADMIN:\n{msg}"
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass

    await update.message.reply_text(f"✅ Đã gửi cho {sent} người")

async def chat_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender_id = str(update.effective_user.id)
    text = update.message.text

    users = load_json(FILE_USERS)
    blocked = load_json(FILE_BLOCKED)

    if sender_id not in users:
        return

    if sender_id in blocked:
        return

    sender = users[sender_id]
    sender_name = f"{sender['first_name']} {sender.get('last_name', '')}".strip()
    sender_username = f"@{sender['username']}"

    for uid, info in users.items():
        if uid == sender_id:
            continue
        if uid in blocked:
            continue
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=(
                    "💬 Thông Báo:\n"
                    f"👤 {sender_name} ({sender_username})\n"
                    f"{text}"
                )
            )
            await asyncio.sleep(0.05)
        except:
            pass
            
async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return

    if not context.args:
        await update.message.reply_text("❗ Dùng: /block <user_id hoặc @username>")
        return

    identifier = context.args[0]
    blocked = load_json(FILE_BLOCKED)

    if identifier in blocked:
        await update.message.reply_text(f"{identifier} đã bị block rồi.")
        return

    blocked[identifier] = True
    save_json(FILE_BLOCKED, blocked)
    await update.message.reply_text(f"✅ Đã block {identifier} thành công.")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    if not context.args:
        await update.message.reply_text("❗ Vui lòng gửi: /unblock <user_id>")
        return
    unblock_id = context.args[0]
    blocked = load_json(FILE_BLOCKED)
    if unblock_id not in blocked:
        await update.message.reply_text(f"User ID {unblock_id} không nằm trong danh sách block.")
        return
    blocked.pop(unblock_id)
    save_json(FILE_BLOCKED, blocked)
    await update.message.reply_text(f"✅ Đã bỏ block user {unblock_id} thành công.")

async def send_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_ID:
        await update.message.reply_text("❌ Bạn không có quyền sử dụng lệnh này.")
        return
    try:
        await update.message.reply_text("📤 Đang gửi file...")
        with open(FILE_USERS, "rb") as f1:
            await context.bot.send_document(chat_id=ADMIN_ID, document=InputFile(f1), filename="users.json")
        with open(FILE_BLOCKED, "rb") as f2:
            await context.bot.send_document(chat_id=ADMIN_ID, document=InputFile(f2), filename="blocked_users.json")
        await update.message.reply_text("✅ Đã gửi file cho admin thành công.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi khi gửi file: {e}")
    
async def choosehero(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else None

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or (username and username in blocked):
        await update.message.reply_text("🚫 Bạn Đã Bị Chặn Khỏi Việc Sử Dụng Bot.")
        return

    if not user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    if int(user_id) in ADMIN_ID:
        await mod(update, context)
        return

    keyvip_db = load_json(KEYVIP_FILE)
    user_vip = keyvip_db.get(user_id)

    if user_vip:
        try:
            expire_time = datetime.fromisoformat(user_vip["expired"])
            if datetime.now() <= expire_time:
                await mod(update, context)
                return
        except Exception:
            pass

    context.user_data.setdefault("choose_count", 0)

    if context.user_data["choose_count"] >= 15:
        await update.message.reply_text(
            "⚠️ Bạn Đã Chọn Đủ 15 lần.\n"
            "Hãy Dùng /run Để Tạo Mod Hoặc Dùng /xoadanhsach Để Chọn Lại."
        )
        return

    context.user_data["choose_count"] += 1

    await update.message.reply_text(f"🎯 Lần Chọn: {context.user_data['choose_count']}/15")

    await mod(update, context)
    
async def resources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể lấy Resources.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return
        
    try:
        with open(RESOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            link = data.get("link")
    except Exception as e:
        return
    if not link:
        return
    buttons = [[InlineKeyboardButton(text="Download", url=link)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("Link Download Resources:", reply_markup=reply_markup)

async def fixresetmod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể lấy Fix Reset Mod.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return
        
    try:
        with open(FIXRESET_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            link = data.get("link")
    except Exception as e:
        return
    if not link:
        return
    buttons = [[InlineKeyboardButton(text="Download", url=link)]]
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("Link Download Fix Reset Mod:", reply_markup=reply_markup)

async def downbutton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể lấy Nút Bấm.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    try:
        with open(BUTTON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        await update.message.reply_text(f"Lỗi đọc dữ liệu: {e}")
        return

    if not data:
        await update.message.reply_text("Không có dữ liệu.")
        return

    buttons = []

    for name, link in data.items():
        buttons.append([
            InlineKeyboardButton(text=name, url=link)
        ])

    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(
        "📥 Link Download Nút Bấm:",
        reply_markup=reply_markup
    )
    
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else f"id_{user_id}"

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or username in blocked:
        await update.message.reply_text("🚫 Bạn đã bị chặn khỏi việc sử dụng bot.")
        return

    if not user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    is_admin = int(user_id) in ADMIN_ID
    is_vip = False

    if not is_admin:
        keyvip_db = load_json(KEYVIP_FILE)
        user_vip = keyvip_db.get(user_id)

        if user_vip:
            try:
                expire_time = datetime.fromisoformat(user_vip["expired"])
                if datetime.now() <= expire_time:
                    is_vip = True
            except Exception:
                pass

    if not (is_admin or is_vip):
        choose_count = context.user_data.get("choose_count", 0)

        if choose_count == 0:
            await update.message.reply_text(
                "⚠️ Bạn Chưa Chọn Tướng Và Skin. Hãy Dùng /choosehero Trước."
            )
            return

        if choose_count > 15:
            await update.message.reply_text(
                "⚠️ Bạn Đã Chọn Quá 15 lần.\n"
                "Hãy /xoadanhsach Rồi Chọn Lại."
            )
            return

    ids = context.user_data.get("idmodskin", [])
    skins = context.user_data.get("skin_list", [])
    tuongs = context.user_data.get("tuong_list", [])

    if not ids:
        await update.message.reply_text(
            "⚠️ Bạn Chưa Chọn Tướng Và Skin. Hãy Dùng /choosehero Trước."
        )
        return

    all_ids_str = " ".join(ids)
    all_skins_str = ", ".join(skins)
    all_tuongs_str = ", ".join(tuongs)

    context.user_data['IDMODSKIN'] = all_ids_str

    msg = await update.message.reply_text("⏳ Chuẩn Bị Tạo Mod...")

    await update_progress(
        msg,
        all_tuongs_str,
        all_skins_str,
        all_ids_str,
        percent=0,
        context=context
    )

    await MainCodeMod(
        update,
        context,
        all_ids_str,
        all_skins_str,
        all_tuongs_str,
        msg
    )

    try:
        with open(MOD_HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {}

    entry = {
        "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Hero": tuongs,
        "Skin": skins,
        "ID": ids
    }

    history.setdefault(username, []).append(entry)

    with open(MOD_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    if not (is_admin or is_vip):
        context.user_data["choose_count"] = 0

    context.user_data["idmodskin"] = []
    context.user_data["skin_list"] = []
    context.user_data["tuong_list"] = []
    

async def xemdanhsach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else f"id_{user_id}"

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or username in blocked:
        await update.message.reply_text("🚫 Bạn đã bị chặn khỏi việc sử dụng bot.")
        return

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return
        
    ids = context.user_data.get("idmodskin", [])
    skins = context.user_data.get("skin_list", [])
    tuongs = context.user_data.get("tuong_list", [])

    if not ids:
        await update.message.reply_text("Chưa Chọn Skin Nào.")
        return

    lines = [f"- {t} - {s} [{i}]" for t, s, i in zip(tuongs, skins, ids)]
    await update.message.reply_text("📌 Danh Sách Skin Đã Chọn:\n" + "\n".join(lines))

async def xoadanhsach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else f"id_{user_id}"

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or username in blocked:
        await update.message.reply_text("🚫 Bạn đã bị chặn khỏi việc sử dụng bot.")
        return
        
    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    context.user_data['idmodskin'] = []
    context.user_data['skin_list'] = []
    context.user_data['tuong_list'] = []
    context.user_data.pop('splash_msg', None)

    context.user_data['choose_count'] = 0

    await update.message.reply_text("✅ Đã Xóa Toàn Bộ Danh Sách Skin Đã Chọn.")
    
def load_json(file):
    if os.path.isfile(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def is_blocked(user_id):
    blocked = load_json(FILE_BLOCKED)
    return str(user_id) in blocked

def read_skin_file(filename="skin.txt"):
    skins = {}
    current_hero = None
    with open(filename, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.endswith(":"):
                current_hero = line[:-1]
                skins.setdefault(current_hero, {})
            elif current_hero and " - " in line:
                parts = line.split(" - ", 1)
                if len(parts) == 2:
                    skin_id = parts[0].strip()
                    skin_name = parts[1].strip()
                    # Do not manufacture duplicate UI entries just to increase
                    # the counter. Only keep the first real display name.
                    if skin_name not in skins[current_hero]:
                        skins[current_hero][skin_name] = skin_id
    return skins

def build_keyboard(items, prefix, tuong=None, page=0):
    keyboard, row = [], []
    start, end = page * PAGE_SIZE, (page + 1) * PAGE_SIZE
    items_page = list(items)[start:end]

    max_cols = 4 if prefix == "TUONG" else 3

    for item in items_page:
        callback = f"{prefix}::{item}" if prefix == "TUONG" else f"{prefix}::{tuong}::{item}"
        row.append(InlineKeyboardButton(item, callback_data=callback))
        if len(row) == max_cols:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    total_pages = (len(items) + PAGE_SIZE - 1) // PAGE_SIZE

    if total_pages > 1 and prefix == "TUONG":
        prev_page = page - 1 if page > 0 else total_pages - 1
        next_page = page + 1 if page < total_pages - 1 else 0

        nav_row = [
            InlineKeyboardButton("⬅️", callback_data=f"PAGE::{prev_page}"),
            InlineKeyboardButton(f"Trang {page + 1}/{total_pages}", callback_data="PAGE::NONE"),
            InlineKeyboardButton("➡️", callback_data=f"PAGE::{next_page}")
        ]
        keyboard.append(nav_row)

    if prefix == "SKIN":
        keyboard.append([InlineKeyboardButton("Quay Lại", callback_data="BACK_TO_TUONG")])

    return keyboard
    
async def mod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = build_keyboard(SKINS.keys(), "TUONG", page=0)
    text = "Chọn Tướng Cần Mod:"
    reply_markup = InlineKeyboardMarkup(keyboard)

    chat_id = update.effective_chat.id

    if update.callback_query:
        await update.callback_query.answer()
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    msg = query.message
    chat = msg.chat if msg else None

    try:
        if data.startswith("PAGE::"):
            _, page_str = data.split("::", 1)
            if page_str != "NONE":
                page = int(page_str)
                keyboard = InlineKeyboardMarkup(
                    build_keyboard(SKINS.keys(), "TUONG", page=page)
                )
                if msg:
                    try:
                        await msg.edit_text(
                            "Chọn Tướng Cần Mod:",
                            reply_markup=keyboard
                        )
                    except Exception:
                        pass
            return

        if data == "BACK_TO_TUONG":
            keyboard = InlineKeyboardMarkup(
                build_keyboard(SKINS.keys(), "TUONG", page=0)
            )
            if msg:
                try:
                    await msg.edit_text(
                        "Chọn Tướng Cần Mod:",
                        reply_markup=keyboard
                    )
                except Exception:
                    pass
            return

        if data.startswith("TUONG::"):
            _, tuong = data.split("::", 1)
            skin_dict = SKINS.get(tuong)

            if not skin_dict:
                if msg:
                    try:
                        await msg.edit_text("⚠️ Tướng Không Hợp Lệ.")
                    except Exception:
                        pass
                return

            skin_list = list(skin_dict.keys())
            if not skin_list:
                if msg:
                    try:
                        await msg.edit_text("❌ Không tìm thấy skin cho tướng này.")
                    except Exception:
                        pass
                return

            keyboard = InlineKeyboardMarkup(
                build_keyboard(skin_list, "SKIN", tuong=tuong)
            )
            if msg:
                try:
                    await msg.edit_text(
                        f"Chọn Skin {tuong}:",
                        reply_markup=keyboard
                    )
                except Exception:
                    pass
            return

        if data.startswith("SKIN::"):
            _, tuong, skin = data.split("::", 2)
            skin_id = SKINS.get(tuong, {}).get(skin)

            if not skin_id:
                if msg:
                    try:
                        await msg.edit_text("❌ Skin không hợp lệ.")
                    except Exception:
                        pass
                return

            selected_ids = context.user_data.get("idmodskin", [])
            selected_skins = context.user_data.get("skin_list", [])
            selected_tuongs = context.user_data.get("tuong_list", [])

            if tuong in selected_tuongs:
                i = selected_tuongs.index(tuong)
                selected_tuongs.pop(i)
                selected_skins.pop(i)
                selected_ids.pop(i)

            selected_tuongs.append(tuong)
            selected_skins.append(skin)
            selected_ids.append(str(skin_id))

            context.user_data.update({
                "idmodskin": selected_ids,
                "skin_list": selected_skins,
                "tuong_list": selected_tuongs
            })

            suffix = "_2" if str(skin_id) in {"16707", "13311", "11620"} else ""
            image_url = (
                "https://dl.ops.kgtw.garenanow.com/CHT/"
                f"HeroTrainingLoadingNew_B36/{skin_id}{suffix}.jpg"
            )

            caption = (
                f"Bạn Đã Chọn: {tuong} - {skin}\n"
                f"⚡ Dùng Lệnh /choosehero Để Chọn Tướng - Skin Tiếp Theo\n"
                f"💥 Dùng Lệnh /run Để Tạo File Mod"
            )

            if chat:
                try:
                    await chat.send_action("upload_photo")
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as resp:
                            if resp.status == 200:
                                file = BytesIO(await resp.read())
                                file.name = f"{skin_id}.jpg"
                                file.seek(0)

                                sent = await chat.send_photo(
                                    photo=InputFile(file),
                                    caption=caption
                                )
                                context.user_data["splash_msg"] = sent
                except Exception:
                    pass

            if msg:
                try:
                    await msg.delete()
                except Exception:
                    pass

            return

    except Exception as e:
        print("Button handler error:", e)


# ====================== WEBAPP (MINI APP) ======================

async def webapp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else None

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or (username and username in blocked):
        await update.message.reply_text("🚫 Bạn Đã Bị Chặn Khỏi Việc Sử Dụng Bot.")
        return

    if not user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🟢 CHỌN SKIN", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )

    await update.message.reply_text(
        "✨ GIAO DIỆN CHỌN SKIN\n\n"
        "Bấm nút 🟢 CHỌN SKIN ngay dưới bàn phím.\n"
        "Chọn xong bấm CHẠY MOD, bot sẽ tạo file và gửi về đây.",
        reply_markup=keyboard
    )


async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.web_app_data:
        return

    try:
        payload = json.loads(msg.web_app_data.data)
    except Exception:
        await update.message.reply_text("❌ Dữ liệu từ WebApp không hợp lệ.")
        return

    raw_selections = payload.get("selections", [])[:15]
    if not raw_selections:
        await update.message.reply_text("⚠️ Bạn chưa chọn skin nào.")
        return

    selected_ids, selected_skins, selected_tuongs = [], [], []
    for item in raw_selections:
        tuong = item.get("tuong")
        skin = item.get("skin")
        skin_id = SKINS.get(tuong, {}).get(skin)
        if not skin_id or tuong in selected_tuongs:
            continue
        selected_tuongs.append(tuong)
        selected_skins.append(skin)
        selected_ids.append(str(skin_id))

    if not selected_ids:
        await update.message.reply_text("❌ Không có skin hợp lệ trong lựa chọn.")
        return

    context.user_data.update({
        "idmodskin": selected_ids,
        "skin_list": selected_skins,
        "tuong_list": selected_tuongs
    })

    choose_count = context.user_data.get("choose_count", 0)
    if choose_count >= 15:
        await update.message.reply_text(
            "⚠️ Bạn Đã Chọn Đủ 15 lần.\n"
            "Hãy Dùng /run Để Tạo Mod Hoặc Dùng /xoadanhsach Để Chọn Lại."
        )
        return
    context.user_data["choose_count"] = choose_count + 1

    # Ghi nhận nền tảng nếu WebApp mới có gửi lên. Engine cũ vẫn giữ nguyên
    # cách tạo file để tránh thay đổi logic mod trong trận.
    device = str(payload.get("device") or payload.get("platform") or "Android")
    context.user_data["device"] = device

    lines = "\n".join(f"• {t} - {s}" for t, s in zip(selected_tuongs, selected_skins))
    skin_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🟢 CHỌN SKIN", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )
    await update.message.reply_text(
        f"✅ Đã Chọn {len(selected_ids)} Skin:\n{lines}\n📱 Thiết bị: {device}\n\n⏳ Đang Tự Động Chạy Mod...",
        reply_markup=skin_keyboard
    )

    # Không gửi album ảnh skin vào chat để gọn và nhanh hơn.
    # Tự động chạy mod ngay sau khi chọn skin xong trên WebApp.
    await run(update, context)


async def webapp_index_handler(request):
    return aioweb.FileResponse(path=os.path.join("Data", "WebApp", "index.html"))



async def webapp_api_heroes_handler(request):
    return aioweb.json_response(
        await build_webapp_heroes_payload(),
        headers={"Cache-Control": "public, max-age=3600"},
    )

async def webapp_api_hero_skins_handler(request):
    hero_name = request.query.get("hero", "")
    payload = await build_webapp_hero_skins_payload(hero_name)
    if not payload:
        raise aioweb.HTTPNotFound(text="Hero not found")
    return aioweb.json_response(
        payload,
        headers={"Cache-Control": "public, max-age=3600"},
    )

async def webapp_api_search_handler(request):
    q = request.query.get("q", "")
    return aioweb.json_response(
        await search_webapp_payload(q),
        headers={"Cache-Control": "no-store"},
    )

async def webapp_api_skins_handler(request):
    return aioweb.json_response(await build_webapp_payload())


async def health_handler(request):
    return aioweb.Response(text="OK")


async def start_webserver():
    webapp = aioweb.Application()
    webapp.router.add_get("/", health_handler)
    webapp.router.add_get("/webapp/", webapp_index_handler)
    webapp.router.add_get("/webapp/api/heroes", webapp_api_heroes_handler)
    webapp.router.add_get("/webapp/api/hero-skins", webapp_api_hero_skins_handler)
    webapp.router.add_get("/webapp/api/search", webapp_api_search_handler)
    webapp.router.add_get("/webapp/api/skins", webapp_api_skins_handler)
    webapp.router.add_get("/download/ios/{token}", ios_download_handler)

    runner = aioweb.AppRunner(webapp)
    await runner.setup()
    site = aioweb.TCPSite(runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    print(f"🌐 WebApp server đang chạy tại cổng {WEBAPP_PORT} (route /webapp/)")

# =================================================================

def _progress_bar(percent: int, width: int = 12) -> str:
    percent = max(0, min(100, int(percent)))
    filled = round(width * percent / 100)
    return "▰" * filled + "▱" * (width - filled)

def _human_mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"

async def update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, percent, context):
    try:
        tuongs = [t.strip() for t in all_tuongs_str.split(",")]
        skins = [s.strip() for s in all_skins_str.split(",")]
        list_mod = [f"{t} - {s}" for t, s in zip(tuongs, skins)]
        text = "\n".join(list_mod)
        caption = (
            f"🛠️ Đang Tạo File Mod\n"
            f"{_progress_bar(percent)}  {int(percent)}%\n\n"
            f"{text}"
        )
        if getattr(message, "photo", None):
            await context.bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=caption
            )
        else:
            await message.edit_text(caption)
    except Exception:
        pass
 
async def finish_message(message, all_tuongs_str, all_skins_str, all_ids_str, context):
    if not message:
        return

    try:
        tuongs = [t.strip() for t in all_tuongs_str.split(",") if t.strip()]
        skins = [s.strip() for s in all_skins_str.split(",") if s.strip()]

        list_mod = [f"{t} - {s}" for t, s in zip(tuongs, skins)]
        text = "\n".join(list_mod) if list_mod else "Không có dữ liệu"

        caption = (
            "🎉 Mod Skin:\n"
            f"{text}\n"
            "Hoàn Tất\n\n"
            "➡️ Dùng Lệnh: /layfile\n"
            "➢ Để Nhận Link Tải File Mod 📁."
        )

        if getattr(message, "photo", None):
            await context.bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=caption
            )
        else:
            await message.edit_text(caption)

    except Exception as e:
        print("finish_message error:", e)

async def newkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if int(user.id) not in ADMIN_ID:
        await update.message.reply_text("🚫 Bạn không có quyền tạo Key.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text(
            "📌 Hướng Dẫn:\n"
            "/newkeyvip 7d  (7 ngày)\n"
            "/newkeyvip 12h (12 giờ)"
        )
        return

    time_arg = args[0].lower()

    try:
        if time_arg.endswith("d"):
            value = int(time_arg[:-1])
            delta = timedelta(days=value)
        elif time_arg.endswith("h"):
            value = int(time_arg[:-1])
            delta = timedelta(hours=value)
        else:
            raise ValueError

        if value <= 0:
            raise ValueError

    except ValueError:
        await update.message.reply_text("❗ Định dạng không hợp lệ. Ví dụ: 7d hoặc 12h")
        return

    keydb = load_json(KEY_FILE)

    new_key = "TD-MOD_" + uuid4().hex[:8].upper()
    expired_date = (datetime.now() + delta).replace(minute=0, second=0, microsecond=0).isoformat()

    keydb[new_key] = {
        "expired": expired_date
    }

    save_json(KEY_FILE, keydb)

    await update.message.reply_text(
        f"✅ Key Mới Được Tạo:\n"
        f"🔑 `{new_key}`\n"
        f"🕒 Hết hạn: {expired_date}",
        parse_mode="Markdown"
    )

async def getkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể Get Key.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return
    
    buttons = []
    buttons.append([InlineKeyboardButton("💰 MUA KEY - Telegram ADMIN", url="https://t.me/nhan207")])
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("🔑 Bạn Có Thể Lấy Key Miễn Phí Hoặc Mua Key:", reply_markup=markup)
    
async def inputkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else None

    if int(user_id) in ADMIN_ID:
        await update.message.reply_text("👑 Bạn là ADMIN, không cần nhập key.")
        return

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    await update.message.reply_text("🔑 Vui Lòng Gửi Key Vip Của Bạn:")


async def handle_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    text = update.message.text.strip()

    if int(user_id) in ADMIN_ID:
        return
        
    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return        

    key_db = load_json(KEY_FILE)
    keyvip_db = load_json(KEYVIP_FILE)

    key_info = key_db.get(text)
    if not key_info:
        await update.message.reply_text("❌ Key Không Hợp Lệ.")
        return

    try:
        expire_time = datetime.fromisoformat(key_info["expired"])
        if datetime.now() > expire_time:
            await update.message.reply_text("🔒 Key Đã Hết Hạn.")
            return
    except Exception:
        await update.message.reply_text("⚠️ Lỗi định dạng thời gian key.")
        return

    keyvip_db[user_id] = {
        "first_name": user.first_name,
        "last_name": user.last_name or "",
        "username": user.username or "",
        "keyvip": text,
        "expired": key_info["expired"]
    }
    save_json(KEYVIP_FILE, keyvip_db)

    await update.message.reply_text(
        f"✅ Key VIP Hợp Lệ!\n"
        f"• Name: {user.first_name} {user.last_name or ''}\n"
        f"• Username: @{user.username}\n"
        f"• ID: {user_id}\n"
        f"• Key VIP: {text}\n"
        f"• Hết hạn: {key_info['expired']}"
    )
       
async def get_gofile_servers() -> list[str]:
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        ) as session:
            async with session.get("https://api.gofile.io/servers") as resp:
                if resp.status != 200:
                    print("❌ HTTP status:", resp.status)
                    return []

                js = await resp.json()
                if js.get("status") not in ("ok", "noServer"):
                    print("❌ API status:", js)
                    return []

                data = js.get("data", {})
                servers = data.get("servers") or data.get("serversAllZone") or []

                return [s["name"] for s in servers if "name" in s]
    except Exception as e:
        print("❌ Exception get server:", e)
        return []

class _UploadProgressReader(io.BufferedReader):
    def __init__(self, raw, total, callback=None):
        super().__init__(raw)
        self.total = max(1, int(total))
        self.callback = callback
        self.sent = 0
        self._last_percent = -1
        self._last_time = 0.0

    def read(self, size=-1):
        data = super().read(size)
        if data:
            self.sent += len(data)
            pct = min(100, int(self.sent * 100 / self.total))
            now = time.monotonic()
            if self.callback and (pct >= self._last_percent + 3 or now - self._last_time >= 1.2):
                self._last_percent = pct
                self._last_time = now
                self.callback(self.sent, self.total, pct)
        return data

async def _edit_upload_progress(message, sent: int, total: int, percent: int):
    try:
        title = "✅ Upload Hoàn Tất" if percent >= 100 else "📤 Đang Upload File"
        await message.edit_text(
            f"{title}\n"
            f"{_progress_bar(percent)}  {percent}%\n"
            f"{_human_mb(sent)} / {_human_mb(total)}"
        )
    except Exception:
        pass

async def upload_gofile(file_path: str, progress_callback=None) -> str | None:
    """Upload GoFile without loading the whole ZIP into RAM.

    The old implementation used ``await f.read()`` which buffered the entire
    mod file in memory. Large ZIPs could make Railway restart the container.
    Passing a normal file object to aiohttp lets it stream the body instead.
    """
    filename = os.path.basename(file_path)

    servers = await get_gofile_servers()
    if not servers:
        servers = FALLBACK_SERVERS.copy()

    random.shuffle(servers)

    timeout = aiohttp.ClientTimeout(
        total=None,
        connect=20,
        sock_connect=20,
        sock_read=600,
    )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for server in servers:
            upload_url = f"https://{server}.gofile.io/uploadFile"
            try:
                form = aiohttp.FormData()
                # IMPORTANT: do not use f.read() here. aiohttp streams this
                # file object instead of keeping the whole ZIP in memory.
                total_size = os.path.getsize(file_path)
                with open(file_path, "rb", buffering=0) as raw:
                    f = _UploadProgressReader(raw, total_size, progress_callback)
                    form.add_field(
                        "file",
                        f,
                        filename=filename,
                        content_type="application/octet-stream",
                    )

                    async with session.post(upload_url, data=form) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            print(f"❌ HTTP {resp.status} @ {server}: {body[:200]}")
                            continue

                        js = await resp.json(content_type=None)
                        if js.get("status") != "ok":
                            print(f"❌ GoFile error @ {server}: {js}")
                            continue

                        download = js.get("data", {}).get("downloadPage")
                        if not download:
                            print(f"❌ GoFile không trả downloadPage @ {server}: {js}")
                            continue

                        print("\n✅ Upload thành công!")
                        print(f"📁 File: {filename}")
                        print(f"🌍 Server: {server}")
                        return download

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"❌ Upload network error @ {server}: {type(e).__name__}: {e}")
            except Exception as e:
                print(f"❌ Upload exception @ {server}: {type(e).__name__}: {e}")

    print("❌ Tất Cả Server Đều Thất Bại")
    return None
    
async def create_vuotlink(long_url: str) -> str | None:
    try:
        encoded_url = urllib.parse.quote_plus(long_url)
        api_url = (
            f"{VUOTLINK_API_URL}"
            f"?api={VUOTLINK_API}"
            f"&url={encoded_url}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=30) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                if data.get("status") != "success":
                    print("Vuotlink error:", data)
                    return None

                return data.get("shortenedUrl")
    except Exception as e:
        print("Vuotlink exception:", e)
        return None       
        
async def file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else None

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or (username and username in blocked):
        await update.message.reply_text("🚫 Bạn đã bị chặn khỏi việc sử dụng bot.")
        return

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return

    output_zip = context.user_data.get("output_zip")
    if not output_zip or not os.path.exists(output_zip):
        await update.message.reply_text("❌ Không tìm thấy file mod.\nVui lòng /choosehero lại.")
        return

    # iOS only: keep Android behavior untouched.
    is_ios_download = _is_ios_context(context)
    ios_direct_link = None
    ios_download_token = None

    upload_msg = await update.message.reply_text(
        "📤 Đang Upload File\n"
        f"{_progress_bar(0)}  0%\n"
        f"0.0 MB / {_human_mb(os.path.getsize(output_zip))}"
    )
    loop = asyncio.get_running_loop()
    last_scheduled = {"pct": -1}

    def _upload_cb(sent, total, pct):
        if pct <= last_scheduled["pct"]:
            return
        last_scheduled["pct"] = pct
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(_edit_upload_progress(upload_msg, sent, total, pct))
        )

    if int(user_id) in ADMIN_ID:
        gofile_link = await upload_gofile(output_zip, _upload_cb)
        if not gofile_link:
            await update.message.reply_text("❌ Upload GoFile thất bại.")
            return
        total_size = os.path.getsize(output_zip)
        await _edit_upload_progress(upload_msg, total_size, total_size, 100)
        final_link = gofile_link
        if is_ios_download:
            ios_direct_link, ios_download_token = _register_ios_download(output_zip)
            if ios_direct_link:
                final_link = ios_direct_link
        await update.message.reply_text(
            f"✅ **FILE MOD ĐÃ SẴN SÀNG ( ADMIN )**\n\n"
            f"➢ **Link Tải Mod:**\n{final_link}\n"
            f"❗ **Sử Dụng Trình Duyệt Để Tải Tránh Lỗi**",
            parse_mode="Markdown"
        )
    else:
        keyvip_db = load_json(KEYVIP_FILE)
        user_vip = keyvip_db.get(user_id)

        send_gofile = False
        if user_vip:
            try:
                expire_time = datetime.fromisoformat(user_vip["expired"])
                if datetime.now() <= expire_time:
                    send_gofile = True
            except Exception:
                pass

        if send_gofile:
            gofile_link = await upload_gofile(output_zip, _upload_cb)
            if not gofile_link:
                await update.message.reply_text("❌ Upload GoFile thất bại.")
                return
            total_size = os.path.getsize(output_zip)
            await _edit_upload_progress(upload_msg, total_size, total_size, 100)
            final_link = gofile_link
            if is_ios_download:
                ios_direct_link, ios_download_token = _register_ios_download(output_zip)
                if ios_direct_link:
                    final_link = ios_direct_link
            await update.message.reply_text(
                f"✅ **FILE MOD ĐÃ SẴN SÀNG ( User Key VIP )**\n\n"
                f"➢ **Link Tải Mod:**\n{final_link}\n"
                f"❗ **Sử Dụng Trình Duyệt Để Tải Tránh Lỗi**",
                parse_mode="Markdown"
            )
        else:
            gofile_link = await upload_gofile(output_zip, _upload_cb)
            if not gofile_link:
                await update.message.reply_text("❌ Upload GoFile thất bại.")
                return
            total_size = os.path.getsize(output_zip)
            await _edit_upload_progress(upload_msg, total_size, total_size, 100)

            vuot_target = gofile_link
            if is_ios_download:
                ios_direct_link, ios_download_token = _register_ios_download(output_zip)
                if ios_direct_link:
                    vuot_target = ios_direct_link

            short_link = await create_vuotlink(vuot_target)
            if not short_link:
                if ios_download_token:
                    IOS_DOWNLOADS.pop(ios_download_token, None)
                    ios_download_token = None
                await update.message.reply_text("❌ Tạo link rút gọn Vuotlink thất bại.")
                return

            await update.message.reply_text(
                f"✅ **FILE MOD ĐÃ SẴN SÀNG ( User Normal )**\n\n"
                f"➢ **Link Tải Mod:**\n{short_link}\n"
                f"❗ **Sử Dụng Trình Duyệt Để Tải Tránh Lỗi**",
                parse_mode="Markdown"
            )

    skin_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🟢 CHỌN SKIN", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False
    )
    await update.message.reply_text("🟢 CHỌN SKIN vẫn sẵn sàng cho lượt tiếp theo.", reply_markup=skin_keyboard)

    if is_ios_download and ios_download_token:
        # Safari needs the local file to remain available behind the final
        # Vuotlink destination. It is removed automatically after 1 hour.
        asyncio.create_task(_cleanup_ios_download(ios_download_token))
    else:
        # Android path remains exactly as before.
        try:
            os.remove(output_zip)
        except Exception:
            pass

    context.user_data["output_zip"] = None
        
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)

async def error_handler(update, context):
    err = context.error
    if isinstance(err, (TimedOut, NetworkError)):
        return
    print("Bot error:", err)
    
async def sangdamefx_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else None

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or (username and username in blocked):
        await update.message.reply_text("🚫 Bạn đã bị chặn khỏi việc sử dụng bot.")
        return

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes", callback_data="sangdamefx_yes"),
            InlineKeyboardButton("❌ No", callback_data="sangdamefx_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("ㅤBật Sáng Đậm X2 Hiệu Ứng ❓ㅤ", reply_markup=reply_markup)

async def sangdamefx_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    choice = query.data
    SDages = "yes" if choice == "sangdamefx_yes" else "no"
    context.user_data["SDages"] = SDages

    msg = (
        "✅ Bạn Đã Bật Tính Năng:\n➢ **Sáng Đậm X2 Hiệu Ứng**"
        if SDages == "yes"
        else "✅ Bạn Đã Tắt Tính Năng:\n➢ **Sáng Đậm X2 Hiệu Ứng**"
    )
    await query.edit_message_text(msg, parse_mode="Markdown")

async def nutbam_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else None

    blocked = load_json(FILE_BLOCKED)
    if user_id in blocked or (username and username in blocked):
        await update.message.reply_text("🚫 Bạn đã bị chặn khỏi việc sử dụng bot.")
        return

    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban"
        )
        return
        
    nutbam_data = load_json(NUTBAM_JSON)

    keyboard = []

    for skin_id, skin_name in nutbam_data.items():
        keyboard.append([
            InlineKeyboardButton(
                skin_name,
                callback_data=f"nutbam_{skin_id}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("❌ NO MOD", callback_data="nutbam_none")
    ])

    await update.message.reply_text(
        "**ㅤㅤBật Mod Nút Bấm ( Android ) ❓ㅤㅤ**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
async def nutbam_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    nutbam_data = load_json(NUTBAM_JSON)
    data = query.data

    if data == "nutbam_none":
        context.user_data["NutBam"] = None
        context.user_data["NutBamName"] = None
        msg = "✅ **Đã Tắt Mod Nút Bấm**"
    else:
        skin_id = data.split("_", 1)[1]
        skin_name = nutbam_data.get(skin_id, "Không xác định")

        context.user_data["NutBam"] = skin_id
        context.user_data["NutBamName"] = skin_name

        msg = (
            "✅ **Đã Bật Mod Nút Bấm**\n"
            f"➢ **Tên Nút:** {skin_name}\n"
        )

    await query.edit_message_text(msg, parse_mode="Markdown")
    
async def notify_bot_online(app):
    try:
        await start_webserver()
    except Exception as e:
        print(f"⚠️ Không thể khởi động WebApp server: {e}")

    users = load_json(FILE_USERS)

    for user_id in users.keys():
        try:
            await app.bot.send_message(
                chat_id=int(user_id),
                text=(
    "🟢 Bot Đã ONLINE!\n"
)
                
            )
        except TelegramError as e:
            print(f"Lỗi gửi cho {user_id}: {e}")

init(autoreset=True)

def _verify_generated_mod_zip(zip_path: str, version: str):
    """Fail closed if a generated Android/full mod archive is incomplete/corrupt."""
    if not zip_path or not os.path.isfile(zip_path):
        raise RuntimeError("File ZIP mod không tồn tại sau khi tạo.")
    if os.path.getsize(zip_path) <= 0:
        raise RuntimeError("File ZIP mod có dung lượng 0 byte.")

    base = f"com.garena.game.kgvn/files/Resources/{version}/"
    required = [
        base + "Databin/Client/Actor/heroSkin.bytes",
        base + "Databin/Client/Shop/HeroSkinShop.bytes",
        base + "Databin/Client/Global/HeadImage.bytes",
        base + "StableSystems_3.pkg.bytes",
        base + "KernelLua.pkg.bytes",
    ]

    with zipfile.ZipFile(zip_path, "r") as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"ZIP mod lỗi CRC tại: {bad}")
        names = set(zf.namelist())
        missing = [p for p in required if p not in names]
        if missing:
            raise RuntimeError("ZIP mod thiếu file lõi: " + "; ".join(missing))
        empty = []
        for p in required:
            try:
                if zf.getinfo(p).file_size <= 0:
                    empty.append(p)
            except KeyError:
                empty.append(p)
        if empty:
            raise RuntimeError("ZIP mod có file lõi rỗng: " + "; ".join(empty))

    return True

async def MainCodeMod(update, context, all_ids_str, all_skins_str, all_tuongs_str, message):
    user = update.effective_user
    username = f"@{user.username}" if user.username else ""
    SDages = context.user_data.get("SDages", "no")
   # NutBam = context.user_data.get("NutBam")
    if not update.effective_user.username:
        await update.message.reply_text(
            "⚠️ Bạn chưa có Username Telegram nên không thể sử dụng bot.\n"
            "Hãy đặt Username để sử dụng đầy đủ tính năng bot:\n"
            "Cài Đặt → Chỉnh Sửa Hồ Sơ → Username\n\n"
            "Ví dụ: @ten_cua_ban")
        return
        
    def _safe_rmtree(path, retries=5, delay=0.5):
        for attempt in range(retries):
            try:
                shutil.rmtree(path, ignore_errors=False)
                return
            except Exception:
                if attempt < retries - 1: time.sleep(delay)
        shutil.rmtree(path, ignore_errors=True)
    
    def _safe_move(src, dst, retries=5, delay=0.5):
        for attempt in range(retries):
            try:
                shutil.move(src, dst)
                return
            except Exception:
                if attempt < retries - 1: time.sleep(delay)
                else: raise
    
    ID_HD = ["13215", "59903", "17108", "19016", "15016", "15013", "52908", "54507", "59802", "52710", "59902", "51015", "52113", "13613", "52414", "54805", "13706", "13118", "11120", "19109", "10915", "59901", "13314", "17408", "13213", "11215", "56301", "19908", "53806", "52809", "14214" , "54309", "50613", "15217", "14120", "13316", "15905", "12107", "17519", "10618", "13707", "14215"]
    
    def Setup(Version, FILES_MOD):
        if os.path.exists(FILES_MOD):
            _safe_rmtree(FILES_MOD)
        base = Path(FILES_MOD) / "com.garena.game.kgvn" / "files" / "Resources" / Version
        sub_paths = [
            "Databin/Client/Actor", "Databin/Client/Character", "Databin/Client/Huanhua",
            "Databin/Client/Motion", "Databin/Client/Shop", "Databin/Client/Skill",
            "Databin/Client/Sound", "assetbundle", "Ages/Prefab_Characters/Prefab_Hero", "Prefab_Characters",
            "AssetRefs/Hero"
        ]
        for p in sub_paths:
            (base / p).mkdir(parents=True, exist_ok=True)
    
    def TimNameHero(source_path, ID_SKIN):
        prefix = ID_SKIN[:3] + '_'
        for dir_name in os.listdir(source_path):
            if prefix in dir_name and os.path.isdir(os.path.join(source_path, dir_name)):
                return dir_name
        return None
    
    def process_input_numbers(numbers):
        results = []
        for number in numbers:
            ns = str(number)
            if len(ns) == 5: results.append(number)
            else:
                print(f"The Number {number} Is Invalid (5 digits required).")
                return None
        return results
    
    def safe_filename(name):
        return name.replace("<", "").replace(">", "")
    
    def generate_unique_filename(base_name):
        new_name = base_name
        i = 1
        while os.path.exists(new_name):
            new_name = f"{base_name} [{i}]"
            i += 1
        return new_name

    def suffix_by_mode(base_name, SDages):
        if SDages in ["yes", "sangdamefx_yes"]:
            return f"{base_name} Sáng Đậm"
        else:
            return base_name

    def get_input(prompt):
        while True:
            v = input(prompt).strip().lower()
            if v in {'y', 'n'}: return v
            print("[!] INVALID INPUT! ENTER Y OR N.")
    
    def get_input2(prompt):
        while True:
            v = input(prompt).strip().lower()
            if v in {'1', '2', '3'}: return v
            print("[!] INVALID INPUT! ENTER 1 - 2 - 3.")
    
    async def process_single_skin(ID_SKIN, ctx):
        try:
            Version = ctx['Version']
            FILES_MOD = ctx['FILES_MOD']
            heroSkin = ctx['heroSkin']
            HeroSkinShop = ctx['HeroSkinShop']
            ResSkinSeniorLabelCfg = ctx['ResSkinSeniorLabelCfg']
            OganSkin = ctx['OganSkin']
            ResCharacterComponent = ctx['ResCharacterComponent']
            ResSkinMotionBaseCfg = ctx['ResSkinMotionBaseCfg']
            liteBulletCfg = ctx['liteBulletCfg']
            skillmark = ctx['skillmark']
            skillcombine = ctx['skillcombine']
            Sound_Files = ctx['Sound_Files']
            Huanhua = ctx['Huanhua']
            HeadImage = ctx['HeadImage']
            ResKillBillboardCfg = ctx['ResKillBillboardCfg']
            ktr_Sound = ctx['ktr_Sound']
            Back = ctx['Back']
            hasteE1 = ctx['hasteE1']
            HasteE1_leave = ctx['HasteE1_leave']
            DaofengSprint = ctx['DaofengSprint']
            Born = ctx['Born']
            Dead_Born = ctx['Dead_Born']
            Dance = ctx['Dance']
            DanceBullet = ctx['DanceBullet']
            BlueBuff = ctx['BlueBuff']
            RedBuff_Slow = ctx['RedBuff_Slow']
            BlueBuff_CD = ctx['BlueBuff_CD']
            junglemark = ctx['junglemark']
            Actor = ctx['Actor']
            ResourcePacker = ctx['ResourcePacker']
            ResourceVerification = ctx['ResourceVerification']
            Kb = ctx['Kb']
            ZSTD_DICT = ctx['ZSTD_DICT']           
            
            TEN_SKIN, Vien = Icon_Bac(ID_SKIN, heroSkin, HeroSkinShop, Kb)
            ModLabelDong(ResSkinSeniorLabelCfg, ID_SKIN)
            
            phukienbutter = ctx.get('phukienbutter')
            phukienveres = ctx.get('phukienveres')
            all_skinid0 = ctx.get('all_skinid0')
    
            if ID_SKIN in ['15009', '14111', '11107', '50108', '13015', '13314']:
                hieuungvethan(ID_SKIN, OganSkin)
    
            NAME_HERO = TimNameHero(f'Resources_1/{Version}/Prefab_Characters/Prefab_Hero', ID_SKIN)
            if not NAME_HERO: return False, ID_SKIN
            
            ResSkinExclusiveBattleEffectCfg = f"Resources_1/{Version}/Databin/Client/Huanhua/ResSkinExclusiveBattleEffectCfg.bytes"
            DK_MOD_GT, DK_MOD_BV, xyz_GIATOC, xyz_BIENVE, code_duoi_giatoc = dkgtbv(ID_SKIN, ResSkinExclusiveBattleEffectCfg)
            dieukienmod = (TimDieuKienModAges(ID_SKIN, heroSkin) or ID_SKIN[:3] in ["153", "537"] or ID_SKIN in ["53002", "54506", "17311", "59701", "11621"])

            percent = 56 + round((index + 1) / total_skins * 30)
            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, percent, context)            
                
            Files_1 = f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/{NAME_HERO}/'
            Files_2 = f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/{ID_SKIN}-EFX/{NAME_HERO}/'
            Files_MOD = Files_2 + "skill/"
            Files_3 = f'Resources_1/{Version}/Prefab_Characters/Prefab_Hero/{NAME_HERO}'
            Files_4 = f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/{ID_SKIN}-INFOS/Prefab_Hero/{NAME_HERO}'
    
            with ThreadPoolExecutor(max_workers=9) as ex:
                ex.submit(Mod_Motion, ResSkinMotionBaseCfg, ID_SKIN)
                ex.submit(Sound_Databin, ID_SKIN, Sound_Files)
                ex.submit(Mod_ResCharacterComponent, ResCharacterComponent, ID_SKIN)
                ex.submit(Mod_Skill_Databin, ID_SKIN, ID_HD, liteBulletCfg, skillmark)
                ex.submit(Add_SkillCombineId, ID_SKIN, skillcombine)
                ex.submit(CopyFolder, Files_1, Files_2)
                ex.submit(CopyFolder, Files_3, Files_4)
                if len(ctx['IDMODSKIN']) == 1:
                    ex.submit(Mod_HeadImage, HeadImage, Vien)
                    ex.submit(ModThongBao2, Huanhua, ID_SKIN)
                else:
                    ex.submit(ModThongBao, ResKillBillboardCfg, ID_SKIN)
    
            ID_Sound = IDSOUND_AGES(ID_SKIN, ktr_Sound)
            
            if dieukienmod:
                ModAges(ID_SKIN, Files_MOD, NAME_HERO, ID_Sound)
                SkinAvatar(Files_MOD, NAME_HERO, ID_SKIN)
                FixCodeSkin(ID_SKIN, Files_MOD, NAME_HERO, phukienbutter, phukienveres)
            elif ID_Sound:
                ModSoundAges(ID_SKIN, Files_MOD, ID_Sound)

            if SDages in ["yes", "sangdamefx_yes"]:
                ProcessTrackFiles(Files_MOD, NAME_HERO, "1")
            
            code_bv_skill = ham_code_bv_skill(ID_SKIN, Files_MOD)
            Change_Actor = HDSkill(ID_SKIN, ID_HD, Files_MOD)
            FixStopTrack(Files_MOD)
            AddGetHolidayResourcePath(Files_MOD)
            Function_Track_Guid_AddGetHoliday(Files_MOD)
            # Xml(Files_MOD)
    
            if ID_SKIN == "15009": KillBlueRed(ID_SKIN, BlueBuff, RedBuff_Slow)
            if ID_SKIN == "15013": QTLDKillBlue(ID_SKIN, BlueBuff_CD)
    
            File_AssetRef = f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/AssetRefs/Hero/{ID_SKIN[:3]}_AssetRef.bytes'
            shutil.copy(f'Resources_1/{Version}/AssetRefs/Hero/{ID_SKIN[:3]}_AssetRef.bytes', File_AssetRef)
            Convert_File(File_AssetRef, "1")
            if dieukienmod: AssetRefs(File_AssetRef, ID_SKIN, ID_HD, NAME_HERO, phukienbutter, phukienveres, Change_Actor)
            Convert_File(File_AssetRef, "2")
    
            try:
                target_info_file = next(f for f in os.listdir(Files_4) if f.lower() == f"{NAME_HERO}_actorinfo.bytes".lower())
                Directory = os.path.join(Files_4, target_info_file)
                Convert_File(Directory, "1")
                ID_INFO = str(int(ID_SKIN) + 1)
                if ID_INFO[3:4] == '0': ID_INFO = ID_INFO[:3] + ID_INFO[4:]
                ModInfos(ID_INFO, ID_SKIN, ID_HD, NAME_HERO, Directory, phukienbutter, phukienveres)
                FixCodeInfos(Directory, ID_SKIN, ID_INFO)
                Convert_File(Directory, "2")
            except StopIteration: pass
    
            if ID_SKIN[:3] in ['137', '526']:
                pet_name = '137_SiMaYi_Pet' if ID_SKIN[:3] == '137' else '526_Summoner_Pet'
                pet_dir = f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/{ID_SKIN}-INFOS/Prefab_Pet/{pet_name}'
                shutil.copytree(f'Resources_1/{Version}/Prefab_Characters/Prefab_Pet/{pet_name}', pet_dir, dirs_exist_ok=True)
                if ID_SKIN[:3] == '526':
                    d1 = pet_dir + f'/526_Summoner_Pet_actorinfo.bytes'
                    with open(d1, 'rb') as f_rb: strin = f_rb.read()
                    string = giai(strin, ZSTD_DICT)
                    with open(d1, 'wb') as f_wb: f_wb.write(string)
                    Convert_File(d1, "1"); ModInfos(ID_INFO, ID_SKIN, ID_HD, pet_name, d1, phukienbutter, phukienveres); Convert_File(d1, "2")
            
            if ID_SKIN[:3] in ['192', '196']:
                d2 = f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/{ID_SKIN}-INFOS/Prefab_Hero/{NAME_HERO}/'
                d2 += ('196_Elsu_trap_actorinfo.bytes' if ID_SKIN[:3] == '196' else '192_HuangZhong_lantern_actorinfo.bytes')
                Convert_File(d2, "1"); EfxInfosPhu(ID_SKIN, d2); Convert_File(d2, "2")
                
            if ID_SKIN[:3] == "596":
                base_dir = Files_4
                for suffix in ['', '_02', '_03']:
                    d1 = f'{base_dir}/596_MiLaiDi_JiQi{suffix}_actorinfo.bytes'
                    Convert_File(d1, "1")
                    ModInfos(ID_INFO, ID_SKIN, ID_HD, NAME_HERO, d1, phukienbutter, phukienveres)
                    Convert_File(d1, "2")
    
            Zip_Folder(f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/{ID_SKIN}-EFX', f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/Actor_{ID_SKIN[:3]}_Actions.pkg.bytes')
            Zip_Folder(f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/{ID_SKIN}-INFOS', f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/Actor_{ID_SKIN[:3]}_Infos.pkg.bytes')
    
            if xyz_BIENVE != 'None' and ID_SKIN not in ["13215"]: BienVe(ID_SKIN, ID_HD, NAME_HERO, ID_SKIN[:3], Back, code_bv_skill, xyz_BIENVE.encode(), phukienveres)
            if DK_MOD_GT != 'None' or ID_SKIN in ["15015", "15004", "13311"]: GiaToc(ID_SKIN, ID_HD, NAME_HERO, ID_SKIN[:3], hasteE1, HasteE1_leave, DaofengSprint, xyz_GIATOC.encode(), code_duoi_giatoc.encode())
            Function_Track_Guid(Back, hasteE1, HasteE1_leave)
            
            if ID_SKIN[:3] in ["167", "133", "116", "150"]: ResAwakenBattle(Actor)
            ResourcePackerInfoSetAll(ResourcePacker, ID_INFO)
            
            return True, TEN_SKIN
        except Exception as e:
            print(f"Error processing skin {ID_SKIN}: {e}")
            return False, ID_SKIN
    
    if __name__ == "__main__":
        multiprocessing.freeze_support()
    
        Resources_1 = "Resources_1"
        Version = "UNKNOWN"
        if os.path.exists(Resources_1):
            folders = [f for f in os.listdir(Resources_1) if os.path.isdir(os.path.join(Resources_1, f))]
            if folders: Version = folders[0]
        
        # os.system("cls" if os.name == "nt" else "clear")

        try:
            # os.system("cls" if os.name == "nt" else "clear")
            
            Input_Folder = ''.join(random.choices(string.digits, k=10))
            DECACMOD = "Output/"
            FILES_MOD = DECACMOD + Input_Folder
            
            ctx = {
                'Version': Version, 'FILES_MOD': FILES_MOD,
                'heroSkin': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Actor/heroSkin.bytes",
                'Actor': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Actor/",
                'OganSkin': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Actor/organSkin.bytes",
                'ResCharacterComponent': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Character/ResCharacterComponent.bytes",
                'ResSkinMotionBaseCfg': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Motion/ResSkinMotionBaseCfg.bytes",
                'HeroSkinShop': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Shop/HeroSkinShop.bytes",
                'liteBulletCfg': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Skill/liteBulletCfg.bytes",
                'skillmark': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Skill/skillmark.bytes",
                'skillcombine': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Skill/skillcombine.bytes",
                'HeadImage': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Global/HeadImage.bytes",
                'ResSkinSeniorLabelCfg': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Actor/ResSkinSeniorLabelCfg.bytes",
                'Back': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Back.xml',
                'hasteE1': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/HasteE1.xml',
                'HasteE1_leave': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/HasteE1_leave.xml',
                'DaofengSprint': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/DaofengSprint.xml',
                'Born': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Born.xml',
                'Dead_Born': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Dead_Born.xml',
                'Dance': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Dance.xml',
                'DanceBullet': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/DanceBullet.xml',
                'BlueBuff': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/BlueBuff.xml',
                'RedBuff_Slow': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/RedBuff_Slow.xml',
                'BlueBuff_CD': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/BlueBuff_CD.xml',
                'junglemark': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/junglemark.xml',
                'Versions': f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/version.txt',
                'ktr_Sound': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Sound/BattleBank.bytes",
                'Sound_Files': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Sound",
                'Huanhua': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Huanhua",
                'ResKillBillboardCfg': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Databin/Client/Huanhua/ResKillBillboardCfg.bytes",
                'ResourcePacker': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/assetbundle/resourcepackerinfosetall.assetbundle",
                'ResourceVerification': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/assetbundle/resourceverificationinfosetall.assetbundle",
                'Assetbundle': f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/assetbundle/",
            }

            IDMODSKIN = all_ids_str.split()
            ctx['IDMODSKIN'] = IDMODSKIN

            with open('Data/Code/ZSTD_DICT.xml', 'rb') as f: ctx['ZSTD_DICT'] = pyzstd.ZstdDict(f.read())
            with open('Resources_1/kb.txt', 'r', encoding='utf-8') as f: ctx['Kb'] = f.readlines()

            Setup(Version, FILES_MOD)
            
            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, 10, context)    
                            
            src_files = [f"Resources_1/{Version}/Databin/Client/Actor/heroSkin.bytes", f"Resources_1/{Version}/Databin/Client/Actor/organSkin.bytes", f"Resources_1/{Version}/Databin/Client/Character/ResCharacterComponent.bytes", f"Resources_1/{Version}/Databin/Client/Motion/ResSkinMotionBaseCfg.bytes", f"Resources_1/{Version}/Databin/Client/Shop/HeroSkinShop.bytes", f"Resources_1/{Version}/Databin/Client/Skill/liteBulletCfg.bytes", f"Resources_1/{Version}/Databin/Client/Skill/skillmark.bytes", f"Resources_1/{Version}/Databin/Client/Skill/skillcombine.bytes", f"Resources_1/{Version}/Databin/Client/Global/HeadImage.bytes", f"Resources_1/{Version}/Databin/Client/Actor/ResSkinSeniorLabelCfg.bytes", f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Back.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/HasteE1.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/HasteE1_leave.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/DaofengSprint.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Born.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Dead_Born.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/Dance.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource/DanceBullet.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/BlueBuff.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/RedBuff_Slow.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/BlueBuff_CD.xml', f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource/junglemark.xml', f'Resources_1/{Version}/version.txt']
            dst_files = [ctx['heroSkin'], ctx['OganSkin'], ctx['ResCharacterComponent'], ctx['ResSkinMotionBaseCfg'], ctx['HeroSkinShop'], ctx['liteBulletCfg'], ctx['skillmark'], ctx['skillcombine'], ctx['HeadImage'], ctx['ResSkinSeniorLabelCfg'], ctx['Back'], ctx['hasteE1'], ctx['HasteE1_leave'], ctx['DaofengSprint'], ctx['Born'], ctx['Dead_Born'], ctx['Dance'], ctx['DanceBullet'], ctx['BlueBuff'], ctx['RedBuff_Slow'], ctx['BlueBuff_CD'], ctx['junglemark'], ctx['Versions']]
            
            with ThreadPoolExecutor(max_workers=16) as ex:
                ex.submit(CopyFile1, src_files, dst_files)
                ex.submit(CopyFolder, f"Resources_1/{Version}/Databin/Client/Sound/", f"{ctx['Sound_Files']}/")
                ex.submit(CopyFolder, f"Resources_1/{Version}/Databin/Client/Huanhua/", f"{ctx['Huanhua']}/", exclude=["ResSkinExclusiveBattleEffectCfg.bytes"])
                ex.submit(CopyFolder, f"Resources_1/{Version}/assetbundle/", ctx['Assetbundle'])
                ex.submit(CopyFile, f"Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/CommonActions.pkg.bytes", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/CommonActions.pkg.bytes")
            
            with ThreadPoolExecutor(max_workers=10) as ex:
                ex.submit(HeroSkinJson, ctx['heroSkin'], 1)
                ex.submit(HeroSkinShopJson, ctx['HeroSkinShop'], 1)
                ex.submit(SeniorLabelJson, ctx['ResSkinSeniorLabelCfg'], 1)
                ex.submit(LitebulletJson, ctx['liteBulletCfg'], 1)
                ex.submit(SkillMarkJson, ctx['skillmark'], 1)
                ex.submit(SkillCombineJson, ctx['skillcombine'], 1)
                ex.submit(MotionJson, ctx['ResSkinMotionBaseCfg'], 1)
                ex.submit(SoundDatabinJs, ctx['Sound_Files'], 1)
                ex.submit(CharacterJson, ctx['ResCharacterComponent'], 1)
                ex.submit(HeadImageJson, ctx['HeadImage'], 1)

            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, 49, context)    
            processed_skins = []
            total_skins = len(IDMODSKIN)
            for index, id_skin in enumerate(IDMODSKIN):
                if id_skin == "11620": ctx['phukienbutter'] = "3"
                elif id_skin == "52007": ctx['phukienveres'] = "3"
        
                success, name = await process_single_skin(id_skin, ctx)
       
                if success:
                    processed_skins.append(name)
                    print(f" ✅ {id_skin} Xong!")
                    
                    with open(f'{FILES_MOD}/DanhSáchSkin.txt', 'a', encoding="utf-8") as f_log:
                        f_log.write(f'{name}\n')                   
            
            with ThreadPoolExecutor(max_workers=16) as ex:
                xmls = [ctx['junglemark'], ctx['Back'], ctx['hasteE1'], ctx['HasteE1_leave'], ctx['DaofengSprint'], ctx['Born'], ctx['Dead_Born'], ctx['Dance'], ctx['DanceBullet']]
                for x in xmls:
                    ex.submit(lambda f=x: Xml(f))
                
                conver = [(HeroSkinJson, ctx['heroSkin']), (HeroSkinShopJson, ctx['HeroSkinShop']), (SeniorLabelJson, ctx['ResSkinSeniorLabelCfg']), (LitebulletJson, ctx['liteBulletCfg']), (SkillMarkJson, ctx['skillmark']), (SkillCombineJson, ctx['skillcombine']),(MotionJson, ctx['ResSkinMotionBaseCfg']), (SoundDatabinJs, ctx['Sound_Files']), (CharacterJson, ctx['ResCharacterComponent']), (HeadImageJson, ctx['HeadImage'])]
                for func, path in conver:
                    ex.submit(lambda fu=func, p=path: fu(p, 2))                  

            shutil.copy2(f"Resources_1/{Version}/StableSystems_3.pkg.bytes", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/StableSystems_3.pkg.bytes")
            shutil.copy2(f"Resources_1/{Version}/KernelLua.pkg.bytes", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/KernelLua.pkg.bytes")
            # FixReset(ctx['ResourceVerification'])
            # lz4(ctx['Assetbundle'])
            # ReplacePath(IDMODSKIN, ctx['ResourcePacker'])
            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, 90, context)
                            
            AddFoldersToZip(f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/CommonActions.pkg.bytes", [f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource"])

            File1 = f"{FILES_MOD}/com.garena.game.kgvn/files/"
            File2 = f"{FILES_MOD}/iOS"
            File3 = f"{FILES_MOD}/iOS/Resources/{Version}/assetbundle/"
            CopyFolder(File1, File2)
            NenAsset(File3, "ios")
            Zip_Folder(File2, f'{FILES_MOD}/iOS.zip')

            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, 95, context)
                                                    
            soskin = len(processed_skins)
            base_name = f"{DECACMOD}[{username}] - Pack {soskin} Skin - TD MOD" if soskin > 1 else f"{DECACMOD}[{username}] - {re.sub(r'[^\w\s-]', '', processed_skins[0] if processed_skins else 'Mod')} - TD MOD"
            FILES_MOD_NEW = generate_unique_filename(suffix_by_mode(base_name, SDages))
            _safe_move(FILES_MOD, FILES_MOD_NEW)

            output_zip = f"{FILES_MOD_NEW}.zip"
            Zip_Folder(FILES_MOD_NEW, output_zip)

            # Do not publish a partially generated/corrupt archive. This does not
            # modify Android resources; it only validates the finished ZIP.
            _verify_generated_mod_zip(output_zip, Version)

            if os.path.exists(output_zip):
                fast_rmtree(FILES_MOD_NEW)
            
            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, 100, context)
            await asyncio.sleep(0.1)    
            context.user_data['output_zip'] = output_zip
            await finish_message(message, all_tuongs_str, all_skins_str, all_ids_str, context)
            print("Done Mod!")
        except Exception as e: print(f"Lỗi: {e}")

if __name__ == "__main__":
    import time

    request = HTTPXRequest(
        connect_timeout=30,
        read_timeout=300,
        write_timeout=300,
        pool_timeout=30,
    )

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .post_init(notify_bot_online)
        .build()
    )

    SKINS = read_skin_file("Data/ID/skin.txt")

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run))
    app.add_handler(CommandHandler("getkeyvip", getkey))
    app.add_handler(CommandHandler("xemdanhsach", xemdanhsach))
    app.add_handler(CommandHandler("xoadanhsach", xoadanhsach))
    app.add_handler(CommandHandler("choosehero", choosehero))
    app.add_handler(CommandHandler("webapp", webapp_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
    app.add_handler(CommandHandler("layfile", file_command))
    app.add_handler(CommandHandler("resources", resources))
    # app.add_handler(CommandHandler("fixreset", fixresetmod))
    # app.add_handler(CommandHandler("nutbam", downbutton))
    app.add_handler(CommandHandler("block", block_user))
    app.add_handler(CommandHandler("unblock", unblock_user))
    app.add_handler(CommandHandler("sendfiles", send_files))
    app.add_handler(CommandHandler("sangdamefx", sangdamefx_command))
    app.add_handler(CallbackQueryHandler(sangdamefx_callback, pattern="^sangdamefx_"))
    # app.add_handler(CommandHandler("nutbam", nutbam_command))
    # app.add_handler(CallbackQueryHandler(nutbam_callback, pattern="^nutbam_"))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(CommandHandler("all", broadcast))
    app.add_handler(CommandHandler("newkeyvip", newkey))
    app.add_handler(CommandHandler("inputkeyvip", inputkey))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_key_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_all))

    print("✅ Bot đang chạy...")

    while True:
        try:
            app.run_polling(drop_pending_updates=True, close_loop=False)
        except NetworkError:
            time.sleep(5)            