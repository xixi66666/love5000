            <script>
            function logout() {
                if (confirm('确定要退出吗？')) {
                    sessionStorage.removeItem('isLoggedIn');
                    sessionStorage.removeItem('loginTime');
                    window.location.href = '/login.html';
                }
            }

            // ----------------------------------------------------
            // ★★★ 请在这里修改你们的纪念日 ★★★
            const startDate = new Date("2025-09-21T00:00:00");
            // ----------------------------------------------------

            function updateTimer() {
                const now = new Date();
                const diff = now - startDate;

                const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
                const minutes = Math.floor((diff / 1000 / 60) % 60);
                const seconds = Math.floor((diff / 1000) % 60);

                document.getElementById("timer").innerHTML =
                    `${days} <span style="font-size:1rem">天</span>
            ${hours} <span style="font-size:1rem">小时</span>
            ${minutes} <span style="font-size:1rem">分</span>
            ${seconds} <span style="font-size:1rem">秒</span>`;
            }

            setInterval(updateTimer, 1000);
            updateTimer(); // 初始化

            // 页面DOM加载完成后执行
            document.addEventListener('DOMContentLoaded', function() {
                // 浪漫情话生成器功能
                const loveQuotes = [
                    "我爱你，不是因为你是一个怎样的人，而是因为我喜欢与你在一起时的感觉。",
                    "和你在一起的每一天，都是我最珍贵的记忆。",
                    "我想和你一起看遍世间美景，尝遍天下美食，直到白头。",
                    "你的笑容是我每天最大的动力。",
                    "无论未来怎样，只要有你在身边，我就无所畏惧。",
                    "你是我生命中最美的意外，也是最珍贵的礼物。",
                    "愿得一人心，白首不相离。",
                    "与你相遇，是我此生最幸运的事。",
                    "爱不是彼此凝视，而是一起朝着同一个方向眺望。",
                    "时光静好，与君语；细水流年，与君同；繁华落尽，与君老。",
                    // ★★★ 在这里添加你们自己的情话 ★★★
                    // 例如："第一次见你的时候，我的心就告诉我，就是你了。"
                    // 每行一个情话，用逗号分隔
                ];

                const loveQuoteDisplay = document.getElementById('loveQuoteDisplay');
                const loveQuoteText = document.getElementById('loveQuoteText');
                const loveQuoteBtn = document.getElementById('loveQuoteBtn');
                const loveQuoteClose = document.getElementById('loveQuoteClose');

                function showRandomLoveQuote() {
                    const randomIndex = Math.floor(Math.random() * loveQuotes.length);
                    loveQuoteText.textContent = loveQuotes[randomIndex];
                    loveQuoteDisplay.classList.add('show');

                    // 5秒后自动隐藏
                    clearTimeout(loveQuoteDisplay.timeoutId);
                    loveQuoteDisplay.timeoutId = setTimeout(() => {
                        loveQuoteDisplay.classList.remove('show');
                    }, 5000);
                }

                loveQuoteBtn.addEventListener('click', showRandomLoveQuote);

                loveQuoteClose.addEventListener('click', function() {
                    loveQuoteDisplay.classList.remove('show');
                    clearTimeout(loveQuoteDisplay.timeoutId);
                });

                // 点击情话显示区域外部关闭
                document.addEventListener('click', function(event) {
                    if (!loveQuoteDisplay.contains(event.target) && event.target !== loveQuoteBtn) {
                        loveQuoteDisplay.classList.remove('show');
                        clearTimeout(loveQuoteDisplay.timeoutId);
                    }
                });

                // 初始显示一条情话（延迟2秒）
                setTimeout(() => {
                    showRandomLoveQuote();
                }, 2000);

                // 交互式照片墙功能
                const galleryItems = document.querySelectorAll('.gallery-item');
                const filterButtons = document.querySelectorAll('.filter-btn');
                const lightbox = document.getElementById('lightbox');
                const lightboxImage = document.getElementById('lightboxImage');
                const lightboxDescription = document.getElementById('lightboxDescription');
                const lightboxCounter = document.getElementById('lightboxCounter');
                const lightboxClose = document.getElementById('lightboxClose');
                const lightboxPrev = document.getElementById('lightboxPrev');
                const lightboxNext = document.getElementById('lightboxNext');

                let currentImageIndex = 0;
                let filteredItems = Array.from(galleryItems);

                // 筛选功能
                filterButtons.forEach(button => {
                    button.addEventListener('click', () => {
                        const filter = button.getAttribute('data-filter');

                        // 更新活动按钮
                        filterButtons.forEach(btn => btn.classList.remove('active'));
                        button.classList.add('active');

                        // 筛选项目
                        galleryItems.forEach(item => {
                            if (filter === 'all' || item.getAttribute('data-category') === filter) {
                                item.style.display = 'block';
                                setTimeout(() => {
                                    item.style.opacity = '1';
                                    item.style.transform = 'scale(1)';
                                }, 10);
                            } else {
                                item.style.opacity = '0';
                                item.style.transform = 'scale(0.8)';
                                setTimeout(() => {
                                    item.style.display = 'none';
                                }, 300);
                            }
                        });

                        // 更新筛选后的项目列表
                        filteredItems = Array.from(galleryItems).filter(item => {
                            return filter === 'all' || item.getAttribute('data-category') === filter;
                        });
                    });
                });

                // Lightbox 功能
                function openLightbox(index) {
                    currentImageIndex = index;
                    updateLightbox();
                    lightbox.classList.add('show');
                    document.body.style.overflow = 'hidden';
                }

                function closeLightbox() {
                    lightbox.classList.remove('show');
                    document.body.style.overflow = 'auto';
                }

                function updateLightbox() {
                    if (filteredItems.length === 0) return;

                    const currentItem = filteredItems[currentImageIndex];
                    const img = currentItem.querySelector('img');
                    const description = img.getAttribute('data-description');

                    lightboxImage.src = img.src;
                    lightboxImage.alt = img.alt;
                    lightboxDescription.textContent = description;
                    lightboxCounter.textContent = `${currentImageIndex + 1} / ${filteredItems.length}`;
                }

                function showNextImage() {
                    currentImageIndex = (currentImageIndex + 1) % filteredItems.length;
                    updateLightbox();
                }

                function showPrevImage() {
                    currentImageIndex = (currentImageIndex - 1 + filteredItems.length) % filteredItems.length;
                    updateLightbox();
                }

                // 点击图片打开 Lightbox
                galleryItems.forEach((item, index) => {
                    item.addEventListener('click', () => {
                        // 获取在筛选列表中的索引
                        const filter = document.querySelector('.filter-btn.active').getAttribute('data-filter');
                        const currentFiltered = filter === 'all'
                            ? Array.from(galleryItems)
                            : Array.from(galleryItems).filter(item => item.getAttribute('data-category') === filter);

                        const filteredIndex = currentFiltered.indexOf(item);
                        if (filteredIndex !== -1) {
                            openLightbox(filteredIndex);
                        }
                    });
                });

                // Lightbox 控制
                lightboxClose.addEventListener('click', closeLightbox);
                lightboxPrev.addEventListener('click', showPrevImage);
                lightboxNext.addEventListener('click', showNextImage);

                // 键盘导航
                document.addEventListener('keydown', (e) => {
                    if (!lightbox.classList.contains('show')) return;

                    switch(e.key) {
                        case 'Escape':
                            closeLightbox();
                            break;
                        case 'ArrowLeft':
                            showPrevImage();
                            break;
                        case 'ArrowRight':
                            showNextImage();
                            break;
                    }
                });

                // 点击 Lightbox 背景关闭
                lightbox.addEventListener('click', (e) => {
                    if (e.target === lightbox) {
                        closeLightbox();
                    }
                });

                // 触摸滑动支持（移动端）
                let touchStartX = 0;
                let touchEndX = 0;

                lightbox.addEventListener('touchstart', (e) => {
                    touchStartX = e.changedTouches[0].screenX;
                });

                lightbox.addEventListener('touchend', (e) => {
                    touchEndX = e.changedTouches[0].screenX;
                    handleSwipe();
                });

                function handleSwipe() {
                    const swipeThreshold = 50;
                    const diff = touchStartX - touchEndX;

                    if (Math.abs(diff) > swipeThreshold) {
                        if (diff > 0) {
                            showNextImage();
                        } else {
                            showPrevImage();
                        }
                    }
                }

                // 恋爱里程碑成就系统
                const achievementsData = [
                    {
                        id: 'day7',
                        title: '第一周',
                        description: '相爱满一周，甜蜜的开始',
                        icon: '🌱',
                        daysRequired: 7,
                        date: null
                    },
                    {
                        id: 'day30',
                        title: '满月纪念',
                        description: '相爱一个月，每一天都想你',
                        icon: '🌙',
                        daysRequired: 30,
                        date: null
                    },
                    {
                        id: 'day100',
                        title: '百日纪念',
                        description: '100天啦！我们的爱在成长',
                        icon: '💯',
                        daysRequired: 100,
                        date: null
                    },
                    {
                        id: 'day200',
                        title: '双百纪念',
                        description: '200天，爱你比昨天更多一点',
                        icon: '💖',
                        daysRequired: 200,
                        date: null
                    },
                    {
                        id: 'day365',
                        title: '一周年',
                        description: '相爱一整年！未来的每一年都要一起过',
                        icon: '🎉',
                        daysRequired: 365,
                        date: null
                    },
                    {
                        id: 'day500',
                        title: '五百天',
                        description: '500个日夜，爱你如初',
                        icon: '🌟',
                        daysRequired: 500,
                        date: null
                    },
                    {
                        id: 'day730',
                        title: '两周年',
                        description: '两年时光，爱你依旧',
                        icon: '💑',
                        daysRequired: 730,
                        date: null
                    },
                    // ★★★ 在这里添加自定义成就 ★★★
                    // {
                    //     id: 'custom',
                    //     title: '自定义成就',
                    //     description: '你们的特殊纪念日',
                    //     icon: '❤️',
                    //     daysRequired: 0,
                    //     date: '2023-06-01' // 特殊日期（YYYY-MM-DD格式）
                    // }
                ];

                const achievementsGrid = document.getElementById('achievementsGrid');
                const achievementDaysCounter = document.getElementById('achievementDaysCounter');

                // 计算恋爱天数
                function calculateLoveDays() {
                    const now = new Date();
                    const diff = now - startDate;
                    return Math.floor(diff / (1000 * 60 * 60 * 24));
                }

                // 初始化成就系统
                function initAchievements() {
                    const loveDays = calculateLoveDays();
                    achievementDaysCounter.textContent = `恋爱天数：${loveDays} 天`;

                    // 获取已解锁的成就（从localStorage）
                    const unlockedAchievements = JSON.parse(localStorage.getItem('unlockedAchievements') || '{}');

                    achievementsGrid.innerHTML = '';
                    achievementsData.forEach(achievement => {
                        const isUnlocked = checkAchievementUnlocked(achievement, loveDays, unlockedAchievements);
                        const achievementCard = createAchievementCard(achievement, isUnlocked);
                        achievementsGrid.appendChild(achievementCard);

                        // 如果成就刚解锁，播放动画
                        if (isUnlocked && !unlockedAchievements[achievement.id]) {
                            unlockAchievement(achievement, achievementCard);
                            unlockedAchievements[achievement.id] = new Date().toISOString();
                        }
                    });

                    // 保存已解锁成就
                    localStorage.setItem('unlockedAchievements', JSON.stringify(unlockedAchievements));
                }

                // 检查成就是否解锁
                function checkAchievementUnlocked(achievement, loveDays, unlockedAchievements) {
                    // 如果已经有记录，则已解锁
                    if (unlockedAchievements[achievement.id]) {
                        return true;
                    }

                    // 检查天数条件
                    if (achievement.daysRequired > 0 && loveDays >= achievement.daysRequired) {
                        return true;
                    }

                    // 检查特殊日期条件
                    if (achievement.date) {
                        const specialDate = new Date(achievement.date);
                        const today = new Date();
                        if (specialDate.getDate() === today.getDate() &&
                            specialDate.getMonth() === today.getMonth() &&
                            specialDate.getFullYear() === today.getFullYear()) {
                            return true;
                        }
                    }

                    return false;
                }

                // 创建成就卡片
                function createAchievementCard(achievement, isUnlocked) {
                    const card = document.createElement('div');
                    card.className = `achievement-card ${isUnlocked ? 'unlocked' : 'locked'}`;
                    card.innerHTML = `
                    ${!isUnlocked ? '<div class="achievement-lock">🔒</div>' : ''}
                    <div class="achievement-icon">${achievement.icon}</div>
                    <div class="achievement-title">${achievement.title}</div>
                    <div class="achievement-desc">${achievement.description}</div>
                    <div class="achievement-date">${achievement.daysRequired > 0 ? `第 ${achievement.daysRequired} 天` : '特殊纪念日'}</div>
                `;
                    return card;
                }

                // 解锁成就效果
                function unlockAchievement(achievement, card) {
                    const effect = document.createElement('div');
                    effect.className = 'achievement-unlock-effect';
                    card.appendChild(effect);

                    // 播放音效（可选）
                    try {
                        const audio = new Audio('https://assets.mixkit.co/sfx/preview/mixkit-winning-chimes-2015.mp3');
                        audio.volume = 0.3;
                        audio.play();
                    } catch (e) {
                        // 忽略音效错误
                    }

                    // 3秒后移除效果元素
                    setTimeout(() => {
                        if (effect.parentNode) {
                            effect.remove();
                        }
                    }, 3000);
                }

                // 页面加载时初始化成就系统
                initAchievements();

                // 每天检查一次成就
                setInterval(() => {
                    initAchievements();
                }, 24 * 60 * 60 * 1000); // 24小时

                // 秘密留言板功能
                const secretTrigger = document.getElementById('secretTrigger');
                const secretBoard = document.getElementById('secretBoard');
                const secretBoardClose = document.getElementById('secretBoardClose');
                const secretMessages = document.getElementById('secretMessages');
                const secretMessageInput = document.getElementById('secretMessageInput');
                const secretSendBtn = document.getElementById('secretSendBtn');
                const secretClearBtn = document.getElementById('secretClearBtn');
                const charCounter = document.getElementById('charCounter');

                // 留言存储键
                const MESSAGES_KEY = 'secret_love_messages';

                // 双击触发打开留言板
                let clickCount = 0;
                let clickTimer = null;

                secretTrigger.addEventListener('click', function(e) {
                    clickCount++;

                    if (clickCount === 1) {
                        clickTimer = setTimeout(() => {
                            clickCount = 0;
                        }, 300); // 300毫秒内算双击
                    } else if (clickCount === 2) {
                        clearTimeout(clickTimer);
                        clickCount = 0;
                        openSecretBoard();
                    }
                });

                // 打开留言板
                function openSecretBoard() {
                    secretBoard.classList.add('show');
                    document.body.style.overflow = 'hidden';
                    loadMessages();
                    secretMessageInput.focus();
                }

                // 关闭留言板
                function closeSecretBoard() {
                    secretBoard.classList.remove('show');
                    document.body.style.overflow = 'auto';
                    secretMessageInput.value = '';
                    updateCharCounter();
                }

                // 加载留言
                function loadMessages() {
                    const messages = getMessages();
                    secretMessages.innerHTML = '';

                    if (messages.length === 0) {
                        secretMessages.innerHTML = '<div class="no-messages">还没有留言，写下第一条吧！</div>';
                        return;
                    }

                    messages.forEach((msg, index) => {
                        const messageElement = document.createElement('div');
                        messageElement.className = 'secret-message';
                        messageElement.innerHTML = `
                        <div class="secret-message-text">${escapeHtml(msg.text)}</div>
                        <div class="secret-message-date">${formatDate(msg.date)}</div>
                    `;
                        secretMessages.appendChild(messageElement);
                    });

                    // 滚动到底部
                    secretMessages.scrollTop = secretMessages.scrollHeight;
                }

                // 保存留言
                function saveMessage(text) {
                    if (!text.trim()) return false;

                    const messages = getMessages();
                    const newMessage = {
                        text: text.trim(),
                        date: new Date().toISOString()
                    };

                    messages.push(newMessage);
                    localStorage.setItem(MESSAGES_KEY, JSON.stringify(messages));
                    return true;
                }

                // 获取留言列表
                function getMessages() {
                    try {
                        const messages = localStorage.getItem(MESSAGES_KEY);
                        return messages ? JSON.parse(messages) : [];
                    } catch (e) {
                        return [];
                    }
                }

                // 清空留言
                function clearMessages() {
                    if (confirm('确定要清空所有留言吗？此操作不可撤销。')) {
                        localStorage.removeItem(MESSAGES_KEY);
                        loadMessages();
                    }
                }

                // 更新字符计数器
                function updateCharCounter() {
                    const length = secretMessageInput.value.length;
                    charCounter.textContent = `${length}/200`;

                    if (length > 180) {
                        charCounter.style.color = '#ff6b81';
                    } else if (length > 150) {
                        charCounter.style.color = '#ffa500';
                    } else {
                        charCounter.style.color = '#888';
                    }
                }

                // 发送留言
                function sendMessage() {
                    const text = secretMessageInput.value.trim();

                    if (!text) {
                        alert('请输入留言内容');
                        secretMessageInput.focus();
                        return;
                    }

                    if (text.length > 200) {
                        alert('留言不能超过200字');
                        return;
                    }

                    if (saveMessage(text)) {
                        secretMessageInput.value = '';
                        updateCharCounter();
                        loadMessages();

                        // 轻微动画反馈
                        secretSendBtn.textContent = '已发送 💖';
                        setTimeout(() => {
                            secretSendBtn.textContent = '发送 💌';
                        }, 1500);
                    }
                }

                // 格式化日期
                function formatDate(dateString) {
                    const date = new Date(dateString);
                    const now = new Date();
                    const diffMs = now - date;
                    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

                    if (diffDays === 0) {
                        return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
                    } else if (diffDays === 1) {
                        return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
                    } else if (diffDays < 7) {
                        return `${diffDays}天前`;
                    } else {
                        return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')}`;
                    }
                }

                // HTML转义（防止XSS）
                function escapeHtml(text) {
                    const div = document.createElement('div');
                    div.textContent = text;
                    return div.innerHTML;
                }

                // 事件监听器
                secretBoardClose.addEventListener('click', closeSecretBoard);
                secretSendBtn.addEventListener('click', sendMessage);
                secretClearBtn.addEventListener('click', clearMessages);

                secretMessageInput.addEventListener('input', updateCharCounter);
                secretMessageInput.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                    }
                });

                // 点击留言板外部关闭
                secretBoard.addEventListener('click', function(e) {
                    if (e.target === secretBoard) {
                        closeSecretBoard();
                    }
                });

                // 键盘快捷键
                document.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape' && secretBoard.classList.contains('show')) {
                        closeSecretBoard();
                    }
                });

                // 初始加载字符计数器
                updateCharCounter();

                // ========== 卡片翻转功能 ==========
                window.flipCard = function(card) {
                    card.classList.toggle('flipped');
                };

                // 将函数暴露到全局作用域
                window.flipCard = flipCard;
                window.shuffleCards = shuffleCards;


                // ========== 卡片洗牌功能 ==========
                window.shuffleCards = function() {
                    const cardsStack = document.getElementById('cardsStack');
                    if (!cardsStack) return;

                    const cards = Array.from(cardsStack.querySelectorAll('.memory-card'));

                    // 重置所有卡片
                    cards.forEach(card => {
                        card.classList.remove('flipped');
                        card.style.transition = 'all 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55)';
                    });

                    // 随机打乱顺序
                    for (let i = cards.length - 1; i > 0; i--) {
                        const j = Math.floor(Math.random() * (i + 1));
                        [cards[i], cards[j]] = [cards[j], cards[i]];
                    }

                    // 重新添加到DOM
                    cards.forEach((card, index) => {
                        setTimeout(() => {
                            cardsStack.appendChild(card);
                        }, index * 100);
                    });
                };



                updateCharCounter();

                // ========== 照片上传功能 ==========
                const uploadTrigger = document.getElementById('uploadTrigger');
                const uploadModal = document.getElementById('uploadModal');
                const uploadModalClose = document.getElementById('uploadModalClose');
                const uploadForm = document.getElementById('uploadForm');
                const uploadPreview = document.getElementById('uploadPreview');
                const photoFile = document.getElementById('photoFile');
                const photoCategory = document.getElementById('photoCategory');
                const photoDescription = document.getElementById('photoDescription');
                const uploadSubmitBtn = document.getElementById('uploadSubmitBtn');
                const uploadProgress = document.getElementById('uploadProgress');
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');

                let selectedFile = null;

                // 打开上传模态框
                uploadTrigger.addEventListener('click', function() {
                    uploadModal.classList.add('show');
                    document.body.style.overflow = 'hidden';
                });

                // 关闭上传模态框
                function closeUploadModal() {
                    uploadModal.classList.remove('show');
                    document.body.style.overflow = 'auto';
                    resetUploadForm();
                }

                uploadModalClose.addEventListener('click', closeUploadModal);

                // 点击模态框外部关闭
                uploadModal.addEventListener('click', function(e) {
                    if (e.target === uploadModal) {
                        closeUploadModal();
                    }
                });

                // ESC键关闭
                document.addEventListener('keydown', function(e) {
                    if (e.key === 'Escape' && uploadModal.classList.contains('show')) {
                        closeUploadModal();
                    }
                });

                // 点击预览区域选择文件
                uploadPreview.addEventListener('click', function() {
                    photoFile.click();
                });

                // 文件选择处理
                photoFile.addEventListener('change', function(e) {
                    const file = e.target.files[0];
                    handleFileSelect(file);
                });

                // 拖拽上传
                uploadPreview.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    uploadPreview.style.borderColor = '#ff6b81';
                    uploadPreview.style.background = '#fff5f7';
                });

                uploadPreview.addEventListener('dragleave', function(e) {
                    e.preventDefault();
                    uploadPreview.style.borderColor = '#ddd';
                    uploadPreview.style.background = '#f9f9f9';
                });

                uploadPreview.addEventListener('drop', function(e) {
                    e.preventDefault();
                    uploadPreview.style.borderColor = '#ddd';
                    uploadPreview.style.background = '#f9f9f9';

                    const file = e.dataTransfer.files[0];
                    handleFileSelect(file);
                });

                // 处理文件选择
                function handleFileSelect(file) {
                    if (!file) return;

                    // 验证文件类型
                    if (!file.type.startsWith('image/')) {
                        alert('请选择图片文件');
                        return;
                    }

                    // 验证文件大小（最大10MB）
                    if (file.size > 10 * 1024 * 1024) {
                        alert('图片大小不能超过10MB');
                        return;
                    }

                    selectedFile = file;

                    // 显示预览
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        uploadPreview.innerHTML = `<img src="${e.target.result}" alt="预览">`;
                        uploadPreview.classList.add('has-image');
                        checkUploadReady();
                    };
                    reader.readAsDataURL(file);
                }

                // 检查是否可以上传
                function checkUploadReady() {
                    if (selectedFile && photoCategory.value) {
                        uploadSubmitBtn.disabled = false;
                    } else {
                        uploadSubmitBtn.disabled = true;
                    }
                }

                // 分类变化时检查
                photoCategory.addEventListener('change', checkUploadReady);

                // 重置表单
                function resetUploadForm() {
                    selectedFile = null;
                    photoFile.value = '';
                    photoCategory.value = '';
                    photoDescription.value = '';
                    uploadPreview.innerHTML = `
                        <div class="upload-placeholder">
                            <div class="upload-placeholder-icon">🖼️</div>
                            <div class="upload-placeholder-text">点击选择图片或拖拽到此处</div>
                            <div class="upload-placeholder-hint">支持 JPG、PNG、GIF、WebP 格式</div>
                        </div>
                    `;
                    uploadPreview.classList.remove('has-image');
                    uploadSubmitBtn.disabled = true;
                    uploadProgress.classList.remove('show');
                    progressFill.style.width = '0%';
                }

                // 提交上传
                uploadForm.addEventListener('submit', function(e) {
                    e.preventDefault();

                    if (!selectedFile) {
                        alert('请选择要上传的照片');
                        return;
                    }

                    if (!photoCategory.value) {
                        alert('请选择照片分类');
                        return;
                    }

                    uploadPhoto();
                });

                // 执行上传
                function uploadPhoto() {
                    const formData = new FormData();
                    formData.append('file', selectedFile);
                    formData.append('category', photoCategory.value);
                    formData.append('description', photoDescription.value);

                    // 显示进度条
                    uploadProgress.classList.add('show');
                    uploadSubmitBtn.disabled = true;
                    uploadSubmitBtn.textContent = '上传中...';

                    // 模拟进度（因为XMLHttpRequest的progress事件在某些情况下不可靠）
                    let progress = 0;
                    const progressInterval = setInterval(() => {
                        if (progress < 90) {
                            progress += Math.random() * 10;
                            if (progress > 90) progress = 90;
                            progressFill.style.width = progress + '%';
                            progressText.textContent = `上传中... ${Math.round(progress)}%`;
                        }
                    }, 200);

                    const xhr = new XMLHttpRequest();
                    xhr.open('POST', '/api/photos/upload', true);

                    xhr.onload = function() {
                        clearInterval(progressInterval);

                        if (xhr.status === 200) {
                            try {
                                const response = JSON.parse(xhr.responseText);

                                if (response.success) {
                                    progressFill.style.width = '100%';
                                    progressText.textContent = '上传成功！';

                                    setTimeout(() => {
                                        alert('照片上传成功！');
                                        closeUploadModal();

                                        // 刷新页面以显示新照片（可选）
                                        location.reload();
                                    }, 500);
                                } else {
                                    clearInterval(progressInterval);
                                    alert('上传失败：' + response.message);
                                    uploadSubmitBtn.disabled = false;
                                    uploadSubmitBtn.textContent = '上传照片 📤';
                                    uploadProgress.classList.remove('show');
                                }
                            } catch (e) {
                                clearInterval(progressInterval);
                                alert('上传失败：解析响应错误');
                                uploadSubmitBtn.disabled = false;
                                uploadSubmitBtn.textContent = '上传照片 📤';
                                uploadProgress.classList.remove('show');
                            }
                        } else {
                            clearInterval(progressInterval);
                            alert('上传失败：服务器错误');
                            uploadSubmitBtn.disabled = false;
                            uploadSubmitBtn.textContent = '上传照片 📤';
                            uploadProgress.classList.remove('show');
                        }
                    };

                    xhr.onerror = function() {
                        clearInterval(progressInterval);
                        alert('上传失败：网络错误');
                        uploadSubmitBtn.disabled = false;
                        uploadSubmitBtn.textContent = '上传照片 📤';
                        uploadProgress.classList.remove('show');
                    };

                    xhr.send(formData);
                }
            });
            </script>
