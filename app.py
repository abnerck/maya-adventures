import os
import secrets
import sqlite3
from functools import wraps
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
from PIL import Image, ImageOps, UnidentifiedImageError

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("MAYA_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.environ.get("MAYA_UPLOAD_DIR", BASE_DIR / "static" / "uploads"))
DB_PATH = DATA_DIR / "site.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

DATA_DIR.mkdir(parents=True, exist_ok=True)
secret_path = DATA_DIR / '.session-secret'
if not secret_path.exists():
    secret_path.write_text(secrets.token_hex(32), encoding='utf-8')

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secret_path.read_text(encoding="utf-8").strip(),
    MAX_CONTENT_LENGTH=24 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    UPLOAD_FOLDER=str(UPLOAD_DIR),
)

KINDS = {
    "ferries": "Ferris y horarios",
    "announcements": "Anuncios",
    "promotions": "Promociones",
    "experiences": "Experiencias",
}

DEFAULT_SETTINGS = {
    "site_name": ("MAYADVENTURE", "MAYADVENTURE"),
    "hero_title": ("Descubre la isla de Cozumel y Playa del Carmen", "Discover Cozumel Island and Playa del Carmen"),
    "hero_subtitle": ("Conviértete en tu propio guía y vive cada aventura a tu ritmo", "Become your own guide and enjoy each adventure at your pace"),
    "hero_button": ("Horarios de ferry", "Ferry schedules"),
    "hero_image": ("https://images.unsplash.com/photo-1544551763-46a013bb70d5?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80"),
    "ferries_title": ("Servicio de Ferry Cozumel–Playa del Carmen", "Cozumel–Playa del Carmen ferry service"),
    "ferries_subtitle": ("Ultramar, Winjet, Xcaret Xailing", "Ultramar, Winjet, Xcaret Xailing"),
    "announcements_title": ("Anuncios importantes", "Important announcements"),
    "map_title": ("Mapa turístico", "Tourist map"),
    "map_image": ("/static/img/mapa-cancun-playa-cozumel.png", "/static/img/mapa-cancun-playa-cozumel.png"),
    "map_link": ("", ""),
    "promotions_title": ("Promociones especiales", "Special promotions"),
    "promotions_subtitle": ("Aprovecha nuestras promociones destacadas", "Take advantage of our featured deals"),
    "experiences_title": ("Experiencias", "Experiences"),
    "experiences_subtitle": ("Contenido dinámico: agrega o elimina experiencias fácilmente", "Dynamic content: add or remove experiences anytime"),
    "footer_location_1": ("Playa del Carmen, Quintana Roo", "Playa del Carmen, Quintana Roo"),
    "footer_location_2": ("Conexión principal a Cozumel", "Main connection to Cozumel"),
    "instagram": ("#", "#"), "facebook": ("#", "#"), "tripadvisor": ("#", "#"),
    "copyright": ("© 2026 MAYADVENTURE. Todos los derechos reservados.", "© 2026 MAYADVENTURE. All rights reserved."),
}

