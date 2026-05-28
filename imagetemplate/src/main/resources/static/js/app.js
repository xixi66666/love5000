(function () {
    var state = {
        activeCategory: 'all',
        keyword: '',
        templates: [],
        categories: [],
        selected: null,
        renderedPromptEdited: false,
        referenceImages: []
    };

    var elements = {
        keywordInput: document.getElementById('keywordInput'),
        categoryTabs: document.getElementById('categoryTabs'),
        templateList: document.getElementById('templateList'),
        templateCount: document.getElementById('templateCount'),
        detailCategory: document.getElementById('detailCategory'),
        detailTitle: document.getElementById('detailTitle'),
        detailSummary: document.getElementById('detailSummary'),
        jsonTemplate: document.getElementById('jsonTemplate'),
        promptTemplate: document.getElementById('promptTemplate'),
        variablesInput: document.getElementById('variablesInput'),
        extraInstructionInput: document.getElementById('extraInstructionInput'),
        renderedPrompt: document.getElementById('renderedPrompt'),
        renderPromptButton: document.getElementById('renderPromptButton'),
        copyPromptButton: document.getElementById('copyPromptButton'),
        statusLine: document.getElementById('statusLine'),
        imageSizeSelect: document.getElementById('imageSizeSelect'),
        customImageSizeField: document.getElementById('customImageSizeField'),
        customImageSizeInput: document.getElementById('customImageSizeInput'),
        imageSizeHint: document.getElementById('imageSizeHint'),
        imageQualitySelect: document.getElementById('imageQualitySelect'),
        imageFormatSelect: document.getElementById('imageFormatSelect'),
        imageBackgroundSelect: document.getElementById('imageBackgroundSelect'),
        referenceImageInput: document.getElementById('referenceImageInput'),
        referenceImagePreview: document.getElementById('referenceImagePreview'),
        clearReferenceImagesButton: document.getElementById('clearReferenceImagesButton'),
        openAiApiKeyInput: document.getElementById('openAiApiKeyInput'),
        rememberApiKeyCheckbox: document.getElementById('rememberApiKeyCheckbox'),
        generateImageButton: document.getElementById('generateImageButton'),
        imageResult: document.getElementById('imageResult'),
        emptyImageState: document.getElementById('emptyImageState'),
        generatedImage: document.getElementById('generatedImage'),
        downloadImageButton: document.getElementById('downloadImageButton'),
        imageStatusLine: document.getElementById('imageStatusLine')
    };

    var SESSION_API_KEY_STORAGE = 'imagetemplate.openaiApiKey';
    var MAX_REFERENCE_IMAGE_COUNT = 16;
    var MAX_REFERENCE_IMAGE_SIZE = 50 * 1024 * 1024;
    var SUPPORTED_REFERENCE_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
    var MIN_IMAGE_PIXELS = 655360;
    var MAX_IMAGE_PIXELS = 8294400;
    var MAX_IMAGE_SIDE = 3840;
    var MAX_IMAGE_RATIO = 3;
    var EXPERIMENTAL_IMAGE_PIXELS = 2560 * 1440;
    var DEFAULT_SIZE_HINT = '尺寸需为宽x高，宽高为 16 的倍数，单边不超过 3840。';
    var CUSTOM_SIZE_HINT = DEFAULT_SIZE_HINT + ' 总像素 655360 到 8294400，最长边/最短边不超过 3。';

    function fetchJson(url, options) {
        return fetch(url, options).then(function (response) {
            return response.text().then(function (text) {
                var payload = {};
                if (text) {
                    try {
                        payload = JSON.parse(text);
                    } catch (error) {
                        payload = { message: text };
                    }
                }
                if (!response.ok) {
                    throw new Error(payload.message || ('Request failed: ' + response.status));
                }
                return payload;
            });
        });
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function loadCategories() {
        return fetchJson('/api/image-templates/categories').then(function (payload) {
            state.categories = payload.categories || [];
            renderCategories();
        });
    }

    function loadTemplates() {
        var params = new URLSearchParams();
        if (state.activeCategory !== 'all') {
            params.set('category', state.activeCategory);
        }
        if (state.keyword) {
            params.set('keyword', state.keyword);
        }
        return fetchJson('/api/image-templates' + (params.toString() ? '?' + params.toString() : ''))
            .then(function (payload) {
                state.templates = payload.templates || [];
                if (!state.selected || !state.templates.some(function (item) { return item.id === state.selected.id; })) {
                    state.selected = state.templates[0] || null;
                }
                renderTemplates();
                renderDetail();
            });
    }

    function renderCategories() {
        var allCount = state.categories.reduce(function (sum, category) {
            return sum + category.count;
        }, 0);
        var buttons = ['<button type="button" class="' + (state.activeCategory === 'all' ? 'active' : '') + '" data-category="all">全部 ' + allCount + '</button>'];
        state.categories.forEach(function (category) {
            buttons.push(
                '<button type="button" class="' + (state.activeCategory === category.slug ? 'active' : '') + '" data-category="' + escapeHtml(category.slug) + '">' +
                escapeHtml(category.name) + ' ' + category.count +
                '</button>'
            );
        });
        elements.categoryTabs.innerHTML = buttons.join('');
    }

    function renderTemplates() {
        elements.templateCount.textContent = state.templates.length;
        if (!state.templates.length) {
            elements.templateList.innerHTML = '<div class="template-card"><h3>没有匹配结果</h3><p>调整分类或关键词后重试。</p></div>';
            return;
        }
        elements.templateList.innerHTML = state.templates.map(function (template) {
            var tags = (template.tags || []).slice(0, 4).map(function (tag) {
                return '<span>' + escapeHtml(tag) + '</span>';
            }).join('');
            return '<button type="button" class="template-card ' + (state.selected && state.selected.id === template.id ? 'active' : '') + '" data-id="' + escapeHtml(template.id) + '">' +
                '<h3>' + escapeHtml(template.title) + '</h3>' +
                '<p>' + escapeHtml(template.summary) + '</p>' +
                '<div class="tag-row">' + tags + '</div>' +
                '</button>';
        }).join('');
    }

    function renderDetail() {
        var template = state.selected;
        elements.statusLine.textContent = '';
        if (!template) {
            elements.detailCategory.textContent = '请选择模板';
            elements.detailTitle.textContent = '模板详情';
            elements.detailSummary.textContent = '';
            elements.jsonTemplate.textContent = '{}';
        elements.promptTemplate.textContent = '';
        elements.variablesInput.value = '{}';
        elements.renderedPrompt.value = '';
        state.renderedPromptEdited = false;
        resetGeneratedImage();
        return;
    }
        elements.detailCategory.textContent = template.category;
        elements.detailTitle.textContent = template.title;
        elements.detailSummary.textContent = template.summary;
        elements.jsonTemplate.textContent = JSON.stringify(template.jsonTemplate, null, 2);
        elements.promptTemplate.textContent = template.promptTemplate;
        if (template.categorySlug === 'direct-prompt') {
            elements.variablesInput.value = '{}';
            elements.renderedPrompt.value = template.promptTemplate || '';
        } else {
            elements.variablesInput.value = buildVariableSeed(template.jsonTemplate);
            elements.renderedPrompt.value = '';
        }
        state.renderedPromptEdited = false;
        resetGeneratedImage();
    }

    function buildVariableSeed(jsonTemplate) {
        var seed = {};
        Object.keys(jsonTemplate || {}).forEach(function (key) {
            var value = jsonTemplate[key];
            if (typeof value === 'string' && value.indexOf('<') !== -1) {
                seed[key] = value;
            }
        });
        return JSON.stringify(seed, null, 2);
    }

    function selectTemplate(id) {
        state.selected = state.templates.find(function (template) {
            return template.id === id;
        }) || state.selected;
        renderTemplates();
        renderDetail();
    }

    function renderPrompt() {
        if (!state.selected) {
            return;
        }
        var variables = readVariables();
        if (variables === null) {
            elements.statusLine.textContent = '变量 JSON 格式不正确。';
            return;
        }
        elements.statusLine.textContent = '';
        fetchJson('/api/image-templates/' + encodeURIComponent(state.selected.id) + '/prompt', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                variables: variables,
                extraInstruction: elements.extraInstructionInput.value
            })
        }).then(function (payload) {
            elements.renderedPrompt.value = payload.prompt || '';
            state.renderedPromptEdited = false;
            elements.statusLine.textContent = 'Prompt 已生成。';
        }).catch(function () {
            elements.statusLine.textContent = 'Prompt 生成失败。';
        });
    }

    function readVariables() {
        try {
            return JSON.parse(elements.variablesInput.value || '{}');
        } catch (error) {
            return null;
        }
    }

    function getReferenceImageFiles() {
        if (!elements.referenceImageInput || !elements.referenceImageInput.files) {
            return [];
        }
        return Array.prototype.slice.call(elements.referenceImageInput.files);
    }

    function validateReferenceImageFiles(files) {
        if (files.length > MAX_REFERENCE_IMAGE_COUNT) {
            return '最多只能上传 16 张参考图片。';
        }
        for (var i = 0; i < files.length; i++) {
            if (SUPPORTED_REFERENCE_IMAGE_TYPES.indexOf(files[i].type) === -1) {
                return '参考图片仅支持 PNG、JPEG 或 WebP。';
            }
            if (files[i].size > MAX_REFERENCE_IMAGE_SIZE) {
                return '单张参考图片不能超过 50MB。';
            }
        }
        return '';
    }

    function parseImageSizeValue(value) {
        var normalized = String(value || '').trim().toLowerCase();
        var match = normalized.match(/^(\d+)x(\d+)$/);
        if (!match) {
            return null;
        }
        return {
            width: Number(match[1]),
            height: Number(match[2]),
            size: Number(match[1]) + 'x' + Number(match[2])
        };
    }

    function validateImageSize(sizeValue) {
        var parsed = parseImageSizeValue(sizeValue);
        if (!parsed) {
            return {
                valid: false,
                message: '尺寸格式不正确，请使用宽x高，例如 3840x2160。'
            };
        }
        if (!Number.isInteger(parsed.width) || !Number.isInteger(parsed.height) || parsed.width <= 0 || parsed.height <= 0) {
            return {
                valid: false,
                message: '尺寸宽高必须是正整数。'
            };
        }
        if (parsed.width % 16 !== 0 || parsed.height % 16 !== 0) {
            return {
                valid: false,
                message: '尺寸宽高都必须是 16 的倍数。'
            };
        }
        if (parsed.width > MAX_IMAGE_SIDE || parsed.height > MAX_IMAGE_SIDE) {
            return {
                valid: false,
                message: '尺寸单边不能超过 3840。'
            };
        }
        var longSide = Math.max(parsed.width, parsed.height);
        var shortSide = Math.min(parsed.width, parsed.height);
        if (longSide / shortSide > MAX_IMAGE_RATIO) {
            return {
                valid: false,
                message: '最长边/最短边不能超过 3。'
            };
        }
        var pixels = parsed.width * parsed.height;
        if (pixels < MIN_IMAGE_PIXELS || pixels > MAX_IMAGE_PIXELS) {
            return {
                valid: false,
                message: '总像素必须在 655360 到 8294400 之间。'
            };
        }
        return {
            valid: true,
            size: parsed.size,
            experimental: pixels >= EXPERIMENTAL_IMAGE_PIXELS,
            message: pixels >= EXPERIMENTAL_IMAGE_PIXELS ? '当前为 4K/大尺寸实验尺寸，生成可能更慢或受服务端限制。' : ''
        };
    }

    function resolveImageSize() {
        var selectedSize = elements.imageSizeSelect.value;
        return validateImageSize(selectedSize === 'custom' ? elements.customImageSizeInput.value : selectedSize);
    }

    function updateImageSizeUi() {
        var isCustom = elements.imageSizeSelect.value === 'custom';
        if (elements.customImageSizeField) {
            elements.customImageSizeField.hidden = !isCustom;
        }
        if (!elements.imageSizeHint) {
            return;
        }
        var validation = resolveImageSize();
        if (!validation.valid) {
            elements.imageSizeHint.textContent = isCustom ? validation.message : DEFAULT_SIZE_HINT;
            elements.imageSizeHint.classList.remove('is-warning');
            elements.imageSizeHint.classList.toggle('is-error', isCustom);
            return;
        }
        elements.imageSizeHint.textContent = validation.message || (isCustom ? CUSTOM_SIZE_HINT : DEFAULT_SIZE_HINT);
        elements.imageSizeHint.classList.toggle('is-warning', validation.experimental);
        elements.imageSizeHint.classList.remove('is-error');
    }

    function formatFileSize(size) {
        if (size >= 1024 * 1024) {
            return (size / 1024 / 1024).toFixed(1) + ' MB';
        }
        return Math.max(1, Math.round(size / 1024)) + ' KB';
    }

    function renderReferenceImagePreview() {
        var files = getReferenceImageFiles();
        state.referenceImages = files;
        if (!elements.referenceImagePreview || !elements.clearReferenceImagesButton) {
            return;
        }
        elements.clearReferenceImagesButton.disabled = files.length === 0;
        if (!files.length) {
            elements.referenceImagePreview.innerHTML = '<span>未选择参考图片</span>';
            return;
        }
        elements.referenceImagePreview.innerHTML = files.map(function (file) {
            return '<div class="reference-chip">' +
                '<span>' + escapeHtml(file.name) + '</span>' +
                '<small>' + escapeHtml(formatFileSize(file.size)) + '</small>' +
                '</div>';
        }).join('');
    }

    function clearReferenceImages() {
        if (elements.referenceImageInput) {
            elements.referenceImageInput.value = '';
        }
        renderReferenceImagePreview();
        if (elements.imageStatusLine) {
            elements.imageStatusLine.textContent = '';
        }
    }

    function buildGenerationPayload(variables, imageSize) {
        return {
            variables: variables,
            extraInstruction: elements.extraInstructionInput.value,
            prompt: elements.renderedPrompt.value,
            size: imageSize,
            quality: elements.imageQualitySelect.value,
            outputFormat: elements.imageFormatSelect.value,
            background: elements.imageBackgroundSelect.value
        };
    }

    function buildMultipartPayload(variables, files, imageSize) {
        var formData = new FormData();
        formData.append('variables', JSON.stringify(variables));
        formData.append('extraInstruction', elements.extraInstructionInput.value);
        formData.append('prompt', elements.renderedPrompt.value);
        formData.append('size', imageSize);
        formData.append('quality', elements.imageQualitySelect.value);
        formData.append('outputFormat', elements.imageFormatSelect.value);
        formData.append('background', elements.imageBackgroundSelect.value);
        files.forEach(function (file) {
            formData.append('referenceImages', file, file.name);
        });
        return formData;
    }

    function resetGeneratedImage() {
        if (elements.generatedImage) {
            elements.generatedImage.hidden = true;
            elements.generatedImage.removeAttribute('src');
        }
        if (elements.emptyImageState) {
            elements.emptyImageState.hidden = false;
            elements.emptyImageState.textContent = '生成后的图片会显示在这里';
        }
        if (elements.downloadImageButton) {
            elements.downloadImageButton.href = '#';
            elements.downloadImageButton.setAttribute('aria-disabled', 'true');
            elements.downloadImageButton.setAttribute('download', 'generated-image.png');
        }
        if (elements.imageStatusLine) {
            elements.imageStatusLine.textContent = '';
        }
        if (elements.imageResult) {
            elements.imageResult.classList.remove('loading');
        }
    }

    function setGenerating(isGenerating) {
        if (elements.generateImageButton) {
            elements.generateImageButton.disabled = isGenerating;
            elements.generateImageButton.textContent = isGenerating ? '生成中...' : '生成图片';
        }
        if (elements.imageResult) {
            elements.imageResult.classList.toggle('loading', isGenerating);
        }
        if (elements.emptyImageState && isGenerating) {
            elements.emptyImageState.hidden = false;
            elements.emptyImageState.textContent = '正在调用 OpenAI 生成图片...';
        }
    }

    function generatedFileName(templateId, format) {
        return (templateId || 'generated-image') + '.' + (format || 'png');
    }

    function showGeneratedImage(payload) {
        var imageUrl = payload.dataUrl;
        var format = payload.outputFormat || elements.imageFormatSelect.value || 'png';
        if (!imageUrl) {
            elements.imageStatusLine.textContent = 'OpenAI 返回中没有图片数据。';
            return;
        }
        elements.generatedImage.src = imageUrl;
        elements.generatedImage.hidden = false;
        elements.emptyImageState.hidden = true;
        elements.downloadImageButton.href = imageUrl;
        elements.downloadImageButton.setAttribute('download', generatedFileName(payload.templateId, format));
        elements.downloadImageButton.setAttribute('aria-disabled', 'false');
        if (payload.prompt) {
            elements.renderedPrompt.value = payload.prompt;
            state.renderedPromptEdited = false;
        }
        elements.imageStatusLine.textContent = '图片已生成，可预览或下载。';
    }

    function generateImage() {
        if (!state.selected) {
            return;
        }
        var variables = readVariables();
        if (variables === null) {
            elements.imageStatusLine.textContent = '变量 JSON 格式不正确。';
            return;
        }
        var referenceFiles = getReferenceImageFiles();
        var referenceFileError = validateReferenceImageFiles(referenceFiles);
        if (referenceFileError) {
            elements.imageStatusLine.textContent = referenceFileError;
            return;
        }
        var imageSizeValidation = resolveImageSize();
        updateImageSizeUi();
        if (!imageSizeValidation.valid) {
            elements.imageStatusLine.textContent = imageSizeValidation.message;
            return;
        }
        setGenerating(true);
        elements.imageStatusLine.textContent = imageSizeValidation.message || '';
        persistSessionApiKey();
        var headers = {};
        var userApiKey = readUserApiKey();
        if (userApiKey) {
            headers['X-OpenAI-Api-Key'] = userApiKey;
        }
        var requestBody;
        if (referenceFiles.length) {
            requestBody = buildMultipartPayload(variables, referenceFiles, imageSizeValidation.size);
        } else {
            headers['Content-Type'] = 'application/json';
            requestBody = JSON.stringify(buildGenerationPayload(variables, imageSizeValidation.size));
        }
        fetchJson('/api/image-templates/' + encodeURIComponent(state.selected.id) + '/generate', {
            method: 'POST',
            headers: headers,
            body: requestBody
        }).then(function (payload) {
            showGeneratedImage(payload);
        }).catch(function (error) {
            resetGeneratedImage();
            elements.imageStatusLine.textContent = error.message || '图片生成失败。';
        }).finally(function () {
            setGenerating(false);
        });
    }

    function readUserApiKey() {
        return elements.openAiApiKeyInput ? elements.openAiApiKeyInput.value.trim() : '';
    }

    function persistSessionApiKey() {
        if (!elements.rememberApiKeyCheckbox || !elements.openAiApiKeyInput || !window.sessionStorage) {
            return;
        }
        if (elements.rememberApiKeyCheckbox.checked) {
            sessionStorage.setItem(SESSION_API_KEY_STORAGE, elements.openAiApiKeyInput.value);
        } else {
            sessionStorage.removeItem(SESSION_API_KEY_STORAGE);
        }
    }

    function loadSessionApiKey() {
        if (!elements.rememberApiKeyCheckbox || !elements.openAiApiKeyInput || !window.sessionStorage) {
            return;
        }
        var savedApiKey = sessionStorage.getItem(SESSION_API_KEY_STORAGE);
        if (savedApiKey) {
            elements.openAiApiKeyInput.value = savedApiKey;
            elements.rememberApiKeyCheckbox.checked = true;
        }
        elements.rememberApiKeyCheckbox.addEventListener('change', persistSessionApiKey);
        elements.openAiApiKeyInput.addEventListener('input', function () {
            if (elements.rememberApiKeyCheckbox.checked) {
                persistSessionApiKey();
            }
        });
    }

    function copyPrompt() {
        var text = elements.renderedPrompt.value || elements.promptTemplate.textContent || '';
        if (!text) {
            return;
        }
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(function () {
                elements.statusLine.textContent = '已复制。';
            });
        } else {
            elements.renderedPrompt.select();
            document.execCommand('copy');
            elements.statusLine.textContent = '已复制。';
        }
    }

    elements.keywordInput.addEventListener('input', function () {
        state.keyword = elements.keywordInput.value.trim();
        loadTemplates();
    });

    elements.categoryTabs.addEventListener('click', function (event) {
        var button = event.target.closest('button[data-category]');
        if (!button) {
            return;
        }
        state.activeCategory = button.getAttribute('data-category');
        renderCategories();
        loadTemplates();
    });

    elements.templateList.addEventListener('click', function (event) {
        var button = event.target.closest('button[data-id]');
        if (button) {
            selectTemplate(button.getAttribute('data-id'));
        }
    });

    elements.renderPromptButton.addEventListener('click', renderPrompt);
    elements.copyPromptButton.addEventListener('click', copyPrompt);
    elements.generateImageButton.addEventListener('click', generateImage);
    elements.imageSizeSelect.addEventListener('change', updateImageSizeUi);
    elements.customImageSizeInput.addEventListener('input', updateImageSizeUi);
    elements.renderedPrompt.addEventListener('input', function () {
        state.renderedPromptEdited = true;
        if (elements.renderedPrompt.value.trim()) {
            elements.statusLine.textContent = '已手动编辑，生成图片时会使用当前内容。';
        }
    });
    elements.referenceImageInput.addEventListener('change', function () {
        var files = getReferenceImageFiles();
        var referenceFileError = validateReferenceImageFiles(files);
        renderReferenceImagePreview();
        elements.imageStatusLine.textContent = referenceFileError || (files.length ? '已选择 ' + files.length + ' 张参考图片。' : '');
    });
    elements.clearReferenceImagesButton.addEventListener('click', clearReferenceImages);
    renderReferenceImagePreview();
    updateImageSizeUi();
    loadSessionApiKey();

    Promise.all([loadCategories(), loadTemplates()]).catch(function () {
        elements.statusLine.textContent = '模板加载失败。';
    });
})();
