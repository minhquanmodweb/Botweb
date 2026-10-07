"""Generate selected cosmetic hooks using the V10 native path only."""
import copy
import io
import json
import struct
import zipfile
from pathlib import Path
import pyzstd
from resource_encoding import HEADERS, decode, encode
from ifix_codec import parse, serialize
from skin_extras import read_table, write_table
from lobby_portraits import ExactReader, walk, serialize as lua_serialize
from cosmetic_lua import patch_fn, settings_prefix

TEMPLATES = Path(__file__).resolve().parent / 'CosmeticTemplates'

def plain(data, name, dictionary):
    mode = HEADERS.get(data[:4])
    return decode(data, mode, name, dictionary) if mode else data

def associations(folder, ids):
    selected = {int(s) for s in ids}
    _, rows = read_table(Path(folder) / 'ResPersonalButtonCfg.bytes')
    buttons = {}
    for row in rows:
        theme, sid = struct.unpack_from('<II', row)
        if sid in selected:
            buttons.setdefault(sid, theme)
    _, rows = read_table(Path(folder) / 'ResBillboardSkinCfg.bytes')
    billboards = {}
    for row in rows:
        theme, count = struct.unpack_from('<II', row)
        if len(row) != 8 + 4 * count:
            raise ValueError('Invalid billboard skin association')
        for sid in struct.unpack_from('<' + 'I' * count, row, 8):
            if sid in selected:
                billboards.setdefault(sid, theme)
    return buttons, billboards

