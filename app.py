import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
DB_PATH = DATA_DIR / "site.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion"),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    UPLOAD_FOLDER=str(UPLOAD_DIR),
)

CONTENT_TYPES = {
    "services": {"label": "Servicios", "icon": "fa-compass"},
    "announcements": {"label": "Anuncios importantes", "icon": "fa-bullhorn"},
    "promotions": {"label": "Promociones", "icon": "fa-tags"},
    "experiences": {"label": "Experiencias", "icon": "fa-sun"},
}

DEFAULT_SETTINGS = {
    "site_name": "MAYADVENTURE",
    "hero_title": "Tu aventura comienza en Playa del Carmen",
    "hero_text": "Descubre el Caribe mexicano, cruza a Cozumel y vive experiencias inolvidables.",
    "hero_image": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1900&q=85",
    "services_title": "Servicios para tu viaje",
    "services_subtitle": "Todo lo que necesitas para disfrutar el Caribe",
    "announcements_title": "Anuncios importantes",
    "announcements_subtitle": "Información útil para planear tu visita",
    "promotions_title": "Promociones especiales",
    "promotions_subtitle": "Aprovecha ofertas seleccionadas para ti",
    "experiences_title": "Experiencias inolvidables",
    "experiences_subtitle": "Vive lo mejor de la Riviera Maya",
    "contact_title": "¿Listo para vivir la aventura?",
    "contact_text": "Escríbenos y te ayudaremos a organizar una experiencia memorable.",
    "whatsapp": "529841234567",
    "email": "hola@mayadventure.mx",
    "address": "Playa del Carmen, Quintana Roo, México",
    "footer_text": "Tu conexión con lo mejor del Caribe mexicano.",
}

SEED_ITEMS = [
    ("services", "Ferries a Cozumel", "Consulta opciones de cruce y disfruta una travesía segura por el Caribe.", "/static/img/ferries.jpg", "Ver opciones", "#contacto", "", 1),
    ("services", "Tours y actividades", "Explora cenotes, parques naturales y sitios arqueológicos increíbles.", "/static/img/xcaret.png", "Descubrir", "#experiencias", "", 2),
    ("services", "Ubicación privilegiada", "Encuentra fácilmente el muelle y los principales puntos de interés.", "/static/img/terminal-segura.png", "Más información", "#contacto", "", 3),
    ("announcements", "Planea tu cruce con tiempo", "Llega con anticipación y confirma los horarios de salida durante temporada alta.", "/static/img/dock.jpg", "Más información", "#contacto", "Información", 1),
    ("announcements", "Terminal segura", "Sigue las indicaciones del personal y conserva tus pertenencias contigo.", "/static/img/terminal-segura.png", "Contáctanos", "#contacto", "Aviso", 2),
    ("promotions", "Escapada a Cozumel", "Cruce y experiencia pensados para disfrutar un día extraordinario en la isla.", "/static/img/Muelle.jpg", "Reservar", "#contacto", "Oferta especial", 1),
    ("promotions", "Aventura en la Riviera Maya", "Descubre paisajes inolvidables con una experiencia diseñada para ti.", "/static/img/mapa-cancun-playa-cozumel.png", "Solicitar información", "#contacto", "Recomendado", 2),
    ("experiences", "Sabores de Playa", "Descubre restaurantes emblemáticos y la energía de la Quinta Avenida.", "/static/img/hrcafe.jpg", "Quiero vivirla", "#contacto", "Gastronomía", 1),
    ("experiences", "Caribe sobre las olas", "Navega entre aguas turquesa y vistas espectaculares del mar Caribe.", "/static/img/Muelle.jpg", "Quiero vivirla", "#contacto", "Mar y aventura", 2),
]


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL, title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
                button_text TEXT NOT NULL DEFAULT '', link TEXT NOT NULL DEFAULT '',
                badge TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        for key, value in DEFAULT_SETTINGS.items():
            connection.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (key, value))
        if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            connection.execute(
                "INSERT INTO users(username,password_hash) VALUES (?,?)",
                (os.environ.get("ADMIN_USERNAME", "admin"),
                 generate_password_hash(os.environ.get("ADMIN_PASSWORD", "Cambiar123!"))),
            )
        if connection.execute("SELECT COUNT(*) FROM content").fetchone()[0] == 0:
            connection.executemany(
                """INSERT INTO content
                (kind,title,description,image,button_text,link,badge,position)
                VALUES (?,?,?,?,?,?,?,?)""", SEED_ITEMS
            )


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(24)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