SEED_ITEMS = [
    ("ferries", "Ultramar", "Ultramar", "Ver horarios y boletos", "View schedules and tickets", "/static/img/ultramar.png", "https://www.ultramarferry.com/es/rutas-y-horarios", "", "", "", "", 1),
    ("ferries", "Winjet", "Winjet", "Ver horarios y boletos", "View schedules and tickets", "/static/img/winjet.png", "https://winjet.mx/", "", "", "", "", 2),
    ("ferries", "Xcaret Xailing", "Xcaret Xailing", "Ver horarios y boletos", "View schedules and tickets", "/static/img/xcaret.png", "https://www.xailing.com/es/rutas-horarios/", "", "", "", "", 3),
    ("announcements", "Terminal segura", "Secure terminal", "Estamos al día con la seguridad y seguimos mejorando nuestras instalaciones para hacer la terminal marítima más segura de México.", "We stay up to date with safety standards and continuously improve our facilities to make this maritime terminal one of the safest in Mexico.", "/static/img/terminal-segura.png", "#ferries", "Ver horarios", "View schedules", "", "", "", "", 1),
    ("announcements", "Mantenimiento programado", "Scheduled maintenance", "El muelle principal podrá estar en mantenimiento en fechas programadas. Agradecemos tu comprensión.", "The main pier may be closed for scheduled maintenance on certain dates. Thank you for your understanding.", "https://images.unsplash.com/photo-1541888946425-d81bb19240f5?auto=format&fit=crop&w=800&q=80", "#contact", "Más información", "More info", "", "", "", "", 2),
    ("announcements", "Semana Santa", "Holy Week", "Son días de alto tránsito en la ruta de navegación entre la isla y el continente. Sea paciente en las filas y disfrute de la vista.", "These are high-traffic days on the route between the island and the mainland. Please be patient in line and enjoy the view.", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=800&q=80", "#ferries", "Ver horarios", "View schedules", "", "", "", "", 3),
    ("promotions", "Paquete familiar", "Family package", "Descuento especial para familias de 4 o más personas en servicios de ferry.", "Special discount for families of 4 or more on ferry services.", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=800&q=80", "#contact", "Reservar", "Book now", "-20%", "Familia", "Family", "$960", 1),
    ("promotions", "Tour + Ferry", "Tour + Ferry", "Reserva cualquier tour y obtén tu ferry redondo sin costo.", "Book any tour and get your round-trip ferry ticket at no cost.", "https://images.unsplash.com/photo-1506929562872-bb421503ef21?auto=format&fit=crop&w=800&q=80", "#contact", "Más información", "More information", "2x1", "Combo", "Combo", "Oferta especial", 2),
    ("promotions", "Verano 2026", "Summer 2026", "Paquete todo incluido: ferry, hotel y actividades con descuento especial.", "All-inclusive package: ferry, hotel, and activities with a special discount.", "https://images.unsplash.com/photo-1506477331477-33d5d8b3dc85?auto=format&fit=crop&w=800&q=80", "#contact", "Ver paquetes", "View packages", "15% OFF", "Julio-agosto", "July-August", "Desde $2,500", 3),
    ("experiences", "Snorkel en Cozumel", "Snorkeling in Cozumel", "Explora arrecifes cristalinos con guías locales certificados.", "Explore crystal-clear reefs with certified local guides.", "https://images.unsplash.com/photo-1682687220742-aba13b6e50ba?auto=format&fit=crop&w=1000&q=80", "", "", "", "", "", "", "", 1),
    ("experiences", "Ruta local en Playa del Carmen", "Local route in Playa del Carmen", "Recorre la ciudad con recomendaciones para comer, pasear y disfrutar.", "Explore the city with recommendations for dining, walking and enjoying.", "https://images.unsplash.com/photo-1519046904884-53103b34b206?auto=format&fit=crop&w=1000&q=80", "", "", "", "", "", "", "", 2),
]


SEED_ITEMS = [row[:-1] + ('', '') + row[-1:] if row[0] == 'ferries' else row for row in SEED_ITEMS]

@contextmanager
def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    backup = DATA_DIR / 'before-original-landing-v1.sqlite3'
    if DB_PATH.exists() and not backup.exists():
        source = sqlite3.connect(DB_PATH)
        destination = sqlite3.connect(backup)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_es TEXT NOT NULL DEFAULT '', value_en TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
                title_es TEXT NOT NULL DEFAULT '', title_en TEXT NOT NULL DEFAULT '',
                description_es TEXT NOT NULL DEFAULT '', description_en TEXT NOT NULL DEFAULT '',
                image TEXT NOT NULL DEFAULT '', link TEXT NOT NULL DEFAULT '',
                button_es TEXT NOT NULL DEFAULT '', button_en TEXT NOT NULL DEFAULT '',
                badge TEXT NOT NULL DEFAULT '', meta_es TEXT NOT NULL DEFAULT '', meta_en TEXT NOT NULL DEFAULT '',
                price TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(items)")}
        for column in ("duration_es", "duration_en", "old_price", "price_en"):
            if column not in columns:
                connection.execute(f"ALTER TABLE items ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        for key, values in DEFAULT_SETTINGS.items():
            connection.execute("INSERT OR IGNORE INTO settings(key,value_es,value_en) VALUES (?,?,?)", (key, *values))
        if not connection.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            initial_password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(15)
            if not os.environ.get("ADMIN_PASSWORD"):
                (DATA_DIR / 'initial-access.txt').write_text('Usuario: ' + os.environ.get('ADMIN_USERNAME', 'admin') + '\nContraseña: ' + initial_password + '\n', encoding='utf-8')
            connection.execute("INSERT INTO users(username,password_hash) VALUES (?,?)", (
                os.environ.get("ADMIN_USERNAME", "admin"),
                generate_password_hash(initial_password),
            ))
        if not connection.execute("SELECT 1 FROM settings WHERE key='content_initialized'").fetchone():
            connection.executemany("""INSERT INTO items
                (kind,title_es,title_en,description_es,description_en,image,link,button_es,button_en,badge,meta_es,meta_en,price,position)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", SEED_ITEMS)
            for title, duration_es, duration_en, old_price in [
                ('Paquete familiar', 'Lunes a jueves', 'Monday to Thursday', '$1,200'),
                ('Tour + Ferry', 'Temporada limitada', 'Limited season', ''),
                ('Verano 2026', 'Julio-agosto', 'July-August', '')]:
                connection.execute("UPDATE items SET duration_es=?,duration_en=?,old_price=? WHERE kind='promotions' AND title_es=?", (duration_es, duration_en, old_price, title))
            connection.execute("UPDATE items SET meta_es='Paquete',meta_en='Package' WHERE title_es='Verano 2026'")
            connection.execute("INSERT INTO settings(key,value_es,value_en) VALUES ('content_initialized','1','1')")
        # Restore only untouched defaults from the first CMS release, once.
        if not connection.execute("SELECT 1 FROM settings WHERE key='original_landing_v1'").fetchone():
            connection.execute("UPDATE settings SET value_es=? WHERE key=? AND value_es=?", ('https://images.unsplash.com/photo-1544551763-46a013bb70d5?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80', 'hero_image', '/static/img/Muelle.jpg'))
            connection.execute("UPDATE settings SET value_en=? WHERE key=? AND value_en=?", ('https://images.unsplash.com/photo-1544551763-46a013bb70d5?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80', 'hero_image', '/static/img/Muelle.jpg'))
            connection.execute("UPDATE settings SET value_es=? WHERE key=? AND value_es=?", ('Contenido dinámico: agrega o elimina experiencias fácilmente', 'experiences_subtitle', 'Descubre actividades inolvidables'))
            connection.execute("UPDATE settings SET value_en=? WHERE key=? AND value_en=?", ('Dynamic content: add or remove experiences anytime', 'experiences_subtitle', 'Discover unforgettable activities'))
            connection.execute("UPDATE items SET description_en=? WHERE title_es=? AND description_en=? AND kind IN ('announcements','promotions')", ('We stay up to date with safety standards and continuously improve our facilities to make this maritime terminal one of the safest in Mexico.', 'Terminal segura', 'We stay up to date with safety standards and continuously improve our facilities.'))
            connection.execute("UPDATE items SET description_en=? WHERE title_es=? AND description_en=? AND kind IN ('announcements','promotions')", ('The main pier may be closed for scheduled maintenance on certain dates. Thank you for your understanding.', 'Mantenimiento programado', 'The main pier may be closed for scheduled maintenance on certain dates.'))
            connection.execute("UPDATE items SET description_en=? WHERE title_es=? AND description_en=? AND kind IN ('announcements','promotions')", ('These are high-traffic days on the route between the island and the mainland. Please be patient in line and enjoy the view.', 'Semana Santa', 'These are high-traffic days on the route between the island and mainland. Please be patient and enjoy the view.'))
            connection.execute("UPDATE items SET description_en=? WHERE title_es=? AND description_en=? AND kind IN ('announcements','promotions')", ('All-inclusive package: ferry, hotel, and activities with a special discount.', 'Verano 2026', 'All-inclusive package: ferry, hotel and activities with a special discount.'))
            connection.execute("UPDATE items SET price_en=? WHERE kind='promotions' AND title_es=? AND price=? AND price_en=''", ('Special offer', 'Tour + Ferry', 'Oferta especial'))
            connection.execute("UPDATE items SET price_en=? WHERE kind='promotions' AND title_es=? AND price=? AND price_en=''", ('From $2,500', 'Verano 2026', 'Desde $2,500'))
            connection.execute("INSERT INTO settings(key,value_es,value_en) VALUES ('original_landing_v1','1','1')")


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(24)
    return session["_csrf"]


def validate_csrf():
    if not session.get("_csrf") or not secrets.compare_digest(session["_csrf"], request.form.get("_csrf", "")):
        abort(400, "Solicitud inválida. Actualiza la página.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def safe_url(value):
    value = value.strip()
    if not value:
        return value
    parsed = urlsplit(value)
    if any(ord(c) < 32 for c in value) or any(c in value for c in "\\'\"<>()"):
        raise ValueError("El enlace contiene caracteres no permitidos.")
    if parsed.scheme and parsed.scheme.lower() not in ('http', 'https'):
        raise ValueError("Usa un enlace que empiece con https:// o una ruta del sitio.")
    if value.startswith('//'):
        raise ValueError("Usa la dirección completa con https://.")
    return value


def save_image(file):
    if not file or not file.filename:
        return ""
    try:
        image = Image.open(file.stream)
        if image.format not in {'JPEG', 'PNG', 'WEBP', 'GIF'}:
            raise ValueError("Usa una imagen JPG, PNG, WEBP o GIF.")
        if image.width * image.height > 40_000_000:
            raise ValueError("La imagen es demasiado grande. Usa una de hasta 40 megapíxeles.")
        image = ImageOps.exif_transpose(image)
        image.thumbnail((2400, 2400))
        image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
        filename = f"{uuid4().hex}.webp"
        image.save(UPLOAD_DIR / filename, 'WEBP', quality=88)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("No se pudo leer la foto. Usa JPG, PNG, WEBP o GIF.")
    return f"/static/uploads/{filename}"


app.jinja_env.globals["csrf_token"] = csrf_token


@app.get("/")
def home():
    with db() as connection:
        settings = {r["key"]: {"es": r["value_es"], "en": r["value_en"] or r["value_es"]} for r in connection.execute("SELECT * FROM settings")}
        content = {kind: connection.execute("SELECT * FROM items WHERE kind=? AND active=1 ORDER BY position,id", (kind,)).fetchall() for kind in KINDS}
    return render_template("index.html", settings=settings, content=content)


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        validate_csrf()
        with db() as connection:
            user = connection.execute("SELECT * FROM users WHERE username=?", (request.form.get("username", "").strip(),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear(); session["user_id"] = user["id"]; session["username"] = user["username"]
            return redirect(url_for("admin"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.post("/admin/logout")
@login_required
def logout():
    validate_csrf(); session.clear()
    return redirect(url_for("home"))


@app.get("/admin")
@login_required
def admin():
    section = request.args.get("section", "general")
    if section not in {*KINDS, "general", "account"}: section = "general"
    with db() as connection:
        settings = {r["key"]: r for r in connection.execute("SELECT * FROM settings")}
        items = connection.execute("SELECT * FROM items WHERE kind=? ORDER BY position,id", (section,)).fetchall() if section in KINDS else []
    return render_template("admin.html", settings=settings, items=items, section=section, kinds=KINDS)


@app.post("/admin/settings")
@login_required
def update_settings():
    validate_csrf()
    try:
        for key in ('hero_image', 'map_image', 'map_link', 'instagram', 'facebook', 'tripadvisor'):
            for lang in ('es', 'en'):
                safe_url(request.form.get(f'{key}_{lang}', ''))
        hero = save_image(request.files.get("hero_upload")); map_image = save_image(request.files.get("map_upload"))
    except ValueError as error:
        flash(str(error), "error"); return redirect(url_for("admin"))
    with db() as connection:
        for key in DEFAULT_SETTINGS:
            es_key, en_key = f"{key}_es", f"{key}_en"
            if es_key in request.form:
                connection.execute("UPDATE settings SET value_es=?,value_en=? WHERE key=?", (request.form[es_key].strip(), request.form.get(en_key, "").strip(), key))
        if hero: connection.execute("UPDATE settings SET value_es=?,value_en=? WHERE key='hero_image'", (hero, hero))
        if map_image: connection.execute("UPDATE settings SET value_es=?,value_en=? WHERE key='map_image'", (map_image, map_image))
    flash("Configuración actualizada.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/items/save")
@login_required
def save_item():
    validate_csrf()
    kind = request.form.get("kind", "")
    if kind not in KINDS: abort(400)
    try:
        if not request.form.get('title_es', '').strip():
            raise ValueError('Escribe un título en español.')
        position = int(request.form.get('position', 0) or 0)
        safe_url(request.form.get('image', ''))
        safe_url(request.form.get('link', ''))
        uploaded = save_image(request.files.get("image_upload"))
    except ValueError as error:
        flash(str(error), "error"); return redirect(url_for("admin", section=kind))
    item_id = request.form.get("id", "").strip()
    values = (
        request.form.get("title_es", "").strip(), request.form.get("title_en", "").strip(),
        request.form.get("description_es", "").strip(), request.form.get("description_en", "").strip(),
        uploaded or request.form.get("image", "").strip(), request.form.get("link", "").strip(),
        request.form.get("button_es", "").strip(), request.form.get("button_en", "").strip(),
        request.form.get("badge", "").strip(), request.form.get("meta_es", "").strip(), request.form.get("meta_en", "").strip(),
        request.form.get("price", "").strip(), position, 1 if request.form.get("active") else 0,
        request.form.get("duration_es", "").strip(), request.form.get("duration_en", "").strip(), request.form.get("old_price", "").strip(), request.form.get("price_en", "").strip(),
    )
    with db() as connection:
        if item_id:
            connection.execute("""UPDATE items SET title_es=?,title_en=?,description_es=?,description_en=?,image=?,link=?,button_es=?,button_en=?,badge=?,meta_es=?,meta_en=?,price=?,position=?,active=?,duration_es=?,duration_en=?,old_price=?,price_en=? WHERE id=? AND kind=?""", values + (item_id, kind))
        else:
            connection.execute("""INSERT INTO items (title_es,title_en,description_es,description_en,image,link,button_es,button_en,badge,meta_es,meta_en,price,position,active,duration_es,duration_en,old_price,price_en,kind) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values + (kind,))
    flash("Elemento guardado.", "success")
    return redirect(url_for("admin", section=kind))


@app.post("/admin/items/<int:item_id>/delete")
@login_required
def delete_item(item_id):
    validate_csrf(); kind = request.form.get("kind", "")
    if kind not in KINDS: abort(400)
    with db() as connection: connection.execute("DELETE FROM items WHERE id=? AND kind=?", (item_id, kind))
    flash("Elemento eliminado.", "success")
    return redirect(url_for("admin", section=kind))


@app.post("/admin/password")
@login_required
def change_password():
    validate_csrf(); current = request.form.get("current_password", ""); new = request.form.get("new_password", "")
    if len(new) < 8:
        flash("La nueva contraseña debe tener al menos 8 caracteres.", "error")
    else:
        with db() as connection:
            user = connection.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
            if not user or not check_password_hash(user["password_hash"], current): flash("La contraseña actual no es correcta.", "error")
            else: connection.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(new), session["user_id"])); flash("Contraseña actualizada.", "success"); (DATA_DIR / "initial-access.txt").unlink(missing_ok=True)
    return redirect(url_for("admin", section="account"))


@app.errorhandler(413)
def too_large(_error):
    flash("Las imágenes superan el límite de 24 MB por envío. Elige fotos más pequeñas.", "error")
    return redirect(url_for('admin'))


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
