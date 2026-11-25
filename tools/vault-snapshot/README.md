# vault-snapshot

个人资料库（Vault）的独立、离线、可验证快照工具。使用 Python 3.9+ 标准库实现，只扫描显式传入的 Vault，不使用默认用户目录或默认临时目录，不联网，不调用模型 API，也不内置加密或自动排程。

它把 Vault 中的全部普通文件打成一个自包含 ZIP，生成带路径、大小和 SHA-256 的文件清单；`verify` 可随时离线校验清单、成员和摘要，`restore` 只能把归档写到一个全新的目标目录。

> 这是文件级完整性工具，不是经过认证的备份系统。清单与数据放在同一个 ZIP 中，能发现丢失、额外成员和内容损坏，但没有签名，无法阻止能够重写整个归档（含清单）的攻击者。归档不加密。

## 目录

```text
tools/vault-snapshot/
├── pyproject.toml
├── README.md
├── vault_snapshot/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   └── core.py
└── tests/
    └── test_vault_snapshot.py
```

## 快速开始

所有路径都必须显式传入。工具没有默认 Vault、默认用户目录或默认临时目录。

```bash
cd tools/vault-snapshot

# 1. 创建快照：会生成 <WORK_DIR>/vault-snapshot.zip
python -m vault_snapshot create \
  --vault /path/to/vault \
  --work-dir /path/to/explicit-work-dir

# 2. 只读验证
python -m vault_snapshot verify \
  --archive /path/to/explicit-work-dir/vault-snapshot.zip

# 3. 恢复到全新的目录；目标必须不存在
python -m vault_snapshot restore \
  --archive /path/to/explicit-work-dir/vault-snapshot.zip \
  --dest /path/to/new-restored-vault
```

Windows PowerShell 示例：

```powershell
cd tools/vault-snapshot
python -m vault_snapshot create --vault D:\data\Notes `
  --work-dir D:\backups\offline-work
python -m vault_snapshot verify --archive D:\backups\offline-work\vault-snapshot.zip
python -m vault_snapshot restore --archive D:\backups\offline-work\vault-snapshot.zip `
  --dest D:\restores\Notes-2026-01-01
```

环境已经具备打包工具时，也可以选择在本目录中做可编辑安装，获得 `vault-snapshot` 命令：

```bash
# 当前目录：tools/vault-snapshot
python -m pip install -e .
vault-snapshot --help
```

不安装也可以直接使用 `python -m vault_snapshot`。运行时没有第三方依赖；`pyproject.toml` 只用于可选的本地安装。

## 命令约定

### create

```text
python -m vault_snapshot create --vault PATH --work-dir PATH
```

- `--vault`：必须存在的 Vault 目录。
- `--work-dir`：必须存在的目录，用作显式临时位置和最终发布位置；必须位于 Vault 之外。
- 固定发布为 `<work-dir>/vault-snapshot.zip`，不会使用系统临时目录。
- 如果目标 ZIP 已存在，命令拒绝覆盖并退出，已有文件保持不变。需要重新备份时先自行移走旧归档。
- 扫描 Vault 中所有普通文件，包括隐藏文件和非 Markdown 附件。
- 拒绝符号链接、目录符号链接、FIFO、套接字、设备文件等非普通文件；不会跟随符号链接读取 Vault 外部内容。
- 空目录不会被记录。文件的 mtime、权限、ACL、扩展属性、硬链接关系和 Windows ADS 不会保留。
- 先在 `--work-dir` 内创建随机临时 ZIP，完整校验通过后执行原子无覆盖发布：Windows 使用同目录 `os.rename`（目标存在时系统拒绝替换），POSIX 使用同目录 `os.link` 硬链接创建最终名（目标存在时内核返回 `EEXIST`）。
- 因此，即使目标 ZIP 在初始检查后、发布前被其他进程创建为文件或空目录，`create` 也会以稳定错误失败；该路径及其内容保持原样，不会被覆盖或清理。
- 如果工作目录所在文件系统不支持所需的原子无覆盖操作（例如 POSIX 上不支持硬链接），命令返回稳定错误，不会退化为覆盖式重命名；本次临时 ZIP 仍会删除。
- 快照是单次扫描，不提供事务隔离。若 Vault 在创建过程中被其他程序修改，应停止修改后重新创建。

