// Global variables to store uploaded file details
let coverWidth = 0;
let coverHeight = 0;
let payloadSize = 0;
let currentMethod = 'auto';

// Initialize events when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    // Setup file drag and drop listeners
    setupDragAndDrop('cover-drop-zone', 'cover-input', handleCoverFile);
    setupDragAndDrop('payload-drop-zone', 'payload-input', handlePayloadFile);
    setupDragAndDrop('stego-drop-zone', 'stego-input', handleStegoFile);

    // Watch inputs that affect capacity
    const rangeInputs = document.querySelectorAll('#advanced-hide-content input[type="range"]');
    rangeInputs.forEach(input => {
        input.addEventListener('input', () => {
            calculateCapacity();
        });
    });

    // Form submission handlers
    setupHideForm();
    setupRevealForm();
});

// Switch Tab logic
function switchTab(tab) {
    // Buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`tab-${tab}`).classList.add('active');

    // Forms
    document.querySelectorAll('.stego-form').forEach(form => form.classList.remove('active'));
    document.getElementById(`${tab}-form`).classList.add('active');

    // Close alert
    closeAlert();
}

// Password toggle eye icon
function togglePassword(inputId, el) {
    const input = document.getElementById(inputId);
    if (input.type === 'password') {
        input.type = 'text';
        el.classList.remove('fa-eye-slash');
        el.classList.add('fa-eye');
    } else {
        input.type = 'password';
        el.classList.remove('fa-eye');
        el.classList.add('fa-eye-slash');
    }
}

// Expand advanced settings panel
function toggleAdvanced(contentId) {
    const content = document.getElementById(contentId);
    const arrow = document.getElementById(contentId.replace('content', 'arrow'));
    
    content.classList.toggle('hidden');
    arrow.classList.toggle('rotated');
}

// Update text label above slider
function updateRangeVal(slider, valSpanId) {
    document.getElementById(valSpanId).textContent = slider.value;
}

// File Drag & Drop handlers
function setupDragAndDrop(zoneId, inputId, callback) {
    const zone = document.getElementById(zoneId);
    const input = document.getElementById(inputId);

    // Prevent defaults
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        zone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop zone
    ['dragenter', 'dragover'].forEach(eventName => {
        zone.addEventListener(eventName, () => zone.classList.add('dragover'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        zone.addEventListener(eventName, () => zone.classList.remove('dragover'), false);
    });

    // Handle dropped files
    zone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            input.files = files;
            callback(files[0]);
        }
    });

    // Handle selected files via input click
    input.addEventListener('change', (e) => {
        if (input.files.length > 0) {
            callback(input.files[0]);
        }
    });
}

// Format file size helper
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// Handle selected cover file
function handleCoverFile(file) {
    const preview = document.getElementById('cover-preview');
    const dropZone = document.getElementById('cover-drop-zone');

    if (!file.type.match('image.*')) {
        showAlert('Invalid file type. Cover must be a PNG or JPEG image.', 'error');
        return;
    }

    // Read image dimensions
    const reader = new FileReader();
    reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
            coverWidth = img.width;
            coverHeight = img.height;
            
            // Show preview details
            dropZone.querySelector('.upload-icon').style.display = 'none';
            dropZone.querySelector('.upload-text').style.display = 'none';
            
            preview.style.display = 'flex';
            preview.innerHTML = `
                <i class="fa-solid fa-file-image" style="font-size: 1.5rem;"></i>
                <div style="text-align: left;">
                    <div style="font-weight:600; color: var(--text-main);">${file.name}</div>
                    <div style="color: var(--text-muted); font-size: 0.8rem;">
                        ${formatBytes(file.size)} &bull; ${coverWidth}x${coverHeight}px
                    </div>
                </div>
            `;

            calculateCapacity();
        };
        img.src = e.target.result;
    };
    reader.readAsDataURL(file);
}

