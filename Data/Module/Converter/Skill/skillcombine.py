
import struct
import json
import os
import hashlib
from itertools import dropwhile


HEADER_SIZE = 140
DEFAULT_RESERVED_TAIL = b"\x00" * 11


def zro(lst):
    return list(reversed(list(dropwhile(lambda x: x == 0, reversed(lst)))))


def B2Js(blocks_data):
    offset = HEADER_SIZE
    blocks = []
    data_len = len(blocks_data)

    def need(size, limit=None):
        lim = data_len if limit is None else limit
        if offset + size > lim:
            raise ValueError(
                f"Not enough data at 0x{offset:X}: need {size} byte(s), limit=0x{lim:X}"
            )

    def rv(fmt, limit=None):
        nonlocal offset
        size = struct.calcsize(fmt)
        need(size, limit)
        value = struct.unpack_from(fmt, blocks_data, offset)[0]
        offset += size
        return value

    def S(limit=None):
        return rv("<I", limit)

    def S2(limit=None):
        return rv("<H", limit)

    def I(limit=None):
        return rv("<i", limit)

    def B1(limit=None):
        return rv("<B", limit)

    def Str(limit):
        nonlocal offset
        length = S(limit)
        need(length, limit)
        raw_bytes = blocks_data[offset:offset + length]
        offset += length
        return raw_bytes.decode("utf-8", errors="replace").rstrip("\x00")

    while offset < data_len:
        try:
            block_start = offset
            blockinfo = S()
            block_end = block_start + 4 + blockinfo

            if block_end > data_len:
                raise ValueError(
                    f"Block at 0x{block_start:X} ends at 0x{block_end:X}, "
                    f"past EOF 0x{data_len:X}"
                )

            block = {
                "CfgID": I(block_end),
                "DependCfgID": I(block_end),
                "MutexCfgID1": I(block_end),
                "MutexCfgID2": I(block_end),
                "MutexCfgID3": I(block_end),
                "bMapSkillCombineUseRuleID": B1(block_end),
                "TriggerRate": I(block_end),
                "CroupID": I(block_end),
                "FirstLifeStealAttenuation": I(block_end),
                "FollowUpLifeStealAttenuation": I(block_end),
                "bHurtFadeType": B1(block_end),
                "NextDeltaFadeRate": I(block_end),
                "NextLowFadeRate": I(block_end),
                "ClearRule": S(block_end),
                "OverlayFadeRate": I(block_end),
                "OverlayRule": S(block_end),
                "OverlayMax": S(block_end),
                "OverlayMaxGrowType": S(block_end),
                "EffectType": S(block_end),
                "EffectSubType": S(block_end),
                "ShowType": S(block_end),
                "FloatTextID": S(block_end),
                "SkillCombineName": Str(block_end),
                "SkillCombineDescTitle": Str(block_end),
                "SkillCombineDesc": Str(block_end),
                "Prefab": Str(block_end),
                "Duration": I(block_end),
                "DurationGrow": I(block_end),
            }

            block = {k: v for k, v in block.items() if v not in (0, "")}

            bSkillFuncInfoCnt = B1(block_end)

            if bSkillFuncInfoCnt > 0:
                block["SkillFuncInfo"] = []

                for _ in range(bSkillFuncInfoCnt):
                    func = {
                        "SkillFuncType": S(block_end),
                        "SkillFuncFreq": S(block_end),
                        "SkillFuncParam": zro([I(block_end) for _ in range(13)]),
                        "SkillFuncGroup": zro([I(block_end) for _ in range(13)]),
                    }
                    block["SkillFuncInfo"].append(func)

            block2 = {
                "SrcType": I(block_end),
                "IconPath": Str(block_end),
                "bIsShowBuff": B1(block_end),
                "bShowBuffPriority": B1(block_end),
                "OverlayBuffID": I(block_end),
                "bGrowthType": B1(block_end),
                "bIsInheritByKiller": B1(block_end),
                "CanSkillCrit": I(block_end),
                "DamageLimit": I(block_end),
                "MonsterDamageLimit": I(block_end),
                "LongRangeReduction": I(block_end),
                "EffectiveTargetType": I(block_end),
                "bIsAssistEffect": B1(block_end),
                "bAgeImmeExcute": B1(block_end),
                "bAgeImmeStop": B1(block_end),
                "bNotGetHate": B1(block_end),
                "ExtraEffectSlotType": I(block_end),
                "ReplaceHudNameType": S(block_end),
                "bIsHideBuffTimerBar": B1(block_end),
                "bStatSlotType": B1(block_end),
                "bDifferentSource": B1(block_end),
                "bNotShowHitEffectLOD3": B1(block_end),
                "bNotShowDmgFloatLOD3": B1(block_end),
                "bTakeEffectCountMax": B1(block_end),
                "bIsRecordTakeEffectCountWhenAddBuff": B1(block_end),
                "ChangeDurationProperty": S2(block_end),
                "ChangeDurationPropertyRate": I(block_end),
                "DurationMax": I(block_end),
                "bNoAffectByTenacity": B1(block_end),
                "TargetMarkerSlotType": I(block_end),
                "bIsUniqueBuff": B1(block_end),
                "bIsHeroBuff": B1(block_end),
                "bNotShowDmgFloat": B1(block_end),
                "BindSkillID": I(block_end),
                "RemoveRuleID": I(block_end),
                "ControlEffectType": I(block_end),
                "bBuffBorderType": B1(block_end),
                "bBuffRelocateByCopyedActor": B1(block_end),
                "CoverCombineCfgID1": I(block_end),
                "CoverCombineCfgID2": I(block_end),
                "CoverCombineCfgID3": I(block_end),
                "bBUsePreCrit": B1(block_end),

                # Correct order/types from ResSkillCombineCfgInfo:
                "TriggerExtraEffectFadeRate": S2(block_end),   # UInt16
                "GrowthBuffID": I(block_end),                 # Int32
                "bSyncAllActorPerformance": B1(block_end),    # Byte
            }

            block2 = {k: v for k, v in block2.items() if v not in (0, "")}
            block.update(block2)

            reserved = blocks_data[offset:block_end]
            if reserved != DEFAULT_RESERVED_TAIL:
                block["_ReservedTailHex"] = reserved.hex()

            offset = block_end
            blocks.append(block)

        except (ValueError, struct.error) as e:
            print(f"Error reading block at offset 0x{offset:X}: {e}")
            break

    return json.dumps(blocks, ensure_ascii=False, indent=4)


