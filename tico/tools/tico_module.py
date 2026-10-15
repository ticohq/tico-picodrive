#!/usr/bin/env python3
"""Settings definition and translations for the tico module of PicoDrive.

Run after merging upstream. It builds tools/dump_core_options.c against the
core's own libretro_core_options.h, so tico/module/settings.json lists exactly
the options the libnx core reads (picodrive_* keys, values and defaults), laid
out in tabs, followed by the overlay's own display and controls options.
Labels are translation keys; the strings go into tico/lang/*.json, taken from
the LABELS and CHOICES tables below: the core translates none of tico's
languages. Choice labels stay English in settings.json;
the overlay translates them through settings_picodrive_value_* keys.

    python3 tico/tools/tico_module.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TICO = ROOT / "tico"
SETTINGS = TICO / "module/settings.json"
LANG_DIR = TICO / "lang"
LANGUAGES = ("en", "de", "es", "fr", "ja", "pt", "ru", "zh")
# tico-nx's own strings label the options it already knew; optional
TICO_NX = Path(os.environ.get("TICO_NX_DIR", ROOT.parents[1] / "tico-nx"))

# Core option -> label key. Options are named after their key without picodrive_.
LABEL_KEYS: dict[str, str] = {}

# Core options the module has no use for: it runs only the 32X (Genesis Plus
# GX has the Master System, Game Gear, SG-1000 and Sega CD), tico resamples
# whatever rate the core runs at and paces the frames itself.
EXCLUDED = {
    "picodrive_smstype", "picodrive_smsmapper", "picodrive_smstms", "picodrive_smsfm",
    "picodrive_ggghost", "picodrive_ramcart", "picodrive_sound_rate",
    "picodrive_frameskip", "picodrive_frameskip_threshold",
}

# (tab, [(section, [option keys])]). Every core option the dump lists must be
# placed or excluded; the overlay's own tabs are added around these.
LAYOUT = [
    ("settings_picodrive_tab_system", [
        ("settings_picodrive_section_system", ["picodrive_region"]),
        ("settings_picodrive_section_input", ["picodrive_input1", "picodrive_input2"]),
    ]),
    ("settings_picodrive_tab_video", [
        ("settings_picodrive_section_display", ["picodrive_aspect", "picodrive_renderer",
                                                "picodrive_sprlim"]),
    ]),
    ("settings_picodrive_tab_audio", [
        ("settings_picodrive_section_sound", ["picodrive_fmchip", "picodrive_fm_filter",
                                              "picodrive_audio_filter", "picodrive_lowpass_range"]),
    ]),
    ("settings_picodrive_tab_hacks", [
        ("settings_picodrive_section_performance", ["picodrive_drc", "picodrive_overclk68k"]),
    ]),
]

# Listed only while another option has a value, like the core's own menus.
DEPENDS_ON: dict[str, tuple[str, str]] = {
    "picodrive_lowpass_range": ("picodrive_audio_filter", "low-pass"),
}

# Switch buttons a Mega Drive button (or the fast-forward hotkey) can sit on.
SWITCH_BUTTONS = [("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y"), ("L", "L"), ("R", "R"),
                  ("ZL", "ZL"), ("ZR", "ZR"), ("Plus", "Plus"), ("Minus", "Minus"),
                  ("StickL", "Left stick"), ("StickR", "Right stick"), ("Up", "Up"),
                  ("Down", "Down"), ("Left", "Left"), ("Right", "Right"), ("None", "Disabled")]

POSITIONS = [("hidden", "Hidden"), ("top_left", "Top left"), ("top_right", "Top right"),
             ("bottom_left", "Bottom left"), ("bottom_right", "Bottom right")]

# The overlay's own options: how the game is scaled, fast forward and the HUD.
# Shaders are picked in game (Settings > Shaders): tico cannot see the presets
# on the SD card.
OVERLAY_TAB = ("settings_picodrive_tab_display", [
    ("settings_picodrive_section_screen", [
        {"key": "display_mode", "label": "settings_picodrive_display_mode", "type": "enum",
         "default": "Display", "choices": [("Integer", "Integer"), ("Display", "Display")]},
        {"key": "display_size", "label": "settings_picodrive_display_size", "type": "enum",
         "default": "4:3", "choices": [("Stretch", "Stretch"), ("4:3", "4:3"), ("16:9", "16:9"),
                                       ("Original", "Original"), ("1x", "1x"), ("2x", "2x"),
                                       ("Auto", "Auto")]},
    ]),
    ("settings_picodrive_section_fast_forward", [
        {"key": "fast_forward_speed", "label": "settings_picodrive_fast_forward_speed", "type": "enum",
         "default": "200", "choices": [("150", "150%"), ("200", "200%"), ("300", "300%"),
                                        ("400", "400%"), ("unlimited", "Unlimited")]},
        {"key": "fast_forward_mode", "label": "settings_picodrive_fast_forward_mode", "type": "enum",
         "default": "hold", "choices": [("hold", "Hold"), ("toggle", "Toggle")]},
        {"key": "fast_forward_hotkey", "label": "settings_picodrive_fast_forward_hotkey",
         "type": "enum", "default": "ZR", "choices": SWITCH_BUTTONS},
    ]),
    ("settings_picodrive_section_hud", [
        {"key": "fps_counter_position", "label": "settings_picodrive_fps_counter", "type": "enum",
         "default": "hidden", "choices": POSITIONS},
        {"key": "rendered_ir_position", "label": "settings_picodrive_rendered_resolution",
         "type": "enum", "default": "hidden", "choices": POSITIONS},
    ]),
])

# The overlay's button mapping: Mega Drive button -> Switch button, as
# tico-genesisplusgx places them (TicoMain.cpp's kButtonMappings).
CONTROLS_TAB = ("settings_picodrive_tab_controls", [
    ("settings_picodrive_section_button_mapping", [
        {"key": key, "label": "settings_picodrive_" + key, "type": "enum", "default": default,
         "choices": SWITCH_BUTTONS}
        for key, default in [
            ("map_a", "Y"), ("map_b", "B"), ("map_c", "A"), ("map_x", "L"), ("map_y", "X"),
            ("map_z", "R"), ("map_start", "Plus"), ("map_mode", "Minus"),
            ("map_up", "Up"), ("map_down", "Down"), ("map_left", "Left"), ("map_right", "Right"),
        ]
    ] + [
        {"key": "analog_dpad", "label": "settings_picodrive_analog_dpad", "type": "bool",
         "default": "enabled"},
    ]),
])

# Labels the core does not define. key -> (en, de, es, fr, ja, pt, ru, zh)
LABELS = {
    "settings_picodrive_tab_system": ("System", "System", "Sistema", "Système", "システム", "Sistema",
                                      "Система", "系统"),
    "settings_picodrive_section_system": ("System", "System", "Sistema", "Système", "システム",
                                          "Sistema", "Система", "系统"),
    "settings_picodrive_section_input": ("Controllers", "Controller", "Mandos", "Manettes",
                                         "コントローラー", "Controles", "Контроллеры", "控制器"),
    "settings_picodrive_tab_video": ("Video", "Video", "Vídeo", "Vidéo", "ビデオ", "Vídeo", "Видео",
                                     "视频"),
    "settings_picodrive_section_display": ("Display", "Anzeige", "Pantalla", "Affichage", "表示",
                                           "Exibição", "Отображение", "显示"),
    "settings_picodrive_tab_audio": ("Audio", "Audio", "Audio", "Audio", "オーディオ", "Áudio", "Звук",
                                     "音频"),
    "settings_picodrive_section_sound": ("Sound", "Ton", "Sonido", "Son", "サウンド", "Som", "Звук",
                                         "声音"),
    "settings_picodrive_tab_hacks": ("Hacks", "Hacks", "Hacks", "Hacks", "ハック", "Hacks", "Хаки",
                                     "修改"),
    "settings_picodrive_section_performance": ("Performance", "Leistung", "Rendimiento",
                                               "Performances", "パフォーマンス", "Desempenho",
                                               "Производительность", "性能"),
    "settings_picodrive_region": ("Region", "Region", "Región", "Région", "地域", "Região", "Регион",
                                  "地区"),
    "settings_picodrive_input1": ("Controller 1", "Controller 1", "Mando 1", "Manette 1",
                                  "コントローラー1", "Controle 1", "Контроллер 1", "控制器1"),
    "settings_picodrive_input2": ("Controller 2", "Controller 2", "Mando 2", "Manette 2",
                                  "コントローラー2", "Controle 2", "Контроллер 2", "控制器2"),
    "settings_picodrive_aspect": ("Aspect ratio", "Seitenverhältnis", "Relación de aspecto",
                                  "Format d'image", "アスペクト比", "Proporção", "Соотношение сторон",
                                  "宽高比"),
    "settings_picodrive_renderer": ("Renderer", "Renderer", "Renderizador", "Moteur de rendu",
                                    "レンダラー", "Renderizador", "Рендерер", "渲染器"),
    "settings_picodrive_sprlim": ("No sprite limit", "Kein Sprite-Limit", "Sin límite de sprites",
                                  "Pas de limite de sprites", "スプライト制限なし",
                                  "Sem limite de sprites", "Без лимита спрайтов", "无精灵数量限制"),
    "settings_picodrive_fmchip": ("FM chip", "FM-Chip", "Chip FM", "Puce FM", "FM音源チップ",
                                  "Chip FM", "FM-чип", "FM 芯片"),
    "settings_picodrive_fm_filter": ("FM filtering", "FM-Filterung", "Filtrado FM", "Filtrage FM",
                                     "FMフィルタリング", "Filtragem FM", "FM-фильтрация", "FM 滤波"),
    "settings_picodrive_audio_filter": ("Audio filter", "Audiofilter", "Filtro de audio",
                                        "Filtre audio", "オーディオフィルター", "Filtro de áudio",
                                        "Аудиофильтр", "音频滤波器"),
    "settings_picodrive_lowpass_range": ("Low-pass filter %", "Tiefpassfilter %",
                                         "Filtro de paso bajo %", "Filtre passe-bas %",
                                         "ローパスフィルター %", "Filtro passa-baixa %",
                                         "Фильтр НЧ %", "低通滤波 %"),
    "settings_picodrive_drc": ("Dynamic recompiler", "Dynamischer Recompiler",
                               "Recompilador dinámico", "Recompilateur dynamique",
                               "動的リコンパイラ", "Recompilador dinâmico",
                               "Динамический рекомпилятор", "动态重编译器"),
    "settings_picodrive_overclk68k": ("68K overclock", "68K-Übertaktung", "Overclock del 68K",
                                      "Overclock du 68K", "68Kオーバークロック", "Overclock do 68K",
                                      "Разгон 68K", "68K 超频"),
    "settings_picodrive_tab_display": ("Display", "Anzeige", "Pantalla", "Affichage", "表示", "Tela",
                                       "Экран", "显示"),
    "settings_picodrive_section_screen": ("Screen", "Bild", "Imagen", "Image", "画面", "Imagem",
                                          "Изображение", "画面"),
    "settings_picodrive_section_hud": ("On-screen info", "Bildschirmanzeige",
                                       "Información en pantalla", "Affichage à l'écran", "画面表示",
                                       "Informações na tela", "Экранная информация", "屏幕信息"),
    "settings_picodrive_display_mode": ("Display Mode", "Anzeigemodus", "Modo de pantalla",
                                        "Mode d'affichage", "表示モード", "Modo de exibição",
                                        "Режим отображения", "显示模式"),
    "settings_picodrive_display_size": ("Size", "Größe", "Tamaño", "Taille", "サイズ", "Tamanho",
                                        "Размер", "尺寸"),
    "settings_picodrive_fps_counter": ("FPS counter", "FPS-Zähler", "Contador de FPS",
                                       "Compteur de FPS", "FPSカウンター", "Contador de FPS",
                                       "Счётчик FPS", "帧率计数器"),
    "settings_picodrive_rendered_resolution": ("Rendered resolution", "Gerenderte Auflösung",
                                               "Resolución renderizada", "Résolution de rendu",
                                               "描画解像度", "Resolução renderizada",
                                               "Разрешение рендеринга", "渲染分辨率"),
    "settings_picodrive_section_fast_forward": ("Fast Forward", "Vorspulen", "Avance rápido",
                                                "Avance rapide", "早送り", "Avanço rápido",
                                                "Перемотка", "快进"),
    "settings_picodrive_fast_forward_speed": ("Fast forward speed", "Vorspul-Geschwindigkeit",
                                              "Velocidad de avance rápido",
                                              "Vitesse d'avance rapide", "早送りの速度",
                                              "Velocidade do avanço rápido", "Скорость перемотки",
                                              "快进速度"),
    "settings_picodrive_fast_forward_mode": ("Fast forward mode", "Vorspul-Modus",
                                             "Modo de avance rápido", "Mode d'avance rapide",
                                             "早送りモード", "Modo do avanço rápido",
                                             "Режим перемотки", "快进模式"),
    "settings_picodrive_fast_forward_hotkey": ("Fast forward button", "Vorspul-Taste",
                                               "Botón de avance rápido", "Bouton d'avance rapide",
                                               "早送りボタン", "Botão do avanço rápido",
                                               "Кнопка перемотки", "快进按键"),
    "settings_picodrive_tab_controls": ("Controls", "Steuerung", "Controles", "Commandes", "操作",
                                        "Controles", "Управление", "控制"),
    "settings_picodrive_section_button_mapping": ("Button mapping", "Tastenbelegung",
                                                  "Asignación de botones",
                                                  "Attribution des boutons", "ボタン割り当て",
                                                  "Mapeamento de botões", "Назначение кнопок",
                                                  "按键映射"),
    "settings_picodrive_map_a": ("A",) * 8,
    "settings_picodrive_map_b": ("B",) * 8,
    "settings_picodrive_map_c": ("C",) * 8,
    "settings_picodrive_map_x": ("X",) * 8,
    "settings_picodrive_map_y": ("Y",) * 8,
    "settings_picodrive_map_z": ("Z",) * 8,
    "settings_picodrive_map_start": ("Start", "Start", "Start", "Start", "スタート", "Start",
                                     "Start", "开始"),
    "settings_picodrive_map_mode": ("Mode", "Mode", "Mode", "Mode", "モード", "Mode", "Mode", "模式"),
    "settings_picodrive_map_up": ("D-Pad Up", "Steuerkreuz oben", "Cruceta arriba", "Croix haut",
                                  "十字キー上", "Direcional para cima", "Крестовина вверх",
                                  "方向键上"),
    "settings_picodrive_map_down": ("D-Pad Down", "Steuerkreuz unten", "Cruceta abajo", "Croix bas",
                                    "十字キー下", "Direcional para baixo", "Крестовина вниз",
                                    "方向键下"),
    "settings_picodrive_map_left": ("D-Pad Left", "Steuerkreuz links", "Cruceta izquierda",
                                    "Croix gauche", "十字キー左", "Direcional para a esquerda",
                                    "Крестовина влево", "方向键左"),
    "settings_picodrive_map_right": ("D-Pad Right", "Steuerkreuz rechts", "Cruceta derecha",
                                     "Croix droite", "十字キー右", "Direcional para a direita",
                                     "Крестовина вправо", "方向键右"),
    "settings_picodrive_analog_dpad": ("Left stick as D-Pad", "Linker Stick als Steuerkreuz",
                                       "Stick izquierdo como cruceta",
                                       "Stick gauche comme croix directionnelle",
                                       "左スティックを十字キーとして使う",
                                       "Analógico esquerdo como direcional",
                                       "Левый стик как крестовина", "左摇杆作为方向键"),
}

# Choice labels the core does not translate. English -> (de, es, fr, ja, pt, ru, zh)
CHOICES = {
    "Japan NTSC": ("Japan NTSC", "Japón NTSC", "Japon NTSC", "日本 NTSC", "Japão NTSC", "Япония NTSC",
                   "日本 NTSC"),
    "Japan PAL": ("Japan PAL", "Japón PAL", "Japon PAL", "日本 PAL", "Japão PAL", "Япония PAL",
                  "日本 PAL"),
    "US": ("USA", "EE. UU.", "États-Unis", "北米", "EUA", "США", "美国"),
    "Europe": ("Europa", "Europa", "Europe", "欧州", "Europa", "Европа", "欧洲"),
    "3 Button Pad": ("3-Tasten-Pad", "Mando de 3 botones", "Manette 3 boutons", "3ボタンパッド",
                     "Controle de 3 botões", "3-кнопочный геймпад", "3 键手柄"),
    "6 Button Pad": ("6-Tasten-Pad", "Mando de 6 botones", "Manette 6 boutons", "6ボタンパッド",
                     "Controle de 6 botões", "6-кнопочный геймпад", "6 键手柄"),
    "Sega 4 Player Adaptor": ("Sega 4-Spieler-Adapter", "Adaptador Sega de 4 jugadores",
                              "Adaptateur Sega 4 joueurs", "セガ4人用アダプター",
                              "Adaptador Sega de 4 jogadores", "Адаптер Sega на 4 игрока",
                              "世嘉四人适配器"),
    "EA 4way Play Adaptor": ("EA 4way Play Adapter", "Adaptador EA 4way Play",
                             "Adaptateur EA 4way Play", "EA 4way Play アダプター",
                             "Adaptador EA 4way Play", "Адаптер EA 4way Play", "EA 4way Play 适配器"),
    "None": ("Keiner", "Ninguno", "Aucun", "なし", "Nenhum", "Нет", "无"),
    "Accurate": ("Genau", "Preciso", "Précis", "正確", "Preciso", "Точный", "精确"),
    "Good": ("Gut", "Bueno", "Bon", "良好", "Bom", "Хороший", "良好"),
    "Fast": ("Schnell", "Rápido", "Rapide", "高速", "Rápido", "Быстрый", "快速"),
    "Low-Pass": ("Tiefpass", "Paso bajo", "Passe-bas", "ローパス", "Passa-baixa", "НЧ", "低通"),
    "Disabled": ("Deaktiviert", "Desactivado", "Désactivé", "無効", "Desativado", "Выключено",
                 "禁用"),
    "Enabled": ("Aktiviert", "Activado", "Activé", "有効", "Ativado", "Включено", "启用"),
    "Integer": ("Ganzzahlig", "Entero", "Entier", "整数倍", "Inteiro", "Целочисленный", "整数"),
    "Display": ("Anzeige", "Pantalla", "Écran", "画面", "Tela", "Экран", "屏幕"),
    "Stretch": ("Strecken", "Estirar", "Étirer", "引き伸ばし", "Esticar", "Растянуть", "拉伸"),
    "Original": ("Original", "Original", "Original", "オリジナル", "Original", "Оригинал", "原始"),
    "Auto": ("Auto", "Auto", "Auto", "自動", "Auto", "Авто", "自动"),
    "Unlimited": ("Unbegrenzt", "Ilimitado", "Illimité", "無制限", "Ilimitado", "Без ограничений",
                  "无限制"),
    "Hold": ("Halten", "Mantener", "Maintenir", "長押し", "Segurar", "Удерживать", "按住"),
    "Toggle": ("Umschalten", "Alternar", "Basculer", "切り替え", "Alternar", "Переключать", "切换"),
    "Right stick": ("Rechter Stick", "Stick derecho", "Stick droit", "右スティック", "Analógico direito",
                    "Правый стик", "右摇杆"),
    "Left stick": ("Linker Stick", "Stick izquierdo", "Stick gauche", "左スティック", "Analógico esquerdo",
                   "Левый стик", "左摇杆"),
    "Plus": ("Plus", "Más", "Plus", "プラス", "Mais", "Плюс", "加号"),
    "Minus": ("Minus", "Menos", "Moins", "マイナス", "Menos", "Минус", "减号"),
    "Up": ("Oben", "Arriba", "Haut", "上", "Cima", "Вверх", "上"),
    "Down": ("Unten", "Abajo", "Bas", "下", "Baixo", "Вниз", "下"),
    "Left": ("Links", "Izquierda", "Gauche", "左", "Esquerda", "Влево", "左"),
    "Right": ("Rechts", "Derecha", "Droite", "右", "Direita", "Вправо", "右"),
    "Hidden": ("Ausgeblendet", "Oculto", "Masqué", "非表示", "Oculto", "Скрыто", "隐藏"),
    "Top left": ("Oben links", "Arriba a la izquierda", "En haut à gauche", "左上",
                 "Superior esquerdo", "Сверху слева", "左上"),
    "Top right": ("Oben rechts", "Arriba a la derecha", "En haut à droite", "右上",
                  "Superior direito", "Сверху справа", "右上"),
    "Bottom left": ("Unten links", "Abajo a la izquierda", "En bas à gauche", "左下",
                    "Inferior esquerdo", "Снизу слева", "左下"),
    "Bottom right": ("Unten rechts", "Abajo a la derecha", "En bas à droite", "右下",
                     "Inferior direito", "Снизу справа", "右下"),
}

RESTART_SUFFIX = re.compile(r"\s*\((Restart Required|Restart|Reload Core|[^)]*[Nn]eustart[^)]*|[^)]*[Rr]einici[^)]*|"
                            r"[^)]*[Rr]edémarr[^)]*|[^)]*再起動[^)]*|[^)]*перезапуск[^)]*|"
                            r"[^)]*重启[^)]*|[^)]*[Rr]einicializa[^)]*)\)")


def value_key(label: str) -> str:
    """tico_config.cpp's ValueKey: settings_picodrive_value_ + label as a slug."""
    return "settings_picodrive_value_" + "_".join(re.findall(r"[a-z0-9]+", label.lower()))


