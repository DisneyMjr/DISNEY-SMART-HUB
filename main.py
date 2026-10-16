"""DISNEY-SMART-HUB: storefront and installer for the user's GitHub Releases."""
from __future__ import annotations
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QProgressBar, QMessageBox, QLineEdit)

APP_NAME = "DISNEY-SMART-HUB"
IS_WINDOWS = sys.platform == "win32"
USER_AGENT = "DisneySmartHub/0.3 (GitHub Releases installer)"


def bundled(name):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return root / name


def app_data():
    if IS_WINDOWS:
        base = Path(os.getenv('LOCALAPPDATA') or (Path.home() / 'AppData/Local'))
    else:
        base = Path(os.getenv('XDG_DATA_HOME') or (Path.home() / '.local/share'))
    path = base / 'DisneySmartHub'
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_read():
    p = app_data() / 'state.json'
    try: return json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError): return {}


def state_write(obj):
    dest = app_data() / 'state.json'
    tmp = dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(dest)


def github_release(repo):
    url = f'https://api.github.com/repos/{repo}/releases/latest'
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.load(response)
    assets = data.get('assets', [])
    if IS_WINDOWS:
        candidates = [x for x in assets if x['name'].lower().endswith('.msi') and 'arm64' not in x['name'].lower()]
    else:
        candidates = [x for x in assets if x['name'].lower().endswith('.appimage') and 'aarch64' not in x['name'].lower() and 'arm64' not in x['name'].lower()]
    candidates.sort(key=lambda a: ('x64' not in a['name'].lower() and 'x86_64' not in a['name'].lower(), len(a['name'])))
    return data, (candidates[0] if candidates else None)


def download_file(url, dest, progress):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as response, dest.open('wb') as output:
        total = int(response.headers.get('Content-Length') or '0')
        done = 0
        while True:
            block = response.read(1024 * 256)
            if not block: break
            output.write(block)
            done += len(block)
            if total: progress.emit(min(100, int(done * 100 / total)))


def valid_executable_path(path):
    try:
        p = Path(path).expanduser().resolve()
        return p.is_file() and p.suffix.lower() in (['.exe'] if IS_WINDOWS else ['.appimage'])
    except (ValueError, OSError): return False


def detect_executable(app):
    state = state_read().get(app['id'], {})
    local = state.get('executable', '')
    if valid_executable_path(local): return local
    if IS_WINDOWS:
        roots = [Path(os.getenv('LOCALAPPDATA') or Path.home()), Path(os.getenv('PROGRAMFILES') or 'C:/Program Files'),
                 Path(os.getenv('PROGRAMFILES(X86)') or 'C:/Program Files (x86)')]
        folders = [app['name'], app['name'].replace(' ', ''), app['id'], app['exe'][-1].replace('.exe', '')]
        for base in roots:
            for folder in folders:
                for executable in app['exe']:
                    for loc in (base / folder / executable, base / 'Programs' / folder / executable):
                        if loc.is_file(): return str(loc)
    return None


class Worker(QObject):
    progress = Signal(int)
    finished = Signal(str, str, str)  # action, version, detail
    error = Signal(str)

    def __init__(self, app, action):
        super().__init__()
        self.app, self.action = app, action

    def run(self):
        try:
            info, asset = github_release(self.app['repo'])
            version = info.get('tag_name', 'versão indisponível')
            if self.action == 'check':
                self.finished.emit('check', version, str(bool(asset)))
                return
            if not asset:
                raise RuntimeError('A Release mais recente não contém um MSI x64' if IS_WINDOWS else 'A Release mais recente não contém uma AppImage x64')
            url = asset['browser_download_url']
            if not url.startswith('https://github.com/' + self.app['repo'] + '/releases/download/'):
                raise RuntimeError('URL inesperada do instalador; operação cancelada.')
            clean_name = Path(asset['name']).name
            if clean_name != asset['name'] or not re.fullmatch(r'[A-Za-z0-9._+() -]+', clean_name):
                raise RuntimeError('Nome de arquivo inesperado na Release.')
            store = app_data() / 'downloads' / self.app['id']
            store.mkdir(parents=True, exist_ok=True)
            dest = store / clean_name
            partial = dest.with_suffix(dest.suffix + '.part')
            try:
                download_file(url, partial, self.progress)
                partial.replace(dest)
            finally:
                partial.unlink(missing_ok=True)
            if IS_WINDOWS:
                self.finished.emit('installer', version, str(dest))
            else:
                appimage = app_data() / 'programs' / self.app['id'] / clean_name
                appimage.parent.mkdir(parents=True, exist_ok=True)
                os.replace(dest, appimage)
                appimage.chmod(0o755)
                state = state_read()
                state[self.app['id']] = {'version':version, 'executable':str(appimage)}
                state_write(state)
                self.finished.emit('installed', version, str(appimage))
        except urllib.error.HTTPError as e:
            detail = ('Nenhuma Release pública encontrada (404). Publique uma Release antes de instalar.' if e.code == 404 else f'GitHub respondeu HTTP {e.code}.')
            self.error.emit(detail)
        except Exception as exc:
            self.error.emit(str(exc))