def pack_string(value):
    encoded = str(value).encode("utf-8") + b"\x00"
    return struct.pack("<I", len(encoded)) + encoded


def JstoB(json_data, binary_file):
    blocks = json.loads(json_data)

    binary_data = bytearray()
    header = bytearray()

    header.extend(b"MSES\x07\x00\x00\x00")
    header.extend(struct.pack("<I", 0))  # patched later
    header.extend(struct.pack("<I", len(blocks)))
    header.extend(b"\x61" * 32)
    header.extend(b"\x00" * 16 + b"UTF-8" + b"\x00" * 23)
    header.extend(b"\x00" * (HEADER_SIZE - len(header)))
    binary_data.extend(header)

    last_block_len = 0

    for block in blocks:
        block_data = bytearray()

        def U(fmt, value):
            block_data.extend(struct.pack(fmt, value))

        def U8(value):
            value = int(value)
            if not 0 <= value <= 0xFF:
                raise ValueError(f"Byte value out of range: {value}")
            block_data.append(value)

        def S1(value):
            block_data.extend(pack_string(value))

        def getv(name, *aliases, default=0):
            if name in block:
                return block[name]
            for alias in aliases:
                if alias in block:
                    return block[alias]
            return default

        # ResSkillCombineCfgInfo field order
        U("<i", getv("CfgID"))
        U("<i", getv("DependCfgID", "SkillFuncType"))
        U("<i", getv("MutexCfgID1", "SkillFuncFreq"))
        U("<i", getv("MutexCfgID2"))
        U("<i", getv("MutexCfgID3"))
        U8(getv("bMapSkillCombineUseRuleID"))
        U("<i", getv("TriggerRate"))
        U("<i", getv("CroupID"))
        U("<i", getv("FirstLifeStealAttenuation"))
        U("<i", getv("FollowUpLifeStealAttenuation"))
        U8(getv("bHurtFadeType"))
        U("<i", getv("NextDeltaFadeRate"))
        U("<i", getv("NextLowFadeRate"))
        U("<I", getv("ClearRule"))
        U("<i", getv("OverlayFadeRate"))
        U("<I", getv("OverlayRule"))
        U("<I", getv("OverlayMax"))
        U("<I", getv("OverlayMaxGrowType"))
        U("<I", getv("EffectType"))
        U("<I", getv("EffectSubType"))
        U("<I", getv("ShowType"))
        U("<I", getv("FloatTextID"))
        S1(getv("SkillCombineName", default=""))
        S1(getv("SkillCombineDescTitle", default=""))
        S1(getv("SkillCombineDesc", default=""))
        S1(getv("Prefab", default=""))
        U("<i", getv("Duration"))
        U("<i", getv("DurationGrow"))

        skill_funcs = block.get("SkillFuncInfo", [])
        if len(skill_funcs) > 0xFF:
            raise ValueError("SkillFuncInfo count exceeds UInt8")

        U8(len(skill_funcs))

        for skill_func in skill_funcs:
            U("<I", skill_func.get("SkillFuncType", 0))
            U("<I", skill_func.get("SkillFuncFreq", 0))

            params = (list(skill_func.get("SkillFuncParam", [])) + [0] * 13)[:13]
            groups = (list(skill_func.get("SkillFuncGroup", [])) + [0] * 13)[:13]

            for param in params:
                U("<i", param)

            for group in groups:
                U("<i", group)

        U("<i", getv("SrcType"))
        S1(getv("IconPath", default=""))
        U8(getv("bIsShowBuff"))
        U8(getv("bShowBuffPriority"))
        U("<i", getv("OverlayBuffID"))
        U8(getv("bGrowthType"))
        U8(getv("bIsInheritByKiller"))
        U("<i", getv("CanSkillCrit"))
        U("<i", getv("DamageLimit"))
        U("<i", getv("MonsterDamageLimit"))
        U("<i", getv("LongRangeReduction"))
        U("<i", getv("EffectiveTargetType"))
        U8(getv("bIsAssistEffect"))
        U8(getv("bAgeImmeExcute"))
        U8(getv("bAgeImmeStop"))
        U8(getv("bNotGetHate"))
        U("<i", getv("ExtraEffectSlotType"))
        U("<I", getv("ReplaceHudNameType"))
        U8(getv("bIsHideBuffTimerBar"))
        U8(getv("bStatSlotType"))
        U8(getv("bDifferentSource"))
        U8(getv("bNotShowHitEffectLOD3"))
        U8(getv("bNotShowDmgFloatLOD3"))
        U8(getv("bTakeEffectCountMax"))
        U8(getv("bIsRecordTakeEffectCountWhenAddBuff"))
        U("<H", getv("ChangeDurationProperty"))
        U("<i", getv("ChangeDurationPropertyRate"))
        U("<i", getv("DurationMax"))
        U8(getv("bNoAffectByTenacity"))
        U("<i", getv("TargetMarkerSlotType"))
        U8(getv("bIsUniqueBuff"))
        U8(getv("bIsHeroBuff"))
        U8(getv("bNotShowDmgFloat"))
        U("<i", getv("BindSkillID"))
        U("<i", getv("RemoveRuleID"))
        U("<i", getv("ControlEffectType"))
        U8(getv("bBuffBorderType"))
        U8(getv("bBuffRelocateByCopyedActor"))
        U("<i", getv("CoverCombineCfgID1"))
        U("<i", getv("CoverCombineCfgID2"))
        U("<i", getv("CoverCombineCfgID3"))
        U8(getv("bBUsePreCrit"))

        # New/correct field names. For JSON generated by the OLD tool, preserve
        # its old 7-byte tail layout exactly instead of misinterpreting values.
        has_new_tail = any(
            key in block
            for key in (
                "TriggerExtraEffectFadeRate",
                "GrowthBuffID",
                "bSyncAllActorPerformance",
            )
        )
        has_old_tail = any(
            key in block for key in ("UnknownI4", "UnknownH2", "UnknownB1")
        )

        if has_new_tail or not has_old_tail:
            U("<H", getv("TriggerExtraEffectFadeRate"))
            U("<i", getv("GrowthBuffID"))
            U8(getv("bSyncAllActorPerformance"))
        else:
            U("<i", getv("UnknownI4"))
            U("<H", getv("UnknownH2"))
            U8(getv("UnknownB1"))

        reserved_hex = block.get("_ReservedTailHex")
        if reserved_hex:
            try:
                reserved = bytes.fromhex(reserved_hex)
            except ValueError as e:
                raise ValueError(
                    f"Invalid _ReservedTailHex for CfgID={getv('CfgID')}: {e}"
                ) from e
        else:
            reserved = DEFAULT_RESERVED_TAIL

        block_data.extend(reserved)

        last_block_len = len(block_data)
        binary_data.extend(struct.pack("<I", last_block_len))
        binary_data.extend(block_data)

    binary_data[8:12] = struct.pack("<I", last_block_len + 4)

    md5_hash = hashlib.md5(binary_data[HEADER_SIZE:]).hexdigest().encode("ascii")
    binary_data[96:128] = md5_hash

    binary_data[128:140] = (
        b"\x00\x00\x00\x00"
        b"\x8c\x00\x00\x00"
        b"\x00\x00\x00\x00"
    )

    with open(binary_file, "wb") as bf:
        bf.write(binary_data)


def SkillCombineJson(filepath, mode):
    if mode == 1:
        with open(filepath, "rb") as f:
            json_data = B2Js(f.read())

        with open(filepath, "w", encoding="utf-8") as json_file:
            json_file.write(json_data)

    elif mode == 2:
        with open(filepath, "r", encoding="utf-8") as json_file:
            json_data = json_file.read()

        JstoB(json_data, filepath)

    else:
        raise ValueError("mode must be 1 (bytes -> JSON) or 2 (JSON -> bytes)")