### verify

```text
python -m vault_snapshot verify --archive PATH
```

只读，不发布、不恢复、不写文件。成功返回 `0`；失败会列出发现的问题并以 `1` 退出。报告不输出文件内容。

校验范围：

- ZIP 可读，且只包含 `MANIFEST.json` 和 `files/**` 普通文件成员。
- 清单格式严格、UTF-8、字段齐全，文件路径安全且按确定性顺序排列。
- ZIP 成员不重复、不是目录、不是符号链接、不加密、大小写不冲突。
- 清单与 ZIP 成员一一对应，报告缺失成员、清单外成员和大小差异。
- 对每个文件流式计算 SHA-256，与清单比较，报告 `TAMPERED`。
- 路径必须可编码为 UTF-8，不能绝对、不能含 `..`/`.`、控制字符或 Windows 禁用字符，也不能使用 Windows 的大小写别名、尾随点/空格或保留设备名。

### restore

```text
python -m vault_snapshot restore --archive PATH --dest PATH
```

- `--dest` 必须是**不存在的全新目录**；已存在的文件、目录或失效符号链接一律拒绝，不做覆盖或合并。
- 父目录必须已存在。
- 在目标父目录内创建随机暂存目录，写入文件并再次校验每个文件的大小和 SHA-256。只有全部文件校验通过后，才会开始发布目标路径。
- Windows：用同目录 `os.rename` 原子重命名暂存目录；目标在发布瞬间已存在时该调用失败，不会替换任何文件或目录。
- POSIX：先以 `os.mkdir` 对目标路径做**原子独占预留**，验证预留的 device/inode 身份且确认其为空，再把完整暂存目录以 `os.rename` 原子替换到该空预留上。目标被其他进程提前创建时 `mkdir` 返回 `EEXIST`；预留被替换、被写入内容或最终重命名不可用时，命令失败。
- 任意失败都会删除本次暂存目录。POSIX 预留只有在身份未变且仍为空时才用 `rmdir` 移除；绝不对目标路径做递归删除，也不会删除他人写入的内容。
- 如果文件系统不支持所需的原子无覆盖发布，命令返回稳定错误，不会退化为覆盖式重命名。POSIX 独占预留存在极短暂的可见空目录窗口；这是发布预留，不是已完成的恢复数据。
- 解压只写普通文件，不执行归档中的任何内容。
- 恢复同样拒绝 Windows 大小写碰撞；大小写折叠按完整路径逐级检查，包括目录前缀。

上述发布不依赖“先检查目标不存在、再覆盖”的窗口：初始存在性检查只用于尽快返回参数错误；最终是否可发布由内核级无覆盖操作或独占预留决定。并发保障仅覆盖目标路径的创建/发布；不与其他进程共享锁，也不阻止他人在已成功发布的目录内继续写入。POSIX 目录发布在最后一次复核预留身份与空目录状态后，仍以可移植的 `rename` 替换该空预留；若外部进程恰好在这个极短窗口内主动删除并重建同名空目录，标准库没有可移植的 `RENAME_NOREPLACE` 可以消除该理论窗口。正常的并发创建（文件或空目录）会先被预留阻止。

## 归档格式

```text
vault-snapshot.zip
├── files/path/to/note.md
├── files/path/to/attachment.png
└── MANIFEST.json
```

- 负载路径是相对于 Vault 根目录的 `/` 分隔路径。
- `files/` 下只写普通文件，不写目录条目。
- ZIP 成员顺序是 `files/...` 的确定性顺序，`MANIFEST.json` 最后写入。
- 所有 ZIP 成员的修改时间固定为 `1980-01-01 00:00:00`，文件模式固定；归档不记录本机绝对路径或创建时间。
- `MANIFEST.json` 示例（实际写入为确定性 UTF-8 JSON）：

```json
{
  "files": [
    {
      "path": "notes/alpha.md",
      "sha256": "017b70af1737a855266fc9eb9b3f88917dc972f20d2a1c7d6baa03b85260e8b8",
      "size": 8
    }
  ],
  "format": "vault-snapshot",
  "version": 1
}
```

