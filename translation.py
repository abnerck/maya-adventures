"""Server-side DeepL adapter; credentials never reach the browser."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def translate_texts(texts):
    key = os.environ.get('DEEPL_API_KEY', '').strip()
    if not key:
        raise ValueError('La traducción automática aún no está configurada. Puedes escribir el inglés manualmente.')
    host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
    request = Request(
        f'https://{host}/v2/translate',
        data=json.dumps({'text': texts, 'source_lang': 'ES', 'target_lang': 'EN-US', 'preserve_formatting': True}).encode('utf-8'),
        headers={'Authorization': f'DeepL-Auth-Key {key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.load(response)
        translated = [item['text'] for item in result['translations']]
        if len(translated) != len(texts) or not all(isinstance(text, str) for text in translated):
            raise ValueError('Respuesta incompleta del traductor. Intenta de nuevo.')
        return translated
    except HTTPError as error:
        if error.code in (401, 403):
            raise ValueError('Revisa la clave de DeepL en la configuración del servidor.') from None
        if error.code in (429, 456):
            raise ValueError('El servicio alcanzó su límite. Intenta más tarde o revisa tu cuota de DeepL.') from None
        raise ValueError('El traductor no está disponible. Intenta de nuevo más tarde.') from None
    except (URLError, TimeoutError, OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('No se pudo obtener la traducción. Tus textos no se han cambiado.') from None
