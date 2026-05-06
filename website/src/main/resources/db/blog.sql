-- Blog micro app schema and seed data.
-- Target database: website module MySQL database, currently ycx_pms.

create table if not exists auth_user (
    id bigint primary key auto_increment,
    username varchar(64) not null unique,
    display_name varchar(100) not null,
    password_hash varchar(100) not null,
    role varchar(40) not null default 'USER',
    enabled tinyint(1) not null default 1,
    created_at datetime not null default current_timestamp,
    updated_at datetime not null default current_timestamp on update current_timestamp
) charset = utf8mb4;

create table if not exists blog_article (
    id bigint primary key auto_increment,
    title varchar(160) not null,
    slug varchar(180) not null unique,
    summary varchar(500) not null,
    content_html text not null,
    category varchar(80) not null,
    tags varchar(300) not null,
    author_id bigint null,
    author_username varchar(64) null,
    author_display_name varchar(100) null,
    word_count int not null default 0,
    read_minutes int not null default 1,
    published_at datetime not null,
    created_at datetime not null default current_timestamp,
    updated_at datetime not null default current_timestamp on update current_timestamp,
    key idx_blog_article_published_at (published_at),
    key idx_blog_article_category (category)
) charset = utf8mb4;

-- 管理员账号设计：
-- 1. 先通过前端注册普通账号。
-- 2. 再把指定账号提升为管理员，例如：
-- update auth_user set role = 'ADMIN' where username = 'xixi';
-- ADMIN 可以编辑和删除所有文章；USER 只能编辑和删除自己创建的文章。

insert into blog_article (
    title,
    slug,
    summary,
    content_html,
    category,
    tags,
    word_count,
    read_minutes,
    published_at
) values (
    '如何搭建一个完整的个人网站',
    'build-personal-site',
    '从主页入口、静态资源组织和微应用拆分三个层面，梳理个人网站的演进方式。',
    '<h2>微应用拆分</h2><p>个人网站不需要一开始就做成复杂系统。主页负责聚合入口，博客、相册、小游戏等功能按目录拆分，既方便维护，也方便后续独立部署。</p><h2>资源约定</h2><p>当前项目的 website 模块以静态资源为主。博客页面放在 static/blog 下，CSS 和 JavaScript 与页面同目录维护，后端通过 /api/blog 提供数据。</p><h2>后续方向</h2><ul><li>增加 Markdown 解析</li><li>接入文章管理接口</li><li>把文章元数据保存到 MySQL</li><li>增加 RSS 和站点地图</li></ul>',
    '建站相关',
    'Web,Spring Boot,静态页面',
    1320,
    6,
    '2026-05-05 09:00:00'
) on duplicate key update
    title = values(title),
    summary = values(summary),
    content_html = values(content_html),
    category = values(category),
    tags = values(tags),
    word_count = values(word_count),
    read_minutes = values(read_minutes),
    published_at = values(published_at);

insert into blog_article (
    title,
    slug,
    summary,
    content_html,
    category,
    tags,
    word_count,
    read_minutes,
    published_at
) values (
    '网页布局与 CSS 盒子模型',
    'frontend-box-model',
    '理解盒子模型、间距和响应式约束，是做稳定页面布局的基础。',
    '<h2>盒子模型</h2><p>页面上的元素都可以看成盒子。内容、内边距、边框和外边距共同决定它在布局中的实际占用空间。</p><h2>响应式约束</h2><p>固定宽度只适合少量工具面板。页面主体更适合使用 minmax、clamp、grid 和 flex，让内容在不同屏幕上自然重排。</p>',
    '前端开发',
    'CSS,布局,浏览器',
    860,
    4,
    '2026-04-20 10:00:00'
) on duplicate key update
    title = values(title),
    summary = values(summary),
    content_html = values(content_html),
    category = values(category),
    tags = values(tags),
    word_count = values(word_count),
    read_minutes = values(read_minutes),
    published_at = values(published_at);

insert into blog_article (
    title,
    slug,
    summary,
    content_html,
    category,
    tags,
    word_count,
    read_minutes,
    published_at
) values (
    '使用 Git 管理个人项目代码',
    'git-workflow',
    '个人项目也需要稳定的提交习惯，最小可用流程是分支、提交、拉取和推送。',
    '<h2>保持工作区可解释</h2><p>提交前先看 git status，确认变更都来自当前任务。不要把构建产物、IDE 缓存和真实密钥放进提交。</p><h2>提交粒度</h2><p>一次提交最好对应一个明确目标。这样回滚、审查和定位问题都更直接。</p>',
    '技术教程',
    'Git,Github,工程化',
    980,
    5,
    '2026-03-18 11:00:00'
) on duplicate key update
    title = values(title),
    summary = values(summary),
    content_html = values(content_html),
    category = values(category),
    tags = values(tags),
    word_count = values(word_count),
    read_minutes = values(read_minutes),
    published_at = values(published_at);
