# Processing engine copied from the uploaded bot; no Telegram connection.
from Data.Module import *
import asyncio, multiprocessing, time, random, string, re, os, shutil, zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pyzstd
from skin_extras import map_extras
from action_validation import validate_action_folder
from reset_overlay import apply_reset_overlay, verify_reset_archive
from resource_encoding import restore_resource_encoding
from resource_fixes import Icon_Bac, ModInfos, AssetRefs, FixCodeSkin
class CheckedPool(ThreadPoolExecutor):
    def __init__(self,max_workers=4,**kwargs):
        super().__init__(max_workers=min(max_workers,4),**kwargs)
    def __enter__(self):
        self.pending = []
        return super().__enter__()
    def __exit__(self, *args):
        result = super().__exit__(*args)
        if args[0] is None:
            for task in self.pending:
                task.result()
        return result

def checked_submit(pool, *args, **kwargs):
    future = pool.submit(*args, **kwargs)
    pool.pending.append(future)
    return future

def resolve_hero_folder(parent, hero):
    """Resolve native resource casing without changing the output/game path."""
    parent = Path(parent)
    exact = parent / hero
    if exact.is_dir():
        return str(exact)
    matches = [p for p in parent.iterdir() if p.is_dir() and p.name.casefold() == hero.casefold()]
    if len(matches) != 1:
        raise RuntimeError('Thiếu dữ liệu tài nguyên tướng ' + hero)
    return str(matches[0])

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
        verify_reset_archive(zf, base, version)
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
            if not NAME_HERO: raise RuntimeError(f"Thiếu dữ liệu tướng cho skin {ID_SKIN}")
            
            ResSkinExclusiveBattleEffectCfg = f"Resources_1/{Version}/Databin/Client/Huanhua/ResSkinExclusiveBattleEffectCfg.bytes"
            DK_MOD_GT, DK_MOD_BV, xyz_GIATOC, xyz_BIENVE, code_duoi_giatoc = dkgtbv(ID_SKIN, ResSkinExclusiveBattleEffectCfg)
            dieukienmod = (TimDieuKienModAges(ID_SKIN, heroSkin) or ID_SKIN[:3] in ["153", "537"] or ID_SKIN in ["53002", "54506", "17311", "59701", "11621"])

            percent = 56 + round((index + 1) / total_skins * 30)
            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, percent, context)            
                
            Files_1 = resolve_hero_folder(f'Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero', NAME_HERO) + '/'
            Files_2 = f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/{ID_SKIN}-EFX/{NAME_HERO}/'
            Files_MOD = Files_2 + "skill/"
            Files_3 = f'Resources_1/{Version}/Prefab_Characters/Prefab_Hero/{NAME_HERO}'
            Files_4 = f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/{ID_SKIN}-INFOS/Prefab_Hero/{NAME_HERO}'
    
            with CheckedPool(max_workers=9) as ex:
                checked_submit(ex, Mod_Motion, ResSkinMotionBaseCfg, ID_SKIN)
                checked_submit(ex, Sound_Databin, ID_SKIN, Sound_Files)
                checked_submit(ex, Mod_ResCharacterComponent, ResCharacterComponent, ID_SKIN)
                checked_submit(ex, Mod_Skill_Databin, ID_SKIN, ID_HD, liteBulletCfg, skillmark)
                checked_submit(ex, Add_SkillCombineId, ID_SKIN, skillcombine)
                checked_submit(ex, CopyFolder, Files_1, Files_2)
                checked_submit(ex, CopyFolder, Files_3, Files_4)
                # Preserve the global head-icon table; never clone one skin frame
                # over every unrelated icon when generating a single skin.
    
            validate_action_folder(Files_2)
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
    
            validate_action_folder(Files_2)
            Zip_Folder(f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/{ID_SKIN}-EFX', f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/Actor_{ID_SKIN[:3]}_Actions.pkg.bytes')
            Zip_Folder(f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/{ID_SKIN}-INFOS', f'{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Prefab_Characters/Actor_{ID_SKIN[:3]}_Infos.pkg.bytes')
    
            if xyz_BIENVE != 'None' and ID_SKIN not in ["13215"]: BienVe(ID_SKIN, ID_HD, NAME_HERO, ID_SKIN[:3], Back, code_bv_skill, xyz_BIENVE.encode(), phukienveres)
            if DK_MOD_GT != 'None' or ID_SKIN in ["15015", "15004", "13311"]: GiaToc(ID_SKIN, ID_HD, NAME_HERO, ID_SKIN[:3], hasteE1, HasteE1_leave, DaofengSprint, xyz_GIATOC.encode(), code_duoi_giatoc.encode())
            Function_Track_Guid(Back, hasteE1, HasteE1_leave)
            
            # Keep genuine bundle hashes and valid awakening tables.
            # The previous placeholder writes made unchanged resources invalid.
            
            return True, TEN_SKIN
        except Exception as e:
            raise RuntimeError(f"Không xử lý được skin {ID_SKIN}: {e}") from e
    
    if True:
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
            
            with CheckedPool(max_workers=16) as ex:
                checked_submit(ex, CopyFile1, src_files, dst_files)
                checked_submit(ex, CopyFolder, f"Resources_1/{Version}/Databin/Client/Sound/", f"{ctx['Sound_Files']}/")
                checked_submit(ex, CopyFolder, f"Resources_1/{Version}/Databin/Client/Huanhua/", f"{ctx['Huanhua']}/", exclude=["ResSkinExclusiveBattleEffectCfg.bytes"])
                checked_submit(ex, CopyFolder, f"Resources_1/{Version}/assetbundle/", ctx['Assetbundle'])
                checked_submit(ex, CopyFile, f"Resources_1/{Version}/Ages/Prefab_Characters/Prefab_Hero/CommonActions.pkg.bytes", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/CommonActions.pkg.bytes")
            
            with CheckedPool(max_workers=10) as ex:
                checked_submit(ex, HeroSkinJson, ctx['heroSkin'], 1)
                checked_submit(ex, HeroSkinShopJson, ctx['HeroSkinShop'], 1)
                checked_submit(ex, SeniorLabelJson, ctx['ResSkinSeniorLabelCfg'], 1)
                checked_submit(ex, LitebulletJson, ctx['liteBulletCfg'], 1)
                checked_submit(ex, SkillMarkJson, ctx['skillmark'], 1)
                checked_submit(ex, SkillCombineJson, ctx['skillcombine'], 1)
                checked_submit(ex, MotionJson, ctx['ResSkinMotionBaseCfg'], 1)
                checked_submit(ex, SoundDatabinJs, ctx['Sound_Files'], 1)
                checked_submit(ex, CharacterJson, ctx['ResCharacterComponent'], 1)
                checked_submit(ex, HeadImageJson, ctx['HeadImage'], 1)

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
            
            with CheckedPool(max_workers=16) as ex:
                xmls = [ctx['junglemark'], ctx['Back'], ctx['hasteE1'], ctx['HasteE1_leave'], ctx['DaofengSprint'], ctx['Born'], ctx['Dead_Born'], ctx['Dance'], ctx['DanceBullet']]
                for x in xmls:
                    checked_submit(ex, lambda f=x: Xml(f))
                
                conver = [(HeroSkinJson, ctx['heroSkin']), (HeroSkinShopJson, ctx['HeroSkinShop']), (SeniorLabelJson, ctx['ResSkinSeniorLabelCfg']), (LitebulletJson, ctx['liteBulletCfg']), (SkillMarkJson, ctx['skillmark']), (SkillCombineJson, ctx['skillcombine']),(MotionJson, ctx['ResSkinMotionBaseCfg']), (SoundDatabinJs, ctx['Sound_Files']), (CharacterJson, ctx['ResCharacterComponent']), (HeadImageJson, ctx['HeadImage'])]
                for func, path in conver:
                    checked_submit(ex, lambda fu=func, p=path: fu(p, 2))                  

            shutil.copy2(f"Resources_1/{Version}/StableSystems_3.pkg.bytes", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/StableSystems_3.pkg.bytes")
            shutil.copy2(f"Resources_1/{Version}/KernelLua.pkg.bytes", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/KernelLua.pkg.bytes")
            # FixReset(ctx['ResourceVerification'])
            for name in ('ResAwakenBattleEffect.bytes','ResAwakenBattleSound.bytes'):
                shutil.copy(f'Resources_1/{Version}/Databin/Client/Actor/{name}',Path(ctx['Actor'])/name)
            # lz4(ctx['Assetbundle'])
            # ReplacePath(IDMODSKIN, ctx['ResourcePacker'])
            await update_progress(message, all_tuongs_str, all_skins_str, all_ids_str, 90, context)
                            
            AddFoldersToZip(f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/CommonActions.pkg.bytes", [f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/commonresource", f"{FILES_MOD}/com.garena.game.kgvn/files/Resources/{Version}/Ages/Prefab_Characters/Prefab_Hero/PassiveResource"])

            extras=map_extras(ctx['Huanhua'], IDMODSKIN)
            print('Native cosmetic associations:',extras)
            resource_root=Path(FILES_MOD) / "com.garena.game.kgvn" / "files" / "Resources" / Version
            from web_cosmetics import apply_web_cosmetics
            cosmetic_result = apply_web_cosmetics(resource_root, Version, IDMODSKIN, context.user_data.get('cosmetics', False) is True)
            print('Selected button and kill effects:', cosmetic_result)
            restore_resource_encoding(resource_root)
            apply_reset_overlay(resource_root, Version)
            from lobby_portraits import apply_lobby_portraits
            apply_lobby_portraits(resource_root, Version, IDMODSKIN)

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
        except Exception:
            raise