def clean_label(text: str) -> str:
    return RESTART_SUFFIX.sub("", text).lstrip("> ").strip()


def english_choice(value: str, label: str) -> str:
    # the core leaves on/off style values unlabelled, or labels them in lower case
    return label.capitalize() if label in ("disabled", "enabled") else label


def dump_options() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "dump_core_options"
        # the libnx build has the SH-2 dynarec (DRC_SH2), and its option
        subprocess.run(["cc", "-std=gnu11", "-w", "-DDRC_SH2",
                        "-I", str(ROOT / "platform/libretro"),
                        "-I", str(ROOT / "platform/libretro/libretro-common/include"),
                        "-o", str(exe), str(Path(__file__).with_name("dump_core_options.c"))],
                       check=True)
        return json.loads(subprocess.run([str(exe)], check=True, capture_output=True,
                                         text=True).stdout)


def label_key(key: str) -> str:
    return LABEL_KEYS.get(key, "settings_picodrive_" + key.removeprefix("picodrive_"))


def build_settings(dump: dict) -> dict:
    core = {o["key"]: o for o in dump["en"]}
    placed = {key for _, sections in LAYOUT for _, keys in sections for key in keys}
    missing = sorted(set(core) - placed - EXCLUDED)
    if missing:
        raise SystemExit(f"core options not placed in LAYOUT: {missing}")

    tabs = []
    for tab, sections in LAYOUT:
        out_sections = []
        for title, keys in sections:
            options = []
            for key in keys:
                source = core[key]
                values = [v for v, _ in source["values"]]
                option = {"key": key, "label": label_key(key)}
                # a default the core does not list ("off" for the FM chip) is
                # its first choice, as the core treats it
                default = source["default"] if source["default"] in values else values[0]
                if sorted(values) == ["disabled", "enabled"]:
                    option.update(type="bool", default=default)
                else:
                    option.update(type="enum", default=default, choices=[
                        {"label": english_choice(v, l), "value": v} for v, l in source["values"]])
                if RESTART_SUFFIX.search(source["desc"]):
                    option["restart"] = True
                if key in DEPENDS_ON:
                    on, value = DEPENDS_ON[key]
                    option["depends_on"] = {"key": on, "value": value}
                options.append(option)
            out_sections.append({"title": title, "options": options})
        tabs.append({"name": tab, "sections": out_sections})

    def overlay_tab(definition):
        tab, sections = definition
        return {"name": tab, "sections": [
            {"title": title, "options": [
                {**o, "choices": [{"label": l, "value": v} for v, l in o["choices"]]}
                if "choices" in o else dict(o)
                for o in options]}
            for title, options in sections]}

    tabs.insert(1, overlay_tab(OVERLAY_TAB))
    tabs.append(overlay_tab(CONTROLS_TAB))

    return {
        "core_id": "picodrive",
        "display_name": "PicoDrive",
        "config_file": "picodrive.jsonc",
        "slugs": ["sega-32x"],
        "bool_true_value": "enabled",
        "bool_false_value": "disabled",
        "tabs": tabs,
    }


