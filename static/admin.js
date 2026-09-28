let dirty = false;
document.querySelectorAll('.editor-form').forEach(form => {
  form.addEventListener('input', () => {
    dirty = true;
    const status = form.querySelector('.save-status');
    if (status) { status.textContent = 'Tienes cambios sin guardar'; status.classList.add('is-dirty'); }
  });
  form.addEventListener('submit', () => { dirty = false; });
});
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
document.querySelectorAll('[data-open-new]').forEach(button => button.addEventListener('click', () => {
  const editor = document.getElementById('new-item'); editor.open = true;
  editor.scrollIntoView({behavior:'smooth', block:'start'});
  editor.querySelector('input[name=title_es]').focus({preventScroll:true});
}));
document.querySelectorAll('.photo-picker').forEach(picker => {
  const input = picker.querySelector('input[type=file]');
  input.addEventListener('change', () => {
    const holder = picker.querySelector('.photo-preview');
    let preview = holder.querySelector('img');
    if (!preview) { preview=document.createElement('img'); preview.alt='Vista previa de la foto seleccionada'; holder.prepend(preview); }
    if (!('original' in preview.dataset)) preview.dataset.original=preview.getAttribute('src') || '';
    if (preview.dataset.url) URL.revokeObjectURL(preview.dataset.url);
    const file=input.files[0];
    if(file) {
      preview.dataset.url=URL.createObjectURL(file); preview.src=preview.dataset.url; preview.hidden=false;
      picker.querySelector('.file-note').textContent=file.name + ' · Guarda para publicar esta foto';
    } else {
      preview.src=preview.dataset.original; preview.hidden=!preview.dataset.original;
      picker.querySelector('.file-note').textContent='Desde tu celular o computadora';
    }
  });
});
document.querySelectorAll('.card-image img,.photo-preview img').forEach(img => {
  img.addEventListener('error', () => { img.hidden=true; });
  if(img.complete && !img.naturalWidth) img.hidden=true;
});
const anchor = location.hash && document.getElementById(location.hash.slice(1));
if(anchor?.tagName==='DETAILS') anchor.open=true;
document.querySelectorAll('a[href="#cover-editor"]').forEach(link => link.addEventListener('click', () => {
  document.getElementById('cover-editor').open = true;
}));
const activeLink = document.querySelector('.nav-link.active');
if (activeLink && window.innerWidth <= 900) {
  activeLink.parentElement.scrollLeft = activeLink.offsetLeft - 16;
}
