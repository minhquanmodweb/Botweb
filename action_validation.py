"""Repair malformed XML export boundaries; leave action contents unchanged."""
from pathlib import Path
import xml.etree.ElementTree as ET
import re

def normalize_action_xml(raw,label='action'):
    # These files are text Projects, not the binary ActorInfo format.
    match=re.search(rb'<(Project|HistoryManager)(?:>|\s)',raw)
    if match is None:
        try:
            ET.fromstring(raw)
            return raw
        except ET.ParseError as e:
            raise RuntimeError('Dữ liệu XML không có gốc hợp lệ: '+label) from e
    start=match.start();closing=b'</'+match.group(1)+b'>';end=raw.rfind(closing)
    if end<start:raise RuntimeError('Dữ liệu XML thiếu thẻ đóng: '+label)
    body=raw[start:end+len(closing)]
    try:ET.fromstring(body)
    except ET.ParseError as e:raise RuntimeError('Dữ liệu kỹ năng XML lỗi: '+label+': '+str(e)) from e
    return b'<?xml version="1.0" encoding="utf-8"?>\r\n'+body+b'\r\n'

def validate_action_folder(folder):
    count=0
    for p in Path(folder).rglob('*.xml'):
        p.write_bytes(normalize_action_xml(p.read_bytes(),p.name));count+=1
    return count