def validate_csrf():
    if not secrets.compare_digest(session.get("_csrf", ""), request.form.get("_csrf", "")):
        abort(400, "Solicitud inválida. Actualiza la página e inténtalo de nuevo.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def settings_dict(connection):
    return {row["key"]: row["value"] for row in connection.execute("SELECT key,value FROM settings")}


def save_image(file):
    if not file or not file.filename:
        return ""
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Formato no permitido. Usa JPG, PNG, WEBP o GIF.")
    filename = f"{uuid4().hex}-{secure_filename(file.filename)}"
    file.save(UPLOAD_DIR / filename)
    return f"/static/uploads/{filename}"


@app.route("/")
def home():
    with db() as connection:
        settings = settings_dict(connection)
        sections = {
            kind: connection.execute(
                "SELECT * FROM content WHERE kind=? AND active=1 ORDER BY position,id", (kind,)
            ).fetchall() for kind in CONTENT_TYPES
        }
    return render_template("index.html", settings=settings, sections=sections)


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        validate_csrf()
        with db() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username=?", (request.form.get("username", "").strip(),)
            ).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"], session["username"] = user["id"], user["username"]
            flash("Bienvenido al panel de administración.", "success")
            return redirect(url_for("admin"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.post("/admin/logout")
@login_required
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@login_required
def admin():
    selected = request.args.get("section", "general")
    if selected not in {*CONTENT_TYPES, "general", "account"}:
        selected = "general"
    with db() as connection:
        settings = settings_dict(connection)
        items = connection.execute(
            "SELECT * FROM content WHERE kind=? ORDER BY position,id", (selected,)
        ).fetchall() if selected in CONTENT_TYPES else []
    return render_template("admin.html", settings=settings, items=items,
                           selected=selected, content_types=CONTENT_TYPES)


@app.post("/admin/settings")
@login_required
def update_settings():
    validate_csrf()
    try:
        hero_upload = save_image(request.files.get("hero_image_file"))
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin"))
    with db() as connection:
        for key in DEFAULT_SETTINGS:
            if key in request.form:
                connection.execute(
                    """INSERT INTO settings(key,value) VALUES (?,?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                    (key, request.form[key].strip()),
                )
        if hero_upload:
            connection.execute("UPDATE settings SET value=? WHERE key='hero_image'", (hero_upload,))
    flash("La información general fue actualizada.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/content/save")
@login_required
def save_content():
    validate_csrf()
    kind = request.form.get("kind", "")
    if kind not in CONTENT_TYPES:
        abort(400)
    item_id, title = request.form.get("id", "").strip(), request.form.get("title", "").strip()
    if not title:
        flash("El título es obligatorio.", "error")
        return redirect(url_for("admin", section=kind))
    try:
        uploaded = save_image(request.files.get("image_file"))
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin", section=kind))
    values = (
        title, request.form.get("description", "").strip(),
        uploaded or request.form.get("image_url", "").strip() or request.form.get("current_image", "").strip(),
        request.form.get("button_text", "").strip(), request.form.get("link", "").strip(),
        request.form.get("badge", "").strip(), request.form.get("position", "0") or 0,
        1 if request.form.get("active") else 0,
    )
    with db() as connection:
        if item_id:
            connection.execute(
                """UPDATE content SET title=?,description=?,image=?,button_text=?,link=?,
                badge=?,position=?,active=? WHERE id=? AND kind=?""", values + (item_id, kind)
            )
            message = "Elemento actualizado."
        else:
            connection.execute(
                """INSERT INTO content
                (title,description,image,button_text,link,badge,position,active,kind)
                VALUES (?,?,?,?,?,?,?,?,?)""", values + (kind,)
            )
            message = "Nuevo elemento publicado."
    flash(message, "success")
    return redirect(url_for("admin", section=kind))


@app.post("/admin/content/<int:item_id>/delete")
@login_required
def delete_content(item_id):
    validate_csrf()
    kind = request.form.get("kind", "")
    if kind not in CONTENT_TYPES:
        abort(400)
    with db() as connection:
        connection.execute("DELETE FROM content WHERE id=? AND kind=?", (item_id, kind))
    flash("Elemento eliminado.", "success")
    return redirect(url_for("admin", section=kind))


@app.post("/admin/password")
@login_required
def change_password():
    validate_csrf()
    current, new = request.form.get("current_password", ""), request.form.get("new_password", "")
    if len(new) < 8:
        flash("La nueva contraseña debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("admin", section="account"))
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if not user or not check_password_hash(user["password_hash"], current):
            flash("La contraseña actual no es correcta.", "error")
        else:
            connection.execute("UPDATE users SET password_hash=? WHERE id=?",
                               (generate_password_hash(new), session["user_id"]))
            flash("Contraseña actualizada correctamente.", "success")
    return redirect(url_for("admin", section="account"))


@app.errorhandler(413)
def too_large(_error):
    return "La imagen supera el límite de 8 MB.", 413


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
