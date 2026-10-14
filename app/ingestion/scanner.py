"""Varredura recursiva do diretório documental (somente leitura)."""
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

IGNORED_NAMES = {"thumbs.db", "desktop.ini", ".ds_store"}
IGNORED_DIRS = {"$recycle.bin", "system volume information"}


@dataclass
class FileInfo:
    path: Path
    relative: str
    size: int
    mtime: float


@dataclass
class ScanResult:
    files: list = field(default_factory=list)
    directories: int = 0
    errors: list = field(default_factory=list)


def check_root(root):
    """Retorna (ok, mensagem) sobre o diretório documental."""
    path = Path(root)
    if not str(root).strip():
        return False, "Nenhum diretório documental configurado."
    if not path.exists():
        return False, f"O diretório {root} não existe."
    if not path.is_dir():
        return False, f"{root} não é um diretório."
    if not os.access(path, os.R_OK):
        return False, f"Sem permissão de leitura em {root}."
    return True, "Diretório acessível."


def _ignored(name):
    low = name.lower()
    return low in IGNORED_NAMES or name.startswith("~$") or name.startswith(".~")


def _key(path):
    return os.path.normcase(os.path.abspath(path))


def scan(root, exclude=(), exclude_files=()):
    """Varre `root`; pastas em `exclude` e arquivos em `exclude_files` (os da própria aplicação) são ignorados."""
    root = Path(root)
    excluded = {_key(p) for p in exclude}
    excluded_files = {_key(p) for p in exclude_files}
    result = ScanResult()
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: result.errors.append(str(e))):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in IGNORED_DIRS
                       and _key(os.path.join(dirpath, d)) not in excluded]
        result.directories += len(dirnames)
        for name in filenames:
            if _ignored(name) or _key(os.path.join(dirpath, name)) in excluded_files:
                continue
            path = Path(dirpath) / name
            try:
                st = path.stat()
            except OSError as exc:
                result.errors.append(f"{path}: {exc}")
                continue
            result.files.append(FileInfo(path, str(path.relative_to(root)), st.st_size, st.st_mtime))
    return result


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
