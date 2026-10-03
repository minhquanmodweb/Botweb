"""Web-only corrections for identified picture and actor-info inconsistencies."""
import copy,json,re
from pathlib import Path
import xml.etree.ElementTree as ET
from Data.Module.Databin.Actor_Shop.heroSkin_HeroSkinShop import Icon_Bac as legacy_icon
from Data.Module.Infos.Code import ModInfos as legacy_infos
from Data.Module.AssetRefs.Code import AssetRefs as legacy_asset_refs
from Data.Module.Ages.FixCodeSkin import FixCodeSkin as legacy_fix_skin

def FixCodeSkin(sid,*args):
    # The old Nakroth U1 patch replaces real particle paths with a placeholder.
    # Use the native action, already retargeted by ModAges, for this skin.
    if str(sid)=='15015':return
    return legacy_fix_skin(sid,*args)

def AssetRefs(path,sid,*args):
    legacy_asset_refs(path,sid,*args)
    tree=ET.parse(path);root=tree.getroot();base=root.find('baseSubset');skins=root.find('skinSubset')
    if base is None or skins is None:return
    info=str(int(sid)+1)
    if info[3:4]=='0':info=info[:3]+info[4:]
    for key in (info,str(sid)):
        selected=next((x.find('v2') for x in skins if x.find('v1') is not None and x.find('v1').get('value')==key),None)
        if selected is not None:break
    if selected is None:return
    for group in selected:
        target=base.find(group.tag)
        if target is None:
            base.append(copy.deepcopy(group));continue
        for entry in group:
            v1=entry.find('v1')
            if v1 is None:continue
            matches=[x for x in target if x.find('v1') is not None and x.find('v1').get('value')==v1.get('value')]
            for x in matches:target.remove(x)
            target.append(copy.deepcopy(entry))
    tree.write(path,encoding='utf-8',xml_declaration=True)

def Icon_Bac(sid,icon_file,shop_file,kb):
    original=json.loads(Path(icon_file).read_text())
    selected=next((x for x in original if str(x['ID'])==sid),None)
    if selected is None:raise RuntimeError('Không có dữ liệu ảnh skin '+sid)
    group=[x for x in original if str(x['ID']).startswith(sid[:3])]
    picture=Path(selected.get('SkinShowUrl','')).stem
    if len(group)>2 and len({x.get('SkinName') for x in group})==1 and re.fullmatch(r'\d{5}',picture) and picture!=sid:
        raise RuntimeError('Dữ liệu nguồn '+sid[:3]+' đã bị mod trước đó, cần resource sạch để tạo skin '+sid)
    in_bundle=selected.get('bIsInAB',0)
    result=legacy_icon(sid,icon_file,shop_file,kb)
    data=json.loads(Path(icon_file).read_text())
    selected=next(x for x in data if str(x['ID'])==sid)
    for row in data:
        if str(row['ID']).startswith(sid[:3]):
            # Preserve the selected image key for the default slot too.
            row['SkinPicID']=selected['SkinPicID']
            row['bIsInAB']=in_bundle
    # All skin tiles show the chosen mod. Preserve native image/loading flags.
    chosen_original=next(x for x in original if str(x['ID'])==sid)
    for row in data:
        if str(row['ID']).startswith(sid[:3]):
            for field in ('SkinPicCDNPath','SkinHeadCDNPath','SkinShowUrl','bSkinDynamicPath','SkinBgAndTable'):
                if field in chosen_original and sid not in ('16707','11620','13311'):
                    row[field]=chosen_original[field]
            row['bIsInAB']=in_bundle
    # The base ID is shared by hero selection and minimap portrait lookups.
    # Keep its native head key/path; use the separate full CDN path for the lobby.
    base_id=sid[:3]+'00'
    base_original=next((x for x in original if str(x['ID'])==base_id),None)
    base_row=next((x for x in data if str(x['ID'])==base_id),None)
    if base_original is None or base_row is None:
        raise RuntimeError('Thiếu ảnh tướng gốc '+sid[:3])
    for field in ('SkinPicID','SkinHeadCDNPath','PresentHeadImg',
                  'HeroSkinShareUrl','SettleShareUrl','WinRateShareUrl'):
        if field in base_original:base_row[field]=base_original[field]
        else:base_row.pop(field,None)
    # Separate the full lobby portrait from the native hero head portrait.
    # CDN mode reads those two distinct paths instead of the shared AB picture key.
    lobby_picture=selected.get('SkinPicCDNPath') or chosen_original.get('SkinPicCDNPath')
    if lobby_picture:
        base_row['SkinPicCDNPath']=lobby_picture
        base_row['bIsInAB']=0
        # The gallery uses its own selected skin argument now. Preserve the
        # tested native hero key while retaining the chosen animation flag.
        base_row['bSkinDynamicPath']=chosen_original.get('bSkinDynamicPath',0)
        if sid=='13118':base_row['SkinPicCDNPath']='301310.jpg'
    else:
        base_row['bIsInAB']=base_original.get('bIsInAB',1)
    # The client shares SkinPicID with pick/minimap even in CDN mode.
    # Never replace the base hero key to enable the selected lobby animation.
    for field in ('SkinPicID','SkinHeadCDNPath','PresentHeadImg'):
        if base_row.get(field)!=base_original.get(field):
            raise RuntimeError('Khóa ảnh tướng gốc bị thay đổi: '+base_id)
    Path(icon_file).write_text(json.dumps(data,ensure_ascii=False))
    return result

