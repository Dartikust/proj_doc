const zone = document.getElementById('uploadForm');
const input = document.getElementById('fileInput');
const choose = document.getElementById('chooseFileBtn');
const selected = document.getElementById('selectedFile');
const upload = document.getElementById('uploadBtn');

if (zone && input && choose && selected && upload) {
    const updateFile = () => {
        const file = input.files && input.files[0];
        if (!file) {
            selected.textContent = '';
            upload.classList.remove('visible');
            return;
        }
        const size = file.size < 1024 * 1024
            ? `${Math.max(1, Math.round(file.size / 1024))} КБ`
            : `${(file.size / 1024 / 1024).toFixed(1)} МБ`;
        selected.innerHTML = `<strong>${file.name}</strong><span>${size}</span>`;
        upload.classList.add('visible');
    };

    choose.addEventListener('click', () => input.click());
    input.addEventListener('change', updateFile);

    ['dragenter', 'dragover'].forEach(eventName => {
        zone.addEventListener(eventName, event => {
            event.preventDefault();
            zone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        zone.addEventListener(eventName, event => {
            event.preventDefault();
            zone.classList.remove('dragover');
        });
    });

    zone.addEventListener('drop', event => {
        if (!event.dataTransfer.files.length) return;
        input.files = event.dataTransfer.files;
        updateFile();
    });
}

for (const row of document.querySelectorAll('.clickable-row')) {
    const open = () => {
        const href = row.dataset.href;
        if (href) window.location.href = href;
    };

    row.addEventListener('click', event => {
        if (event.target.closest('a, button, input, select')) return;
        open();
    });

    row.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            open();
        }
    });
}
