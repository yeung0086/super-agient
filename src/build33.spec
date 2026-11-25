# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 6.x spec for Super-Agient v3.3.0（开发者：yang）。

在 v3.1.0 基础上：
  - 新增 filehub.py（本地文件上传与 PDF/Office/网页/文本解析）
  - 新增 skillhub.py（内置技能总线：22 个技能，含 PDF 转换、格式互转、指定路径保存）
  - 新增 task_engine.py（模型任务指令协议 + 本地执行器，混合省 token）
  - office_skills.py 增加 saveTo 指定路径、不覆盖、URL/UNC 拒绝
  - 前端目录 webdist33/；主脚本 launcher33.py；APP_VERSION = 3.3.0
  - APP_NAME 仍为 "AI.Super-Agent"，保持数据目录与既有配置兼容
  - 应用图标 assets/robot.ico（本地生成，无外部资源）
"""
import os
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

HERE = os.path.dirname(os.path.abspath(SPEC))

hiddenimports = []
for _mod in ('docx', 'openpyxl', 'pptx', 'PyPDF2', 'PIL', 'lxml', 'webview', 'proxy_tools'):
    try:
        hiddenimports += collect_submodules(_mod)
    except Exception:
        pass
hiddenimports += [
    'mcp_stdio',
    'v3_core',
    'docgen',
    'office_skills',
    'filehub',
    'skillhub',
    'task_engine',
    'agent_framework',
    'xml.etree.ElementTree',
    'xml.dom',
    'xml.parsers.expat',
    'ctypes',
    'ctypes.wintypes',
]

datas = []
for _dist in ('python-docx', 'openpyxl', 'python-pptx', 'PyPDF2', 'lxml'):
    try:
        datas += copy_metadata(_dist)
    except Exception:
        pass

webdist_path = os.path.join(HERE, 'webdist33')
datas += [(webdist_path, 'webdist33')]

a = Analysis(
    ['launcher33.py'],
    pathex=[HERE],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc', 'doctest', 'difflib'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Super-Agient-3.3.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(HERE, 'assets', 'robot.ico'),
)