// Handle selected payload file
function handlePayloadFile(file) {
    const preview = document.getElementById('payload-preview');
    const dropZone = document.getElementById('payload-drop-zone');

    payloadSize = file.size;

    dropZone.querySelector('.upload-icon').style.display = 'none';
    dropZone.querySelector('.upload-text').style.display = 'none';

    preview.style.display = 'flex';
    preview.innerHTML = `
        <i class="fa-solid fa-file-zipper" style="font-size: 1.5rem;"></i>
        <div style="text-align: left;">
            <div style="font-weight:600; color: var(--text-main);">${file.name}</div>
            <div style="color: var(--text-muted); font-size: 0.8rem;">
                ${formatBytes(file.size)} ${file.name.endsWith('.zip') ? '' : '(will be zipped)'}
            </div>
        </div>
    `;

    calculateCapacity();
}

// Handle selected stego file
function handleStegoFile(file) {
    const preview = document.getElementById('stego-preview');
    const dropZone = document.getElementById('stego-drop-zone');

    dropZone.querySelector('.upload-icon').style.display = 'none';
    dropZone.querySelector('.upload-text').style.display = 'none';

    preview.style.display = 'flex';
    preview.innerHTML = `
        <i class="fa-solid fa-file-image" style="font-size: 1.5rem;"></i>
        <div style="text-align: left;">
            <div style="font-weight:600; color: var(--text-main);">${file.name}</div>
            <div style="color: var(--text-muted); font-size: 0.8rem;">${formatBytes(file.size)}</div>
        </div>
    `;
}

// Method selection UI handler
function selectMethod(method) {
    currentMethod = method;
    
    // Update active cards styles
    document.querySelectorAll('.method-card').forEach(card => {
        card.classList.remove('active');
        const radio = card.querySelector('input[type="radio"]');
        if (radio.value === method) {
            card.classList.add('active');
        }
    });

    const capacityCard = document.getElementById('capacity-card');
    if (method === 'robust') {
        capacityCard.style.display = 'block';
    } else {
        capacityCard.style.display = 'none';
    }

    calculateCapacity();
}

// Local capacity check and update
function calculateCapacity() {
    if (currentMethod !== 'robust') {
        document.getElementById('hide-submit-btn').removeAttribute('disabled');
        return;
    }

    const valDim = document.getElementById('val-dimensions');
    const valPayload = document.getElementById('val-payload-size');
    const valMax = document.getElementById('val-max-size');
    const fill = document.getElementById('capacity-fill');
    const percentageText = document.getElementById('capacity-percentage');
    const warningMsg = document.getElementById('capacity-warning-msg');
    const submitBtn = document.getElementById('hide-submit-btn');

    if (!coverWidth || !coverHeight) {
        valDim.textContent = '-';
        valPayload.textContent = '-';
        valMax.textContent = '-';
        fill.style.width = '0%';
        percentageText.textContent = '0%';
        warningMsg.style.display = 'none';
        return;
    }

    valDim.textContent = `${coverWidth}x${coverHeight}px`;
    valPayload.textContent = formatBytes(payloadSize);

    // Read advanced parameters from sliders
    const blockSize = parseInt(document.querySelector('input[name="block_size"]').value);
    const redundancy = parseInt(document.querySelector('input[name="redundancy"]').value);

    // Capacity math (matching python logic)
    const blocksH = Math.floor(coverHeight / blockSize);
    const blocksW = Math.floor(coverWidth / blockSize);
    const totalBlocks = blocksH * blocksW;
    const payloadBytes = Math.floor(totalBlocks / (14 * redundancy));
    const maxCapacityBytes = Math.max(0, payloadBytes - 24);

    valMax.textContent = formatBytes(maxCapacityBytes);

    if (payloadSize === 0) {
        fill.style.width = '0%';
        percentageText.textContent = '0%';
        warningMsg.style.display = 'none';
        submitBtn.removeAttribute('disabled');
        return;
    }

    const pct = maxCapacityBytes > 0 ? (payloadSize / maxCapacityBytes) * 100 : 999;
    fill.style.width = `${Math.min(100, pct)}%`;
    percentageText.textContent = `${Math.round(pct)}%`;

    // Colors based on usage
    fill.classList.remove('warning', 'danger');
    if (pct > 100) {
        fill.classList.add('danger');
        warningMsg.style.display = 'flex';
        submitBtn.setAttribute('disabled', 'true');
    } else if (pct > 80) {
        fill.classList.add('warning');
        warningMsg.style.display = 'none';
        submitBtn.removeAttribute('disabled');
    } else {
        warningMsg.style.display = 'none';
        submitBtn.removeAttribute('disabled');
    }
}

