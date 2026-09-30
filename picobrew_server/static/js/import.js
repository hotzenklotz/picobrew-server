const input = document.getElementById('upload-input');
const dropzone = document.getElementById('upload-dropzone');
const fileList = document.getElementById('upload-file-list');
const submit = document.getElementById('upload-submit');
const feedback = document.getElementById('upload-feedback');
const form = document.getElementById('upload-form');
let files = [];

function renderFiles() {
  const transfer = new DataTransfer();
  files.forEach(file => transfer.items.add(file));
  input.files = transfer.files;
  fileList.replaceChildren();
  files.forEach((file, index) => {
    const row = document.createElement('li');
    const name = document.createElement('span');
    name.className = 'file-name';
    name.textContent = file.name;
    const size = document.createElement('small');
    size.textContent = `${Math.max(1, Math.round(file.size / 1024))} KB`;
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'file-remove';
    remove.textContent = 'Remove';
    remove.setAttribute('aria-label', `Remove ${file.name}`);
    remove.addEventListener('click', () => {
      files.splice(index, 1);
      renderFiles();
      feedback.textContent = `${file.name} removed. ${files.length} file${files.length === 1 ? '' : 's'} selected.`;
      const next = fileList.querySelectorAll('.file-remove')[Math.min(index, files.length - 1)];
      (next || input).focus();
    });
    row.append(name, size, remove);
    fileList.append(row);
  });
  submit.disabled = files.length === 0;
}
function addFiles(incoming) {
  const rejected = [];
  for (const file of incoming) {
    if (!/\.(xml|beerxml)$/i.test(file.name)) {
      rejected.push(file.name);
    } else if (!files.some(existing => existing.name === file.name)) {
      files.push(file);
    }
  }
  renderFiles();
  feedback.textContent = rejected.length
    ? `Not added: ${rejected.join(', ')}. Choose .xml or .beerxml files.`
    : `${files.length} file${files.length === 1 ? '' : 's'} selected. Ready to review.`;
}
input.addEventListener('change', () => addFiles([...input.files]));
['dragenter', 'dragover'].forEach(event => dropzone.addEventListener(event, e => {
  e.preventDefault();
  dropzone.classList.add('dragover');
}));
['dragleave', 'drop'].forEach(event => dropzone.addEventListener(event, e => {
  e.preventDefault();
  dropzone.classList.remove('dragover');
}));
dropzone.addEventListener('drop', e => addFiles([...e.dataTransfer.files]));
form.addEventListener('submit', () => {
  submit.disabled = true;
  submit.textContent = 'Reading recipes…';
  form.setAttribute('aria-busy', 'true');
});
window.addEventListener('pageshow', () => {
  files = [...input.files];
  renderFiles();
  submit.innerHTML = 'Review recipes <span aria-hidden="true">→</span>';
  form.removeAttribute('aria-busy');
});
