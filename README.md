# Maya Adventure

Sitio Flask con panel visual y responsivo en /admin. Permite editar portada, textos, fotos, mapa, ferris, anuncios, promociones y experiencias en español e inglés.

## Datos privados

Git no incluye data/ ni static/uploads/. Contienen la base site.db, usuarios, sesiones y fotos. Respaldarlos y transferirlos por separado. En una instalación sin base de datos, el acceso inicial se escribe en data/initial-access.txt. Cambiar la contraseña desde el panel. Una base existente conserva sus usuarios.

## Identificar la versión en PythonAnywhere

En Web, seleccionar el dominio y abrir el archivo WSGI. Revisar la ruta añadida a sys.path y la importación de app. Dentro de esa carpeta ejecutar:

```bash
pwd
git remote -v
git log -1 --oneline
git status --short
```

## Primera publicación desde Git

Conservar la carpeta publicada como respaldo. Clonar en una carpeta nueva:

```bash
git clone https://github.com/abnerck/maya-adventures.git ~/maya-adventures-panel
cd ~/maya-adventures-panel
workon muelle-venv
python -m pip install -r requirements.txt
```

Antes del primer inicio, transferir data/site.db y static/uploads si se desea conservar el contenido local. No reemplazar una base de producción sin respaldarla y revisar cuál contiene los datos vigentes.

En Web, configurar Source code y Working directory como /home/vegascorporativo/maya-adventures-panel. Conservar el virtualenv compatible. Mapear /static/ a /home/vegascorporativo/maya-adventures-panel/static. No publicar data/ mediante un mapeo estático.

Guardar una copia del WSGI anterior y configurar:

```python
import os
import sys
sys.path.insert(0, '/home/vegascorporativo/maya-adventures-panel')
os.environ['COOKIE_SECURE'] = '1'  # Para el dominio HTTPS
from app import app as application
```

Pulsar Reload y comprobar página, acceso, fotos y guardado. Para volver atrás, restaurar el WSGI y mapeo estático anteriores y pulsar Reload.

## Actualizaciones posteriores

Respaldar la base y fotos. En el clon activo:

```bash
cd ~/maya-adventures-panel
git status --short
git pull --ff-only
workon muelle-venv
python -m pip install -r requirements.txt
```

Resolver cualquier modificación local o conflicto antes de seguir. Pulsar Reload. Los datos excluidos de Git permanecen en el servidor.

## Pruebas

python -m unittest test_cms -v

Las ocho pruebas usan una base temporal y comprueban acceso, CSRF, persistencia, imágenes, contenido y contraseña.

## Restauraci?n de la landing original

La actualizaci?n restaura portada, subrayado de MAYA, subt?tulo de experiencias y textos originales de anuncios y promociones. Conserva el panel, las traducciones de experiencias y los ajustes m?viles. En el primer inicio, guarda una copia de la base existente en data/before-original-landing-v1.sqlite3 y corrige ?nicamente los valores predeterminados de la versi?n anterior. La migraci?n se ejecuta una sola vez y conserva usuarios y contenido personalizado. El precio o texto destacado en ingl?s ahora es editable dentro de la traducci?n de promociones.

## Fotos completas y traducción asistida

Anuncios, promociones, experiencias y vistas previas usan ajuste completo de la imagen (contain). Puede quedar fondo alrededor según la proporción. No se recorta el archivo al subirlo. Las fotos subidas para portada también se ajustan completas; los textos de portada siguen superpuestos. La portada original remota mantiene su presentación anterior.

El administrador ofrece “Traducir del español al inglés” dentro de cada bloque de inglés. Envía únicamente los textos de esa sección a DeepL, permite revisarlos y no publica hasta guardar. Solicita confirmación antes de reemplazar inglés existente. Si se escribe durante la petición, conserva esa edición. Los textos incluidos dentro de una fotografía no se traducen.

Configurar DEEPL_API_KEY en el entorno de PythonAnywhere antes de importar app en WSGI. Usar una cuenta DeepL API (Free o Pro); las claves Free terminadas en :fx usan api-free.deepl.com. La clave se guarda solo en el servidor, nunca en Git ni en JavaScript. Se puede guardar en un archivo privado dentro de data/ y cargarlo en WSGI. La conexión requiere salida HTTPS a DeepL y está sujeta a la cuota del proveedor. Sin clave, la edición manual sigue disponible y el botón informa que falta configuración.

Documentación oficial: https://www.deepl.com/en/developers

Validación: 10 pruebas automatizadas; flujo del botón revisado en navegador con respuesta simulada. Para activar y verificar traducciones reales falta configurar la clave del propietario.