清单 `files` 按 `path` 的 Unicode 码点升序排列。相同内容、相同 Python/zlib 运行环境下，生成的归档字节可复现；测试亦覆盖这一点。创建时间没有写入归档，因此确定性和隐私都更好。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 创建、验证或恢复成功 |
| `1` | 归档校验失败、内容被篡改、恢复失败或运行时 I/O 失败 |
| `2` | 参数或路径不合法，例如缺少参数、Vault/工作目录不存在、目标已存在 |

命令开始前已存在的目标按路径不合法返回 `2`。若目标是在初始检查之后、发布之前才被其他进程创建，则由原子发布步骤检测，按运行时失败返回 `1`，且不会改动对方路径。原子发布冲突或文件系统不支持无覆盖发布时，stderr 会明确说明拒绝覆盖或无法无覆盖发布，不输出 traceback。

`verify` 校验失败时 stderr 会包含分类标签，例如：

```text
error: archive verification failed (2 issue(s)):
  MISSING: "notes/alpha.md" is listed in the manifest but absent
  TAMPERED: "notes/beta.md": sha256 ... vs ...
```

常见分类：`INVALID_ARCHIVE`、`INVALID_MANIFEST`、`MISSING`、`UNEXPECTED`、`TAMPERED`、`UNSAFE_PATH`、`DUPLICATE_MEMBER`、`SYMLINK`、`CASE_COLLISION`、`UNEXPECTED_MEMBER`、`ENCRYPTED`。

## 离线演练建议

1. 在单独的 `--work-dir` 中创建归档。
2. 对归档运行 `verify`，确认输出 `Snapshot verified`。
3. 在全新的父目录下选择不存在的恢复路径，运行 `restore`。
4. 抽检 Markdown、附件和目录结构；需要时把恢复目录与原始 Vault 做只读比较。
5. 恢复完成后，恢复目标本身不再被工具修改；再次演练请使用新的目标路径。

不要把恢复目标指向真实 Vault。该工具不会合并、修复或覆盖已有目录。

## 测试

在仓库根目录执行：

```bash
python -m unittest discover -s tools/vault-snapshot/tests -v
```

测试全部使用临时目录中的合成 Vault，只包含 Markdown 和显式 PNG 附件，不读取真实个人资料、不联网、不调用模型。覆盖：

- `create` → `verify` → `restore` 成功往返、空 Vault、确定性归档字节。
- 缺少显式参数、已有归档（文件或空目录）拒绝覆盖、工作目录位于 Vault 内、符号链接 Vault、发布前校验失败及失败后重试。
- 创建/恢复期间才出现的对方文件或空目录不会被覆盖，失败后不残留本次临时文件或暂存目录。
- 原子无覆盖发布能力不可用时返回稳定错误，不回退覆盖。
- POSIX 目录预留清理只移除本次创建且仍为空的原目录；预留中已有他人内容或路径已被替换时保持原样。
- 缺失成员、内容篡改、清单外成员、非法清单格式、路径穿越、Windows 尾随点/空格和设备名。
- 恢复目标已存在（文件、非空目录或空目录）、重复 ZIP 成员、符号链接成员、文件级和目录级 Windows 大小写碰撞。
- 失败后不残留创建临时文件或恢复暂存目录，并可再次成功后恢复。

部分用例依赖操作系统允许创建符号链接；Windows 未启用开发者模式时，创建 Vault 符号链接的单个用例会跳过，恢复侧对符号链接 ZIP 成员的拒绝测试仍会运行。

## 明确边界

- 不做加密、密码保护、数字签名或远程密钥管理。
- 不做自动排程、增量链、轮转、保留策略或自动删除。
- 不访问网络、模型 API 或任何外部服务。
- 不启动、停止或修改其他项目服务，不加入 Maven 模块。
- 没有默认扫描路径或后台扫描；只处理用户显式传入的 Vault 目录。
- 不解释或执行 Vault 内容。
- 不是完整文件系统镜像：不保证空目录及文件系统属性。
- 无提交、推送、发布或部署步骤。
