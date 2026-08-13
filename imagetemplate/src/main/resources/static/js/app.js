(function () {
    var state = {
        activeSource: '',
        activeCategory: '',
        activeFunctionCategory: '',
        activeFunctionScene: '',
        keyword: '',
        imageOnly: false,
        page: 1,
        size: 48,
        catalogTotal: 0,
        total: 0,
        hasMore: false,
        templates: [],
        sources: [],
        categories: [],
        functionCategories: [],
        libraryStatus: null,
        selected: null,
        jsonTemplateEdited: false,
        renderedPromptEdited: false,
        referenceImages: []
    };

    var elements = {
        keywordInput: document.getElementById('keywordInput'),
        libraryAlert: document.getElementById('libraryAlert'),
        functionCategoryFilters: document.getElementById('functionCategoryFilters'),
        functionCategorySelect: document.getElementById('functionCategorySelect'),
        functionSceneFilters: document.getElementById('functionSceneFilters'),
        sourceFilters: document.getElementById('sourceFilters'),
        categorySelect: document.getElementById('categorySelect'),
        imageOnlyToggle: document.getElementById('imageOnlyToggle'),
        clearFiltersButton: document.getElementById('clearFiltersButton'),
        loadMoreButton: document.getElementById('loadMoreButton'),
        listStatus: document.getElementById('listStatus'),
        templateList: document.getElementById('templateList'),
        templateCount: document.getElementById('templateCount'),
        detailCategory: document.getElementById('detailCategory'),
        detailTitle: document.getElementById('detailTitle'),
        detailSummary: document.getElementById('detailSummary'),
        jsonTemplate: document.getElementById('jsonTemplate'),
        jsonTemplateStatus: document.getElementById('jsonTemplateStatus'),
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
        imageStatusLine: document.getElementById('imageStatusLine'),
        sceneStatus: document.getElementById('sceneStatus'),
        scenePrevButton: document.getElementById('scenePrevButton'),
        sceneNextButton: document.getElementById('sceneNextButton'),
        dockProgressBar: document.getElementById('dockProgressBar'),
        scenePanels: document.querySelectorAll('.scene[data-scene]'),
        dockSteps: document.querySelectorAll('.dock-step[data-scene-target]')
    };

    var sceneOrder = ['discover', 'deconstruct', 'direct', 'render'];
    var sceneLabels = {
        discover: '灵感大厅',
        deconstruct: '模板解构',
        direct: 'Prompt 编导台',
        render: '图片生成舱'
    };
    var activeScene = 'discover';
    var SESSION_API_KEY_STORAGE = 'imagetemplate.openaiApiKey';
    var MAX_REFERENCE_IMAGE_COUNT = 16;
    var MAX_REFERENCE_IMAGE_SIZE = 50 * 1024 * 1024;
    var SUPPORTED_REFERENCE_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
    var MIN_IMAGE_PIXELS = 655360;
    var MAX_IMAGE_PIXELS = 8294400;
    var MAX_IMAGE_SIDE = 3840;
    var MAX_IMAGE_RATIO = 3;
    var EXPERIMENTAL_IMAGE_PIXELS = 2560 * 1440;
    var SEARCH_DEBOUNCE_MS = 300;
    var searchTimer = null;
    var listRequestSequence = 0;
    var detailRequestSequence = 0;
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

    function setActiveScene(sceneName, shouldFocus) {
        var sceneIndex = sceneOrder.indexOf(sceneName);
        if (sceneIndex < 0) {
            return;
        }
        if (sceneIndex >= sceneOrder.indexOf('direct') && !syncJsonTemplateToVariables()) {
            return;
        }

        activeScene = sceneName;
        var activePanel = null;
        Array.prototype.forEach.call(elements.scenePanels, function (panel) {
            var isActive = panel.getAttribute('data-scene') === sceneName;
            panel.classList.toggle('is-active', isActive);
            if (isActive) {
                panel.removeAttribute('aria-hidden');
                activePanel = panel;
            } else {
                panel.setAttribute('aria-hidden', 'true');
            }
        });

        Array.prototype.forEach.call(elements.dockSteps, function (button) {
            var isActive = button.getAttribute('data-scene-target') === sceneName;
            button.classList.toggle('is-active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        if (elements.sceneStatus) {
            elements.sceneStatus.textContent =
                (sceneIndex < 9 ? '0' : '') + (sceneIndex + 1) + ' · ' + sceneLabels[sceneName];
        }
        updateDockProgress(sceneIndex);
        if (elements.scenePrevButton) {
            elements.scenePrevButton.disabled = sceneIndex === 0;
        }
        if (elements.sceneNextButton) {
            elements.sceneNextButton.disabled = sceneIndex === sceneOrder.length - 1;
        }

        if (shouldFocus && activePanel) {
            var heading = activePanel.querySelector('h1');
            if (heading) {
                heading.focus();
            }
        }
    }

    function moveScene(offset) {
        var nextIndex = sceneOrder.indexOf(activeScene) + offset;
        if (nextIndex >= 0 && nextIndex < sceneOrder.length) {
            setActiveScene(sceneOrder[nextIndex], true);
        }
    }

    function updateDockProgress(sceneIndex) {
        if (!elements.dockProgressBar) {
            return;
        }
        var progress = ((sceneIndex + 1) / sceneOrder.length * 100) + '%';
        if (window.matchMedia('(max-width: 900px)').matches) {
            elements.dockProgressBar.style.width = progress;
            elements.dockProgressBar.style.height = '100%';
        } else {
            elements.dockProgressBar.style.width = '100%';
            elements.dockProgressBar.style.height = progress;
        }
    }

    function loadMeta() {
        return fetchJson('/api/image-templates/meta').then(function (payload) {
            state.sources = payload.sources || [];
            state.categories = payload.categories || [];
            state.functionCategories = payload.functionCategories || [];
            state.libraryStatus = payload.status || null;
            state.catalogTotal = payload.total || 0;
            state.total = payload.total || 0;
            elements.templateCount.textContent = String(state.total);
            renderMeta();
        });
    }

    function loadTemplatePage(append) {
        var requestSequence = ++listRequestSequence;
        var params = new URLSearchParams();
        params.set('page', String(state.page));
        params.set('size', String(state.size));
        if (state.activeSource) {
            params.set('source', state.activeSource);
        }
        if (state.activeCategory) {
            params.set('category', state.activeCategory);
        }
        if (state.activeFunctionCategory) {
            params.set('functionCategory', state.activeFunctionCategory);
        }
        if (state.activeFunctionScene) {
            params.set('functionScene', state.activeFunctionScene);
        }
        if (state.keyword) {
            params.set('keyword', state.keyword);
        }
        if (state.imageOnly) {
            params.set('imageOnly', 'true');
        }
        elements.listStatus.textContent = append ? '正在加载更多模板…' : '正在检索模板…';
        elements.loadMoreButton.disabled = true;
        if (!append) {
            elements.templateList.innerHTML =
                '<div class="template-card is-skeleton" aria-hidden="true"></div>' +
                '<div class="template-card is-skeleton" aria-hidden="true"></div>';
        }
        return fetchJson('/api/image-templates?' + params.toString())
            .then(function (payload) {
                if (requestSequence !== listRequestSequence) {
                    return;
                }
                var incoming = payload.templates || [];
                state.templates = append ? state.templates.concat(incoming) : incoming;
                state.total = payload.total || 0;
                state.hasMore = Boolean(payload.hasMore);
                elements.templateCount.textContent = String(state.total);
                elements.listStatus.textContent =
                    '已展示 ' + state.templates.length + ' / ' + state.total + ' 条';
                elements.loadMoreButton.hidden = !state.hasMore;
                renderTemplates();
                if (!state.selected && state.templates.length) {
                    return loadTemplateDetail(state.templates[0].id);
                }
            })
            .catch(function (error) {
                if (requestSequence === listRequestSequence) {
                    elements.listStatus.textContent = error.message || '模板列表加载失败。';
                }
                throw error;
            })
            .finally(function () {
                if (requestSequence === listRequestSequence) {
                    elements.loadMoreButton.disabled = false;
                }
            });
    }

    function resetPagination() {
        state.page = 1;
        state.templates = [];
        elements.templateList.innerHTML =
            '<div class="template-card is-skeleton" aria-hidden="true"></div>' +
            '<div class="template-card is-skeleton" aria-hidden="true"></div>';
        return loadTemplatePage(false);
    }

    function renderMeta() {
        renderFunctionFilters();

        var sourceButtons = [
            '<button type="button" class="' + (!state.activeSource ? 'active' : '') +
            '" data-source="">全部 ' + state.catalogTotal + '</button>'
        ];
        state.sources.forEach(function (source) {
            sourceButtons.push(
                '<button type="button" class="' +
                (state.activeSource === source.id ? 'active' : '') +
                '" data-source="' + escapeHtml(source.id) + '">' +
                escapeHtml(source.name) + ' ' + source.count +
                '</button>'
            );
        });
        if (elements.sourceFilters) {
            elements.sourceFilters.innerHTML = sourceButtons.join('');
        }

        var categoryOptions = ['<option value="">全部分类</option>'];
        state.categories.forEach(function (category) {
            categoryOptions.push(
                '<option value="' + escapeHtml(category.slug) + '">' +
                escapeHtml(category.name) + ' · ' + category.count +
                '</option>'
            );
        });
        elements.categorySelect.innerHTML = categoryOptions.join('');
        elements.categorySelect.value = state.activeCategory;

        if (state.libraryStatus && state.libraryStatus.status === 'DEGRADED') {
            elements.libraryAlert.hidden = false;
            elements.libraryAlert.textContent =
                '模板库未完整加载：精选 ' +
                state.libraryStatus.loadedCuratedCount + ' / ' +
                state.libraryStatus.expectedCuratedCount + '，大库 ' +
                state.libraryStatus.loadedLibraryCount + ' / ' +
                state.libraryStatus.expectedLibraryCount + '。' +
                (state.libraryStatus.message ? ' ' + state.libraryStatus.message : '');
        } else {
            elements.libraryAlert.hidden = true;
            elements.libraryAlert.textContent = '';
        }
    }

    function renderFunctionFilters() {
        var categoryButtons = [
            '<button type="button" class="' +
            (!state.activeFunctionCategory ? 'active' : '') +
            '" data-function-category="">全部功能 ' +
            state.catalogTotal + '</button>'
        ];
        state.functionCategories.forEach(function (category) {
            categoryButtons.push(
                '<button type="button" class="' +
                (state.activeFunctionCategory === category.slug ? 'active' : '') +
                '" data-function-category="' + escapeHtml(category.slug) + '">' +
                escapeHtml(category.name) + ' ' + category.count +
                '</button>'
            );
        });
        elements.functionCategoryFilters.innerHTML = categoryButtons.join('');

        var categoryOptions = [
            '<option value="">全部功能 · ' + state.catalogTotal + '</option>'
        ];
        state.functionCategories.forEach(function (category) {
            categoryOptions.push(
                '<option value="' + escapeHtml(category.slug) + '">' +
                escapeHtml(category.name) + ' · ' + category.count +
                '</option>'
            );
        });
        elements.functionCategorySelect.innerHTML = categoryOptions.join('');
        elements.functionCategorySelect.value = state.activeFunctionCategory;

        var selectedCategory = null;
        state.functionCategories.forEach(function (category) {
            if (category.slug === state.activeFunctionCategory) {
                selectedCategory = category;
            }
        });
        if (!selectedCategory) {
            elements.functionSceneFilters.innerHTML = '';
            elements.functionSceneFilters.hidden = true;
            return;
        }

        var sceneButtons = [
            '<button type="button" class="' +
            (!state.activeFunctionScene ? 'active' : '') +
            '" data-function-scene="">全部场景 ' +
            selectedCategory.count + '</button>'
        ];
        (selectedCategory.scenes || []).forEach(function (scene) {
            sceneButtons.push(
                '<button type="button" class="' +
                (state.activeFunctionScene === scene.slug ? 'active' : '') +
                '" data-function-scene="' + escapeHtml(scene.slug) + '">' +
                escapeHtml(scene.name) + ' ' + scene.count +
                '</button>'
            );
        });
        elements.functionSceneFilters.innerHTML = sceneButtons.join('');
        elements.functionSceneFilters.hidden = false;
    }

    function selectFunctionCategory(categorySlug) {
        state.activeFunctionCategory = categorySlug || '';
        state.activeFunctionScene = '';
        renderMeta();
        return resetPagination();
    }

    function clearFilters() {
        state.activeSource = '';
        state.activeCategory = '';
        state.activeFunctionCategory = '';
        state.activeFunctionScene = '';
        state.keyword = '';
        state.imageOnly = false;
        elements.keywordInput.value = '';
        elements.categorySelect.value = '';
        elements.imageOnlyToggle.checked = false;
        renderMeta();
        return resetPagination();
    }

    function renderTemplates() {
        if (!state.templates.length) {
            elements.templateList.innerHTML =
                '<div class="template-empty"><h3>没有匹配结果</h3>' +
                '<p>调整功能、场景或关键词后重试。</p>' +
                '<button type="button" data-clear-filters>清除筛选</button></div>';
            return;
        }
        elements.templateList.innerHTML = state.templates.map(function (template) {
            var tags = (template.tags || []).slice(0, 4).map(function (tag) {
                return '<span>' + escapeHtml(tag) + '</span>';
            }).join('');
            var badges =
                '<span class="template-badge">' +
                escapeHtml(template.functionCategory || '其他工具') +
                '</span>' +
                '<span class="template-badge is-scene">' +
                escapeHtml(template.functionScene || '通用提示词') +
                '</span>' +
                (template.imageRelated
                    ? ''
                    : '<span class="template-badge is-general">通用提示词</span>');
            return '<button type="button" class="template-card ' + (state.selected && state.selected.id === template.id ? 'active' : '') + '" data-id="' + escapeHtml(template.id) + '">' +
                '<div class="template-badges">' + badges + '</div>' +
                '<h3>' + escapeHtml(template.title) + '</h3>' +
                '<p>' + escapeHtml(template.summary) + '</p>' +
                '<small class="template-source">' +
                escapeHtml(template.sourceName || '未知来源') + '</small>' +
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
            elements.jsonTemplate.value = '{}';
            state.jsonTemplateEdited = false;
            resetJsonTemplateStatus();
            elements.promptTemplate.textContent = '';
            elements.variablesInput.value = '{}';
            elements.variablesInput.disabled = false;
            elements.renderedPrompt.value = '';
            state.renderedPromptEdited = false;
            resetGeneratedImage();
            return;
        }
        elements.detailCategory.textContent =
            (template.functionCategory || '其他工具') + ' · ' +
            (template.functionScene || '通用提示词') + ' ｜ ' +
            (template.sourceName || '未知来源');
        elements.detailTitle.textContent = template.title;
        elements.detailSummary.textContent = template.summary;
        elements.jsonTemplate.value = JSON.stringify(template.jsonTemplate, null, 2);
        state.jsonTemplateEdited = false;
        resetJsonTemplateStatus();
        elements.promptTemplate.textContent = template.promptTemplate;
        var direct = template.templateKind === 'DIRECT';
        elements.variablesInput.disabled = false;
        if (direct) {
            elements.variablesInput.value = '{}';
            elements.renderedPrompt.value = template.promptTemplate || '';
        } else {
            elements.variablesInput.value = buildVariableSeed(template.jsonTemplate);
            elements.renderedPrompt.value = '';
        }
        state.renderedPromptEdited = false;
        if (!template.imageRelated) {
            elements.statusLine.textContent = '这是通用提示词，请先调整为适合图片生成的描述。';
        }
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

    function resetJsonTemplateStatus() {
        elements.jsonTemplate.removeAttribute('aria-invalid');
        elements.jsonTemplate.classList.remove('is-invalid');
        elements.jsonTemplateStatus.textContent =
            '可直接修改；进入 Prompt 编导台时会同步到变量剧本。';
    }

    function syncJsonTemplateToVariables() {
        if (!state.jsonTemplateEdited) {
            return true;
        }
        var editedTemplate;
        try {
            editedTemplate = JSON.parse(elements.jsonTemplate.value || '{}');
        } catch (error) {
            elements.jsonTemplate.setAttribute('aria-invalid', 'true');
            elements.jsonTemplate.classList.add('is-invalid');
            elements.jsonTemplateStatus.textContent = 'JSON 格式不正确，请修正后再进入编导台。';
            elements.jsonTemplate.focus();
            return false;
        }
        if (!editedTemplate || Array.isArray(editedTemplate) || typeof editedTemplate !== 'object') {
            elements.jsonTemplate.setAttribute('aria-invalid', 'true');
            elements.jsonTemplate.classList.add('is-invalid');
            elements.jsonTemplateStatus.textContent = 'JSON 模板的最外层必须是对象。';
            elements.jsonTemplate.focus();
            return false;
        }
        elements.variablesInput.value = JSON.stringify(editedTemplate, null, 2);
        elements.jsonTemplate.removeAttribute('aria-invalid');
        elements.jsonTemplate.classList.remove('is-invalid');
        elements.jsonTemplateStatus.textContent = '已同步到 Prompt 编导台的变量剧本。';
        state.jsonTemplateEdited = false;
        return true;
    }

    function loadTemplateDetail(id) {
        var requestSequence = ++detailRequestSequence;
        elements.statusLine.textContent = '正在读取完整模板…';
        return fetchJson('/api/image-templates/' + encodeURIComponent(id))
            .then(function (payload) {
                if (requestSequence !== detailRequestSequence) {
                    return;
                }
                state.selected = payload.template || null;
                renderTemplates();
                renderDetail();
            })
            .catch(function (error) {
                if (requestSequence === detailRequestSequence) {
                    elements.statusLine.textContent =
                        (error.message || '模板详情加载失败') + '，请重试。';
                }
            });
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
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(function () {
            resetPagination().catch(function () {
                elements.libraryAlert.hidden = false;
                elements.libraryAlert.textContent = '模板搜索失败，请稍后重试。';
            });
        }, SEARCH_DEBOUNCE_MS);
    });

    elements.functionCategoryFilters.addEventListener('click', function (event) {
        var button = event.target.closest('button[data-function-category]');
        if (!button) {
            return;
        }
        selectFunctionCategory(
            button.getAttribute('data-function-category')
        ).catch(function () {
            elements.libraryAlert.hidden = false;
            elements.libraryAlert.textContent = '功能分类筛选失败，请稍后重试。';
        });
    });

    elements.functionCategorySelect.addEventListener('change', function () {
        selectFunctionCategory(elements.functionCategorySelect.value)
            .catch(function () {
                elements.libraryAlert.hidden = false;
                elements.libraryAlert.textContent = '功能分类筛选失败，请稍后重试。';
            });
    });

    elements.functionSceneFilters.addEventListener('click', function (event) {
        var button = event.target.closest('button[data-function-scene]');
        if (!button) {
            return;
        }
        state.activeFunctionScene =
            button.getAttribute('data-function-scene') || '';
        renderMeta();
        resetPagination().catch(function () {
            elements.libraryAlert.hidden = false;
            elements.libraryAlert.textContent = '功能场景筛选失败，请稍后重试。';
        });
    });

    if (elements.sourceFilters) {
        elements.sourceFilters.addEventListener('click', function (event) {
            var button = event.target.closest('button[data-source]');
            if (!button) {
                return;
            }
            state.activeSource = button.getAttribute('data-source') || '';
            renderMeta();
            resetPagination().catch(function () {
                elements.libraryAlert.hidden = false;
                elements.libraryAlert.textContent = '来源筛选失败，请稍后重试。';
            });
        });
    }

    elements.categorySelect.addEventListener('change', function () {
        state.activeCategory = elements.categorySelect.value;
        resetPagination().catch(function () {
            elements.libraryAlert.hidden = false;
            elements.libraryAlert.textContent = '分类筛选失败，请稍后重试。';
        });
    });

    elements.imageOnlyToggle.addEventListener('change', function () {
        state.imageOnly = elements.imageOnlyToggle.checked;
        resetPagination().catch(function () {
            elements.libraryAlert.hidden = false;
            elements.libraryAlert.textContent = '图片相关筛选失败，请稍后重试。';
        });
    });

    elements.clearFiltersButton.addEventListener('click', function () {
        clearFilters().catch(function () {
            elements.libraryAlert.hidden = false;
            elements.libraryAlert.textContent = '清除筛选失败，请稍后重试。';
        });
    });

    elements.loadMoreButton.addEventListener('click', function () {
        var previousPage = state.page;
        state.page += 1;
        loadTemplatePage(true).catch(function () {
            state.page = previousPage;
        });
    });

    elements.templateList.addEventListener('click', function (event) {
        var clearButton = event.target.closest('button[data-clear-filters]');
        if (clearButton) {
            clearFilters();
            return;
        }
        var button = event.target.closest('button[data-id]');
        if (button) {
            loadTemplateDetail(button.getAttribute('data-id'));
        }
    });

    elements.templateList.addEventListener('dblclick', function (event) {
        var button = event.target.closest('button[data-id]');
        if (!button) {
            return;
        }
        var id = button.getAttribute('data-id');
        loadTemplateDetail(id).then(function () {
            if (state.selected && state.selected.id === id) {
                setActiveScene('deconstruct', true);
            }
        });
    });

    elements.jsonTemplate.addEventListener('input', function () {
        state.jsonTemplateEdited = true;
        elements.jsonTemplate.removeAttribute('aria-invalid');
        elements.jsonTemplate.classList.remove('is-invalid');
        elements.jsonTemplateStatus.textContent = '内容已修改；进入 Prompt 编导台时会同步。';
    });

    document.addEventListener('click', function (event) {
        var sceneTarget = event.target.closest('[data-scene-target]');
        if (sceneTarget) {
            setActiveScene(sceneTarget.getAttribute('data-scene-target'), true);
        }
    });
    elements.scenePrevButton.addEventListener('click', function () {
        moveScene(-1);
    });
    elements.sceneNextButton.addEventListener('click', function () {
        moveScene(1);
    });
    window.addEventListener('resize', function () {
        updateDockProgress(sceneOrder.indexOf(activeScene));
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
    setActiveScene('discover', false);

    loadMeta().then(function () {
        return loadTemplatePage(false);
    }).catch(function (error) {
        elements.libraryAlert.hidden = false;
        elements.libraryAlert.textContent = error.message || '模板库加载失败。';
        elements.listStatus.textContent = '模板加载失败。';
    });
})();