def tico_owned(key: str) -> bool:
    """Labels tico itself defines, whose wording tico keeps."""
    return key in LABEL_KEYS.values() or key.startswith(("settings_picodrive_tab_",
                                                          "settings_picodrive_section_"))


def build_strings(dump: dict, settings: dict,
                  existing: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    strings: dict[str, dict[str, str]] = {lang: {} for lang in LANGUAGES}
    english = {o["key"]: o for o in dump["en"]}
    for lang in LANGUAGES:
        out = strings[lang]
        index = LANGUAGES.index(lang)
        for option in dump[lang]:
            if option["key"] in EXCLUDED or option["key"] not in english:
                continue
            key, en = option["key"], english[option["key"]]
            out[label_key(key)] = clean_label(option["desc"])
            # by value: a translation may list the choices differently
            en_labels = dict(en["values"])
            for value, label in option["values"]:
                if label is None or value not in en_labels:
                    continue
                en_text = english_choice(value, en_labels[value])
                if label != en_labels[value]:
                    out[value_key(en_text)] = label
        for key, texts in LABELS.items():
            out[key] = texts[index]
        if lang != "en":
            for choice, translations in CHOICES.items():
                out[value_key(choice)] = translations[index - 1]
        if lang == "en":
            for key in list(out):
                if key.startswith("settings_picodrive_value_"):
                    del out[key]
    # tico's own labels keep tico's wording: from tico-nx when it is checked
    # out, otherwise as the language files already have them
    for lang in LANGUAGES:
        path = TICO_NX / "assets/lang" / f"{lang}.json"
        source = json.loads(path.read_text()) if path.exists() else existing[lang]
        for key, value in source.items():
            if tico_owned(key):
                strings[lang][key] = value
    used = set()

    def walk(node):
        if isinstance(node, dict):
            for field in ("label", "name", "title"):
                if isinstance(node.get(field), str) and node[field].startswith("settings_"):
                    used.add(node[field])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(settings)
    unlabelled = sorted(used - set(strings["en"]))
    if unlabelled:
        raise SystemExit(f"labels without English text: {unlabelled}")
    return strings


def main() -> None:
    dump = dump_options()
    settings = build_settings(dump)
    SETTINGS.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    current_files = {lang: json.loads((LANG_DIR / f"{lang}.json").read_text())
                     if (LANG_DIR / f"{lang}.json").exists() else {} for lang in LANGUAGES}
    for lang, strings in build_strings(dump, settings, current_files).items():
        path = LANG_DIR / f"{lang}.json"
        current = {k: v for k, v in current_files[lang].items()
                   if not k.startswith("settings_picodrive_")}
        current.update(dict(sorted(strings.items())))
        path.write_text(json.dumps(current, indent=4, ensure_ascii=False) + "\n")
    print(f"wrote {SETTINGS.relative_to(ROOT)} and {len(LANGUAGES)} language files")


if __name__ == "__main__":
    main()