def native_patch(ids, buttons, billboards, dictionary, enabled):
    template = json.loads((TEMPLATES / 'native.json').read_text())
    for method in template['extern'] + template['fixes'] + template['player_patch']['extern'] + template['player_patch']['fixes']:
        method['params'] = [tuple(p) if isinstance(p, list) else p for p in method['params']]
    op = {name: int(code) for code, name in template['opcodes'].items()}
    def ins(name, arg=0):
        return (op[name], arg)
    first = (TEMPLATES / 'HeroSkin_1.bytes').read_bytes()
    second = (TEMPLATES / 'HeroSkin_2.bytes').read_bytes()
    if not enabled:
        return first, second
    base = parse(plain(first, 'HeroSkin_1.bytes', dictionary))
    patch = copy.deepcopy(base)
    for key in ('types', 'extern', 'fields'):
        assert template[key][:len(base[key])] == base[key]
        patch[key] = copy.deepcopy(template[key])
    selected_buttons = {sid // 100: sid for sid in buttons}
    def getter(mapping):
        code = [tuple(i) for i in template['prefix']]
        for hero, value in sorted(mapping.items()):
            code.extend([ins('Ldloc', 0), ins('Ldc_I4', hero), ins('Ceq'), ins('Brfalse', 3), ins('Ldc_I4', value), ins('Ret', 1)])
        code.extend([ins('Ldc_I4', 0), ins('Ret', 1)])
        return {'code': code, 'eh': []}
    axes = {sid // 100: int(sid in template['full_axis_skins']) for sid in buttons}
    for name, mapping in [('IsOpen', {h: 1 for h in selected_buttons}), ('get_PersonalBtnId', selected_buttons), ('IsUseFullAxis', axes)]:
        fix = copy.deepcopy(next(f for f in template['fixes'] if f['name'] == name))
        fix['method'] = len(patch['methods'])
        patch['methods'].append(getter(mapping))
        patch['fixes'].append(fix)
    player = copy.deepcopy(template['player_patch'])
    prefix = [tuple(i) for i in player['methods'][0]['code'][:29]]
    code = list(prefix)
    # Include billboard-only skins, not only those that also have a button theme.
    for sid in sorted(set(buttons) | set(billboards)):
        body = []
        for mapping, field in [(buttons, 3), (billboards, 2)]:
            if sid in mapping:
                body += [ins('Ldarg', 0), ins('Ldc_I4', mapping[sid]), ins('Stfld', field)]
        code += [ins('Ldarg', 1), ins('Ldc_I4', sid // 100), ins('Ceq'), ins('Brfalse', len(body) + 2)] + body + [ins('Ret', 0)]
    code.append(ins('Ret', 0))
    player['methods'][0] = {'code': code, 'eh': []}
    assert patch['methods'][:len(base['methods'])] == base['methods']
    assert patch['fixes'][:len(base['fixes'])] == base['fixes']
    for tree in (patch, player):
        for method in tree['methods']:
            for pc, (opcode, arg) in enumerate(method['code']):
                if opcode in (op['Br'], op['Brtrue'], op['Brfalse']):
                    assert 0 <= pc + arg < len(method['code'])
    def wrap(tree, original, name):
        raw = serialize(tree)
        assert serialize(parse(raw)) == raw
        mode = HEADERS.get(original[:4])
        return encode(raw, mode, name, dictionary) if mode else raw
    return wrap(patch, first, 'HeroSkin_1.bytes'), wrap(player, second, 'HeroSkin_2.bytes')

def customization(buttons, billboards, dictionary, enabled):
    original = (TEMPLATES / 'Customization.pkg.bytes').read_bytes()
    if not enabled:
        return original
    modules = {
        'Lua_Signed/AOV/Customization/PersonalButton/PersonalButtonModel_lua.bytes': [
            ((147, 151), {v: True for v in buttons.values()}, 'return'),
            ((203, 220), {sid // 100 * 100: sid for sid in buttons}, 'alias'),
            ((780, 788), {key: theme for sid, theme in buttons.items() for key in [sid, sid // 100 * 100]}, 'return')],
        'Lua_Signed/AOV/Customization/HeroBillboard/HeroBillboardModel_lua.bytes': [
            ((375, 388), {sid // 100 * 100: sid for sid in billboards}, 'alias'),
            ((135, 150), {v: True for v in billboards.values()}, 'return')],
        'Lua_Signed/AOV/Customization/PersonalButton/PersonalButtonSystem_lua.bytes': [((14, 18), 'EnablePersonalButton', 'setting')],
        'Lua_Signed/AOV/Customization/HeroBillboard/HeroBillboardSystem_lua.bytes': [((12, 16), 'ShowCommercializeNotify', 'setting')]
    }
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as src, zipfile.ZipFile(result, 'w') as dst:
        for info in src.infolist():
            data = src.read(info)
            if info.filename in modules:
                raw = plain(data, info.filename, dictionary)
                reader = ExactReader(raw)
                start = reader.o
                tree = reader.fn()
                assert reader.o == len(raw) and raw[:start] + lua_serialize(tree) == raw
                for span, mapping, action in modules[info.filename]:
                    fn = next(f for f in walk(tree) if (f['start'], f['end']) == span)
                    if action == 'setting':
                        settings_prefix(fn, mapping)
                    elif mapping:
                        patch_fn(fn, mapping, action)
                raw = raw[:start] + lua_serialize(tree)
                mode = HEADERS.get(data[:4])
                data = encode(raw, mode, info.filename, dictionary) if mode else raw
            dst.writestr(info, data)
    return result.getvalue()

def apply_web_cosmetics(root, version, ids, enabled):
    if version != '1.64.1':
        raise RuntimeError('Cosmetic templates do not match resource version')
    ids = [int(i) for i in ids]
    if not 1 <= len(ids) <= 50 or len({i // 100 for i in ids}) != len(ids):
        raise ValueError('Invalid selected cosmetics')
    root = Path(root)
    folder = root / 'Databin/Client/Huanhua'
    buttons, billboards = associations(folder, ids)
    dictionary = pyzstd.ZstdDict((Path(__file__).parent / 'Data/Code/ZSTD_DICT.xml').read_bytes())
    if enabled:
        header, rows = read_table(folder / 'ResBillboardSkinCfg.bytes')
        for row in rows:
            theme, count = struct.unpack_from('<II', row)
            linked = set(struct.unpack_from('<' + 'I' * count, row, 8))
            additions = {sid // 100 * 100 for sid, value in billboards.items() if value == theme} - linked
            if additions:
                struct.pack_into('<I', row, 4, count + len(additions))
                row.extend(b''.join(struct.pack('<I', sid) for sid in sorted(additions)))
        write_table(folder / 'ResBillboardSkinCfg.bytes', header, rows)
    first, second = native_patch(ids, buttons, billboards, dictionary, enabled)
    (root / 'Thanos').mkdir(exist_ok=True)
    (root / 'Thanos/HeroSkin_1.bytes').write_bytes(first)
    (root / 'Thanos/HeroSkin_2.bytes').write_bytes(second)
    (root / 'Customization.pkg.bytes').write_bytes(customization(buttons, billboards, dictionary, enabled))
    return {'enabled': enabled, 'buttons': sorted(buttons) if enabled else [], 'billboards': sorted(billboards) if enabled else []}
