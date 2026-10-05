document.querySelectorAll('details.translation').forEach(section => {
    const form = section.closest('form');
    if (!form) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-light';
    button.textContent = 'Traducir del español al inglés';
    const status = document.createElement('p');
    status.className = 'hint';
    status.setAttribute('role', 'status');
    status.textContent = 'Genera una propuesta con DeepL. Revísala y guarda para publicarla.';
    section.querySelector('summary').after(button, status);
    button.addEventListener('click', async () => {
        const fields = Array.from(section.querySelectorAll('input[name$="_en"]:not([type="hidden"]),textarea[name$="_en"]'));
        const pairs = fields.map(target => {
            const sourceName = target.name === 'price_en' ? 'price' : target.name.replace(/_en$/, '_es');
            const source = form.elements.namedItem(sourceName);
            return {source, target, original: target.value, text: source?.value.trim()};
        }).filter(pair => pair.text);
        if (!pairs.length) { status.textContent = 'Primero escribe los textos en español.'; return; }
        if (pairs.some(pair => pair.original.trim()) && !confirm('¿Reemplazar los textos en inglés de esta sección con una nueva traducción?')) return;
        button.disabled = true;
        status.textContent = 'Traduciendo…';
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 25000);
        try {
            const body = new URLSearchParams({_csrf: form.elements.namedItem('_csrf').value, texts: JSON.stringify(pairs.map(pair => pair.text))});
            const response = await fetch('/admin/translate', {method: 'POST', body, signal: controller.signal});
            if (response.redirected) throw new Error('Tu sesión terminó. Vuelve a iniciar sesión.');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'No se pudo traducir.');
            if (!Array.isArray(data.translations) || data.translations.length !== pairs.length || data.translations.some(text => typeof text !== 'string')) throw new Error('Respuesta incompleta del traductor.');
            if (pairs.some(pair => pair.source.value.trim() !== pair.text || pair.target.value !== pair.original)) throw new Error('Editaste los textos durante la traducción. Vuelve a intentarlo para conservar tus cambios.');
            pairs.forEach((pair, index) => {
                pair.target.value = data.translations[index];
                pair.target.dispatchEvent(new Event('input', {bubbles: true}));
            });
            status.textContent = 'Traducción lista. Revisa el inglés y pulsa Guardar para publicarlo.';
        } catch (error) {
            status.textContent = error.name === 'AbortError' ? 'La traducción tardó demasiado. Intenta de nuevo.' : (error instanceof SyntaxError ? 'No se pudo traducir. Revisa tu sesión e intenta de nuevo.' : error.message);
        } finally { clearTimeout(timer); button.disabled = false; }
    });
});