class Tile(QFrame):
    def __init__(self, app, controller):
        super().__init__()
        self.app, self.controller = app, controller
        self.setObjectName('tile')
        self.setFixedHeight(132)
        main = QHBoxLayout(self)
        main.setContentsMargins(22, 16, 22, 16)
        main.setSpacing(17)
        icon = QLabel(app['tag']); icon.setAlignment(Qt.AlignCenter); icon.setFixedSize(72, 72)
        icon.setStyleSheet(f'background:{app["color"]};border-radius:17px;color:#fff;font-size:36px;font-weight:800;')
        main.addWidget(icon)
        details = QVBoxLayout(); details.setSpacing(7)
        title = QLabel(app['name']); title.setObjectName('appTitle')
        subtitle = QLabel(app['subtitle']); subtitle.setObjectName('sub')
        self.status = QLabel(''); self.status.setObjectName('status')
        details.addWidget(title); details.addWidget(subtitle); details.addWidget(self.status)
        main.addLayout(details, 1)
        right = QVBoxLayout(); right.setAlignment(Qt.AlignCenter)
        self.button = QPushButton(); self.button.setObjectName('primary')
        self.button.setFixedWidth(134)
        self.button.clicked.connect(lambda: self.controller.main_click(self.app))
        self.progress = QProgressBar(); self.progress.setFixedWidth(134); self.progress.setFixedHeight(5)
        self.progress.setTextVisible(False); self.progress.hide()
        self.check = QPushButton('Verificar versão'); self.check.setObjectName('textbtn')
        self.check.clicked.connect(lambda: self.controller.start(self.app, 'check'))
        right.addWidget(self.button); right.addWidget(self.progress); right.addWidget(self.check)
        main.addLayout(right)
        self.refresh()

    def refresh(self):
        current = detect_executable(self.app)
        data = state_read().get(self.app['id'], {})
        self.button.setText('Abrir' if current else 'Instalar')
        if current:
            self.status.setText(f"Instalado  •  {data.get('version', 'versão não identificada')}")
        else:
            self.status.setText('Disponível via GitHub Releases')


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DISNEY-SMART-HUB | Seus aplicativos criativos')
        self.setMinimumSize(880, 650)
        self.resize(1020, 790)
        self.apps = json.loads(bundled('apps.json').read_text(encoding='utf-8'))
        self.threads = []
        root = QWidget(); self.setCentralWidget(root)
        root.setObjectName('root')
        outer = QVBoxLayout(root); outer.setContentsMargins(36, 30, 36, 22); outer.setSpacing(18)
        header = QHBoxLayout()
        symbol = QLabel('D'); symbol.setObjectName('symbol'); symbol.setFixedSize(47,47); symbol.setAlignment(Qt.AlignCenter)
        header.addWidget(symbol)
        brand = QVBoxLayout(); brand.setSpacing(0)
        a = QLabel('DISNEY-SMART-HUB'); a.setObjectName('brand')
        b = QLabel('Sua central criativa'); b.setObjectName('sub')
        brand.addWidget(a); brand.addWidget(b); header.addLayout(brand)
        header.addStretch()
        website = QPushButton('Siga @disneymkt no Instagram  ↗'); website.setObjectName('textbtn')
        website.clicked.connect(lambda: webbrowser.open('https://instagram.com/disneymkt'))
        header.addWidget(website)
        outer.addLayout(header)
        hero = QFrame(); hero.setObjectName('hero')
        hero_layout = QVBoxLayout(hero); hero_layout.setContentsMargins(24,23,24,23)
        hero_layout.addWidget(self.make_label('Crie sem limites.', 'heroTitle'))
        hero_layout.addWidget(self.make_label('Instale, abra e encontre novas versões dos seus aplicativos em um só lugar.', 'heroDesc'))
        instagram = QPushButton('Siga @disneymkt no Instagram  ↗')
        instagram.setObjectName('textbtn')
        instagram.clicked.connect(lambda: webbrowser.open('https://instagram.com/disneymkt'))
        hero_layout.addWidget(instagram)
        outer.addWidget(hero)
        navbar = QHBoxLayout()
        navbar.addWidget(self.make_label('Aplicativos', 'sectionTitle'))
        navbar.addStretch()
        self.search = QLineEdit(); self.search.setPlaceholderText('Buscar aplicativo...')
        self.search.setFixedWidth(225)
        self.search.textChanged.connect(self.filter_tiles)
        navbar.addWidget(self.search)
        outer.addLayout(navbar)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.NoFrame)
        wrap = QWidget(); layout = QVBoxLayout(wrap); layout.setContentsMargins(0, 0, 8, 0); layout.setSpacing(12)
        self.tiles = {}
        for app in self.apps:
            tile = Tile(app, self); layout.addWidget(tile); self.tiles[app['id']] = tile
        layout.addStretch()
        sc.setWidget(wrap)
        outer.addWidget(sc, 1)
        foot = QLabel('Os instaladores são baixados das Releases oficiais dos repositórios configurados. Verifique a origem antes de instalar.')
        foot.setObjectName('foot'); foot.setWordWrap(True); outer.addWidget(foot)
        self.setStyleSheet(STYLE)

    @staticmethod
    def make_label(s, name):
        label = QLabel(s); label.setObjectName(name); return label

    def filter_tiles(self, search):
        for app in self.apps:
            self.tiles[app['id']].setVisible(search.casefold() in (app['name']+' '+app['subtitle']).casefold())

    def main_click(self, app):
        path = detect_executable(app)
        if path:
            try: subprocess.Popen([path], close_fds=True)
            except OSError as e: QMessageBox.warning(self, 'Não foi possível abrir', str(e))
        else: self.start(app, 'install')

    def start(self, app, action):
        tile = self.tiles[app['id']]
        tile.button.setEnabled(False); tile.check.setEnabled(False)
        tile.progress.show(); tile.progress.setValue(0)
        tile.status.setText('Consultando GitHub...' if action == 'check' else 'Baixando instalador...')
        thread = QThread(self); worker = Worker(app, action)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(tile.progress.setValue)
        worker.error.connect(lambda message, a=app: self.on_error(a, message))
        worker.finished.connect(lambda result, version, detail, a=app: self.on_done(a, result, version, detail))
        worker.error.connect(thread.quit); worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater); thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda t=thread: self.threads.remove(t) if t in self.threads else None)
        self.threads.append(thread); thread.start()

    def reset_tile(self, app):
        tile = self.tiles[app['id']]
        tile.button.setEnabled(True); tile.check.setEnabled(True); tile.progress.hide(); tile.refresh()

    def on_error(self, app, message):
        self.reset_tile(app)
        QMessageBox.warning(self, app['name'], message)

    def on_done(self, app, action, version, detail):
        self.reset_tile(app)
        if action == 'check':
            installed = state_read().get(app['id'], {}).get('version')
            note = 'Instalador disponível.' if detail == 'True' else 'Nenhum instalador compatível nesta Release.'
            if installed: note += f'\nVersão registrada neste computador: {installed}.'
            QMessageBox.information(self, app['name'], f'Última Release: {version}\n{note}')
        elif action == 'installer':
            result = QMessageBox.question(self, app['name'],
              f'Instalador baixado:\n{detail}\n\nDeseja abrir o instalador MSI agora?\nVerifique o editor e a assinatura digital antes de autorizar.',
              QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if result == QMessageBox.Yes:
                try:
                    # Never run downloaded MSI elevated or silently from the launcher.
                    subprocess.Popen(['msiexec.exe','/i', detail], close_fds=True)
                except OSError as e:
                    QMessageBox.warning(self, 'Instalação', str(e))
        elif action == 'installed':
            QMessageBox.information(self, app['name'], f'AppImage instalada em:\n{detail}\nVersão: {version}')
            self.tiles[app['id']].refresh()


STYLE = '''
QWidget#root {background:#0d111b;color:#edf0f8;font-family:"Segoe UI",Arial;font-size:13px;}
QLabel {color:#eef1f8;}
QLabel#symbol {background:#6256f5;border-radius:14px;font-size:28px;font-weight:bold;}
QLabel#brand {font-size:19px;font-weight:900;letter-spacing:2px;}
QLabel#sub,QLabel#heroDesc,QLabel#foot,QLabel#status {color:#9ca6bc;}
QLabel#foot {font-size:11px;}
QFrame#hero {background:#1a2241;border:1px solid #303c6b;border-radius:18px;}
QLabel#heroTitle {font-size:29px;font-weight:850;}
QLabel#heroDesc {font-size:14px;}
QLabel#sectionTitle {font-size:20px;font-weight:700;}
QFrame#tile {background:#171e2d;border:1px solid #273249;border-radius:17px;}
QLabel#appTitle {font-size:18px;font-weight:750;}
QLabel#status {font-size:11px;}
QPushButton {border:0;border-radius:9px;padding:9px 14px;color:#edf0f8;}
QPushButton#primary {background:#6256f5;font-weight:700;}
QPushButton#primary:hover {background:#7b70ff;}
QPushButton#primary:disabled {background:#3c3a70;color:#989bb4;}
QPushButton#textbtn {background:transparent;color:#aab5cb;}
QPushButton#textbtn:hover {color:white;background:#262f45;}
QProgressBar {background:#2f3446;border:0;border-radius:2px;}
QProgressBar::chunk {background:#7d75ff;border-radius:2px;}
QLineEdit {background:#192236;border:1px solid #323d55;border-radius:9px;color:white;padding:10px;}
QScrollArea {border:0;background:transparent;}
QScrollArea > QWidget > QWidget {background:transparent;}
'''

if __name__ == '__main__':
    app = QApplication(sys.argv)
    icon_path = bundled("favicon.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    win = Window(); win.show()
    sys.exit(app.exec())
