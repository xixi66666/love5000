(function () {
    var state = {
        activeCategory: 'all',
        keyword: '',
        templates: [],
        categories: [],
        selected: null
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
        imageQualitySelect: document.getElementById('imageQualitySelect'),
        imageFormatSelect: document.getElementById('imageFormatSelect'),
        imageBackgroundSelect: document.getElementById('imageBackgroundSelect'),
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
        resetGeneratedImage();
        return;
    }
        elements.detailCategory.textContent = template.category;
        elements.detailTitle.textContent = template.title;
        elements.detailSummary.textContent = template.summary;
        elements.jsonTemplate.textContent = JSON.stringify(template.jsonTemplate, null, 2);
        elements.promptTemplate.textContent = template.promptTemplate;
        elements.variablesInput.value = buildVariableSeed(template.jsonTemplate);
        elements.renderedPrompt.value = '';
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
        setGenerating(true);
        elements.imageStatusLine.textContent = '';
        persistSessionApiKey();
        var headers = {
            'Content-Type': 'application/json'
        };
        var userApiKey = readUserApiKey();
        if (userApiKey) {
            headers['X-OpenAI-Api-Key'] = userApiKey;
        }
        fetchJson('/api/image-templates/' + encodeURIComponent(state.selected.id) + '/generate', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                variables: variables,
                extraInstruction: elements.extraInstructionInput.value,
                prompt: elements.renderedPrompt.value,
                size: elements.imageSizeSelect.value,
                quality: elements.imageQualitySelect.value,
                outputFormat: elements.imageFormatSelect.value,
                background: elements.imageBackgroundSelect.value
            })
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
    loadSessionApiKey();

    Promise.all([loadCategories(), loadTemplates()]).catch(function () {
        elements.statusLine.textContent = '模板加载失败。';
    });
})();