// Show custom alert
function showAlert(message, type = 'success') {
    const card = document.getElementById('alert-card');
    const icon = document.getElementById('alert-icon');
    const msg = document.getElementById('alert-message');

    card.className = `alert-card ${type}`;
    msg.textContent = message;

    icon.className = 'fa-solid';
    if (type === 'success') {
        icon.classList.add('fa-circle-check');
    } else {
        icon.classList.add('fa-circle-exclamation');
    }

    card.classList.remove('hidden');
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Close alert
function closeAlert() {
    document.getElementById('alert-card').classList.add('hidden');
}

// Submit HIDE form
function setupHideForm() {
    const form = document.getElementById('hide-form');
    const submitBtn = document.getElementById('hide-submit-btn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        closeAlert();

        // Extra UI validation
        if (currentMethod === 'robust' && !coverWidth) {
            showAlert('Please select a cover image first.', 'error');
            return;
        }

        const formData = new FormData(form);

        // Show spinner
        submitBtn.setAttribute('disabled', 'true');
        submitBtn.querySelector('.btn-text').classList.add('hidden');
        submitBtn.querySelector('.spinner').classList.remove('hidden');

        try {
            const response = await fetch('/hide', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                // Read image response as blob
                const blob = await response.blob();
                
                // Get filename from response header
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'stego_image.png';
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename="(.+)"/);
                    if (match && match[1]) filename = match[1];
                }

                // Download blob to browser
                const downloadUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(downloadUrl);

                showAlert('Embedding completed! Stego image download started.', 'success');
            } else {
                const errData = await response.json();
                showAlert(errData.error || 'Failed to embed file in the image.', 'error');
            }
        } catch (error) {
            showAlert('A network error occurred. Please try again.', 'error');
        } finally {
            submitBtn.removeAttribute('disabled');
            submitBtn.querySelector('.btn-text').classList.remove('hidden');
            submitBtn.querySelector('.spinner').classList.add('hidden');
        }
    });
}

// Submit REVEAL form
function setupRevealForm() {
    const form = document.getElementById('reveal-form');
    const submitBtn = document.getElementById('reveal-submit-btn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        closeAlert();

        const formData = new FormData(form);

        // Show spinner
        submitBtn.setAttribute('disabled', 'true');
        submitBtn.querySelector('.btn-text').classList.add('hidden');
        submitBtn.querySelector('.spinner').classList.remove('hidden');

        try {
            const response = await fetch('/reveal', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const blob = await response.blob();
                
                // Extract filename
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'extracted_file';
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename="(.+)"/);
                    if (match && match[1]) filename = match[1];
                }

                const downloadUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = downloadUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(downloadUrl);

                showAlert('Extraction successful! Hidden file downloaded.', 'success');
            } else {
                const errData = await response.json();
                showAlert(errData.error || 'Failed to extract file. Check password or settings.', 'error');
            }
        } catch (error) {
            showAlert('A network error occurred. Please try again.', 'error');
        } finally {
            submitBtn.removeAttribute('disabled');
            submitBtn.querySelector('.btn-text').classList.remove('hidden');
            submitBtn.querySelector('.spinner').classList.add('hidden');
        }
    });
}
