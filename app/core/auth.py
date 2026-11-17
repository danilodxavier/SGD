"""Usuários, senhas e sessões.

- Senhas: PBKDF2-HMAC-SHA256 com sal aleatório (a senha em si nunca é gravada).
- Sessões: token aleatório entregue em cookie HttpOnly; no banco fica apenas o hash do token.
- Bloqueio: após MAX_FAILURES tentativas erradas seguidas, a conta fica bloqueada por LOCK_MINUTES.
"""
import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import get_conn
from app.core.logging import get_logger

log = get_logger("auth")

# RF-23: Gestor registra decisões e envia documentos; Consulta só consulta; Administrador faz tudo
PROFILES = {"admin": "Administrador", "gestor": "Gestor", "consulta": "Consulta"}
COOKIE_NAME = "agente_sessao"
PBKDF2_ITERATIONS = 390_000
MAX_FAILURES = 5
LOCK_MINUTES = 15
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,49}$")


class AuthError(ValueError):
    """Erro com mensagem para o usuário."""


def _now():
    return datetime.now()


def _iso(dt):
    return dt.isoformat(timespec="seconds")


# ---------------------------------------------------------------- senhas

def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(PBKDF2_ITERATIONS, base64.b64encode(salt).decode(),
                                          base64.b64encode(digest).decode())


def verify_password(password, stored):
    try:
        algorithm, iterations, salt, digest = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), base64.b64decode(salt), int(iterations))
        return hmac.compare_digest(candidate, base64.b64decode(digest))
    except (ValueError, AttributeError):
        return False


def password_problem(password, username=""):
    """Mensagem explicando por que a senha não é aceita, ou None se ela for válida."""
    if len(password) < 8:
        return "A senha deve ter pelo menos 8 caracteres."
    if not re.search(r"[A-Za-zÀ-ÿ]", password) or not re.search(r"\d", password):
        return "A senha deve conter letras e números."
    if username and password.lower() == username.lower():
        return "A senha não pode ser igual ao nome de usuário."
    return None


def normalize_username(username):
    username = (username or "").strip().lower()
    if not USERNAME_RE.match(username):
        raise AuthError("Usuário inválido: use de 3 a 50 caracteres, apenas letras minúsculas sem acento, números, "
                        "ponto, hífen ou sublinhado (ex.: maria.silva).")
    return username


# ---------------------------------------------------------------- usuários

USER_COLUMNS = ("id, username, name, profile, active, must_change_password, created_at, last_login_at, "
                "failed_attempts, locked_until")


def _public(row):
    if row is None:
        return None
    user = {k: row[k] for k in row.keys() if k != "password_hash"}
    user["active"] = bool(user["active"])
    user["must_change_password"] = bool(user["must_change_password"])
    user["profile_label"] = PROFILES.get(user["profile"], user["profile"])
    user["is_admin"] = user["profile"] == "admin"
    user["is_gestor"] = user["profile"] in ("admin", "gestor")
    return user


def count_users():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def list_users():
    with get_conn() as conn:
        return [_public(r) for r in conn.execute(f"SELECT {USER_COLUMNS} FROM users ORDER BY username")]


def get_user(user_id):
    with get_conn() as conn:
        return _public(conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone())


def get_user_by_username(username):
    with get_conn() as conn:
        return _public(conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE username = ?",
                                    ((username or "").strip().lower(),)).fetchone())


def create_user(username, name, profile, password, must_change_password=True):
    username = normalize_username(username)
    name = (name or "").strip()[:120]
    if not name:
        raise AuthError("Informe o nome completo.")
    if profile not in PROFILES:
        raise AuthError("Perfil inválido. Use Administrador ou Consulta.")
    problem = password_problem(password, username)
    if problem:
        raise AuthError(problem)
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
            raise AuthError(f"Já existe um usuário “{username}”.")
        cur = conn.execute(
            "INSERT INTO users (username, name, profile, password_hash, active, must_change_password, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (username, name, profile, hash_password(password), int(must_change_password), _iso(_now())),
        )
    log.info("Usuário criado: %s (%s)", username, profile)
    return get_user(cur.lastrowid)


def _active_admins(conn, excluding=None):
    sql = "SELECT COUNT(*) FROM users WHERE profile = 'admin' AND active = 1"
    params = ()
    if excluding is not None:
        sql += " AND id != ?"
        params = (excluding,)
    return conn.execute(sql, params).fetchone()[0]