def ModInfos(info_id,skin_id,hd,hero,path,butter,veres):
    original=ET.parse(path).getroot()
    camera=copy.deepcopy(original.find('ArtSkinLobbyShowCamera'))
    root_tags={x.tag for x in original if x.tag!='SkinPrefab'}
    # These optional ActorInfo fields occur at ROOT in native actor files.
    # Absence in this hero's default model means default values, not an invalid field.
    root_tags.update({'useMecanim','useNewMecanim','useStateDrivenMecanim',
        'bDisableDirLight','bUnityLight','isHokSkin','hasHokCameraAnim',
        'ArtSkinLobbyNode','ArtSkinLobbyShowMovie'})
    original_skins=original.find('SkinPrefab')
    candidates=[] if original_skins is None else [el for el in original_skins if any('/'+info_id+'_' in x.get('value','') for x in el.iter())]
    # Keep legacy special handling for evolution models, but never silently use
    # an unrelated base model when the selected normal model is missing.
    if not candidates and info_id not in ('1505','13312','1678','11621'):
        raise RuntimeError('Thiếu model sảnh cho skin '+skin_id)
    legacy_infos(info_id,skin_id,hd,hero,path,butter,veres)
    tree=ET.parse(path);root=tree.getroot();skins=root.find('SkinPrefab')
    candidates=[] if skins is None else [el for el in skins if any('/'+info_id+'_' in x.get('value','') for x in el.iter())]
    if not candidates and skins is not None and info_id in ('1505','13312','1678','11621'):
        candidates=list(skins)[:1]
    if not candidates:raise RuntimeError('Không tạo được model sảnh cho skin '+skin_id)
    selected=copy.deepcopy(candidates[0])
    if info_id not in ('1505','13312','1678','11621'):
        selected=next(copy.deepcopy(el) for el in original_skins if any('/'+info_id+'_' in x.get('value','') for x in el.iter()))
    # SkinElement-only flags/movie fields do not belong in the actor root.
    for node in list(root):
        if node.tag not in root_tags and node.tag!='SkinPrefab':root.remove(node)
    rename={'ArtSkinPrefabLOD':'ArtPrefabLOD','ArtSkinPrefabLODEx':'ArtPrefabLODEx','ArtSkinLobbyShowLOD':'ArtLobbyShowLOD','ArtSkinLobbyIdleShowLOD':'ArtLobbyIdleShowLOD'}
    for child in selected:
        if child.tag=='SavedSkinId':continue
        tag=rename.get(child.tag,child.tag)
        if tag not in root_tags:continue
        existing=[x for x in root if x.tag==tag]
        where=list(root).index(existing[0]) if existing else list(root).index(skins)
        for x in existing:root.remove(x)
        node=copy.deepcopy(child);node.tag=tag;root.insert(where,node)
    # Old regex replacement duplicated camera/transform/light blocks at root.
    seen=set()
    for node in list(root):
        if node.tag in seen:root.remove(node)
        else:seen.add(node.tag)
    # A root model needs a camera even when its SkinElement uses a movie.
    if root.find('ArtSkinLobbyShowCamera') is None and camera is not None:
        root.insert(list(root).index(skins),camera)
    # Code-driven legacy clips are incompatible with this skin's new Mecanim rig.
    new=selected.find('useNewMecanim')
    code=root.find('bUseCodeAnimComponent')
    if new is not None and new.get('value','').lower()=='true' and code is not None:
        code.set('value','False')
    ET.indent(tree,space='  ')
    tree.write(path,encoding='utf-8',xml_declaration=True)
