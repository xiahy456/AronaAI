# 记忆库调试脚本

长期记忆同时写在两处（另有 SQLite FTS5 全文索引）：

| 存储 | 默认路径 | 说明 |
|------|----------|------|
| SQLite | `data/memory/memory.db` 表 `memories` | 权威正文：`key`、`content`、`category`、`source` |
| FTS5 | 同库虚拟表 `memories_fts` | 分词检索 |
| Chroma | `data/memory/chroma/` collection `arona_memory` | 向量检索，id 与 `key` 相同 |

路径以 `config.yaml` 的 `memory.db_path` / `memory.chroma_path` / `memory.collection` 为准。

**所有命令都在 `backend/` 目录下执行**（需要读到 `config.yaml`）。

```powershell
cd backend
conda activate shittim-chest   # 或你的后端环境
```

---

## memory_db.py

查看、改写 SQLite 记忆；其中 `upsert` / `delete` / `retrieve` 会走 `MemoryStore`，从而连同 FTS 和 Chroma 一起更新。

### 查看

```powershell
python scripts/memory_db.py list
python scripts/memory_db.py get favorite_drink
python scripts/memory_db.py count
python scripts/memory_db.py -c "SELECT key, content, category FROM memories;"
python scripts/memory_db.py -c "SELECT key, content FROM memories WHERE content LIKE '%草莓牛奶%';"
```

不带子命令则进入 SQL REPL，语句以 `;` 结尾：

```text
sql> .help
sql> .tables
sql> .schema
sql> SELECT * FROM memories;
sql> .quit
```

REPL 与 `-c` **只操作 SQLite**。在这里 `INSERT` / `UPDATE` / `DELETE` 不会更新 Chroma；改完 `memories` 后脚本只会提示 `.sync_fts`（重建 FTS，仍然不动向量库）。

### 同步写入

```powershell
python scripts/memory_db.py upsert favorite_drink "老师喜欢草莓牛奶" --category preference
```

可选 `--source`（默认 `debug`）。这会同时更新 SQLite、FTS、Chroma。

### 混合检索（会加载 BGE）

```powershell
python scripts/memory_db.py retrieve "老师喜欢喝什么" --top-k 5
```

这是线上同款 FTS + 向量检索，带 `min_score` 过滤，不是把向量库全部倒出来。

### 指定库文件

```powershell
python scripts/memory_db.py --db data/memory/memory.db list
```

`--db` **只覆盖 SQLite 路径**。`upsert` / `delete` / `retrieve` 用的 Chroma 仍来自配置，不要拿它去操作另一份临时库却指望向量写到别处。

---

## check_memory_sync.py

比对 SQLite `memories` 与 Chroma 是否一致。只读，不加载 embedding 模型。

```powershell
python scripts/check_memory_sync.py
python scripts/check_memory_sync.py --json
python scripts/check_memory_sync.py --ignore-meta
python scripts/check_memory_sync.py --db data/memory/memory.db --chroma data/memory/chroma
```

报告字段：

| 字段 | 含义 |
|------|------|
| `sql_only` | 只在 SQLite |
| `chroma_only` | 只在 Chroma |
| `content_mismatch` | 同一 `key` 正文不同 |
| `metadata_mismatch` | `category` / `source` 不同（SQL 的 `NULL` 视为空字符串） |
| `missing_embedding` | Chroma 有记录但没有向量 |

退出码：`0` 一致，`1` 有差异，`2` 读库失败。

末行示例：

```text
OK  sql=5  chroma=5  matched=5
INCONSISTENT  mismatches=2
```

---

## 同步删除

不要用 SQL 直接删，否则 Chroma（以及未手动 `.sync_fts` 时的 FTS）会留下脏数据。

正确做法：先查出 `key`，再用 `delete` 子命令。`MemoryStore.delete` 会同时删 SQLite、FTS、Chroma。

```powershell
python scripts/memory_db.py -c "SELECT key, content FROM memories WHERE content = '老师今天下午4点睡到晚上7点';"
```

精确匹配不到时：

```powershell
python scripts/memory_db.py -c "SELECT key, content FROM memories WHERE content LIKE '%下午4点%';"
```

或 `python scripts/memory_db.py list`。

假设查到 `key` 为 `afternoon_nap`：

```powershell
python scripts/memory_db.py delete afternoon_nap
```

多条命中就对每个 `key` 各执行一次。

### 核对

```powershell
python scripts/memory_db.py get afternoon_nap
python scripts/check_memory_sync.py
```

`get` 应提示没有该 key；同步检查应为 `OK`。需要确认检索不再命中时（会加载 BGE）：

```powershell
python scripts/memory_db.py retrieve "老师今天下午4点睡到晚上7点"
```

### 已经误用 SQL 删除时

只要还记得 `key`，再跑一次 `delete <key>` 即可：SQLite 已空也没关系，仍会删 FTS 和 Chroma。

`key` 也丢了的话，用 `check_memory_sync.py` 看 `chroma_only`，再对那些 key 执行 `delete`。没有按正文直接同步删除的命令。

### 不要这样做

```sql
DELETE FROM memories WHERE content = '...';
```

这只改 SQLite。`.sync_fts` 只能重建 FTS，不能补齐或清理 Chroma。