def update_user(user_id, name=None, profile=None, active=None):
    with get_conn() as conn:
        row = conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        losing_admin = row["profile"] == "admin" and row["active"] and (
            (profile is not None and profile != "admin") or (active is not None and not active))
        if losing_admin and _active_admins(conn, excluding=user_id) == 0:
            raise AuthError("Não é possível remover o último administrador ativo.")
        if profile is not None and profile not in PROFILES:
            raise AuthError("Perfil inválido. Use Administrador ou Consulta.")
        conn.execute(
            "UPDATE users SET name = COALESCE(?, name), profile = COALESCE(?, profile), "
            "active = COALESCE(?, active) WHERE id = ?",
            ((name or "").strip()[:120] or None, profile, None if active is None else int(active), user_id),
        )
        if active is not None and not active:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    log.info("Usuário alterado: id=%s perfil=%s ativo=%s", user_id, profile, active)
    return get_user(user_id)


def set_password(user_id, password, must_change_password):
    user = get_user(user_id)
    if user is None:
        return None
    problem = password_problem(password, user["username"])
    if problem:
        raise AuthError(problem)
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash = ?, must_change_password = ?, failed_attempts = 0, "
                     "locked_until = NULL WHERE id = ?", (hash_password(password), int(must_change_password), user_id))
        if must_change_password:  # senha redefinida pelo administrador: encerra as sessões abertas
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    log.info("Senha %s: %s", "redefinida" if must_change_password else "alterada", user["username"])
    return get_user(user_id)


def unlock(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (user_id,))
    return get_user(user_id)


def change_own_password(user_id, current, new):
    with get_conn() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not verify_password(current, row["password_hash"]):
        raise AuthError("A senha atual está incorreta.")
    if current == new:
        raise AuthError("A nova senha deve ser diferente da atual.")
    return set_password(user_id, new, must_change_password=False)


# ---------------------------------------------------------------- login e sessões

def authenticate(username, password, ip=""):
    """Confere usuário e senha; devolve o usuário ou lança AuthError com mensagem genérica."""
    generic = "Usuário ou senha inválidos."
    username = (username or "").strip().lower()
    error = None
    # o erro só é lançado depois da transação: assim a contagem de tentativas erradas é gravada
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            log.warning("Login recusado: usuário inexistente “%s” (origem %s)", username[:50], ip)
            error = generic
        elif row["locked_until"] and row["locked_until"] > _iso(_now()):
            log.warning("Login recusado: conta bloqueada %s (origem %s)", username, ip)
            error = (f"Conta bloqueada temporariamente por excesso de tentativas. Tente novamente após "
                     f"{datetime.fromisoformat(row['locked_until']):%H:%M} ou peça a um administrador para "
                     "desbloqueá-la.")
        elif not verify_password(password or "", row["password_hash"]):
            failures = row["failed_attempts"] + 1
            locked = _iso(_now() + timedelta(minutes=LOCK_MINUTES)) if failures >= MAX_FAILURES else None
            conn.execute("UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                         (0 if locked else failures, locked, row["id"]))
            log.warning("Login recusado: senha incorreta para %s (origem %s, tentativa %d)%s", username, ip, failures,
                        " — conta bloqueada" if locked else "")
            error = generic
        elif not row["active"]:
            log.warning("Login recusado: usuário desativado %s (origem %s)", username, ip)
            error = "Usuário desativado. Procure um administrador do sistema."
        else:
            conn.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login_at = ? WHERE id = ?",
                         (_iso(_now()), row["id"]))
    if error:
        raise AuthError(error)
    log.info("Login: %s (origem %s)", username, ip)
    return get_user(row["id"])


def _token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id, ip=""):
    token = secrets.token_urlsafe(32)
    now = _now()
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(now),))
        conn.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at, ip) VALUES (?, ?, ?, ?, ?)",
                     (_token_hash(token), user_id, _iso(now), _iso(now + timedelta(hours=settings.session_hours)), ip))
    return token


def user_for_token(token):
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT {', '.join('u.' + c.strip() for c in USER_COLUMNS.split(','))} FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1",
            (_token_hash(token), _iso(_now())),
        ).fetchone()
    return _public(row)


def end_session(token):
    if token:
        with get_conn() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
