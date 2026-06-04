# AGENTS.md

## 项目概述

本仓库 **不是** 传统软件项目，而是 **WrinFix-H8™（乙酰基六肽-8）** 产品发布会的可编辑 PPTX 演示文稿仓库。唯一产物为：

- `乙酰基六肽-8-苹果风发布会.pptx`（14 页，Office Open XML 格式）

无 `package.json`、`requirements.txt`、Docker、CI 或应用源码。

## Cursor Cloud specific instructions

### 服务与依赖

| 类型 | 说明 |
|------|------|
| **必须运行** | 无（无后端/前端/数据库服务） |
| **可选** | Python 3（stdlib 即可解析 PPTX）；LibreOffice Impress / PowerPoint / Keynote 用于人工预览 |

VM 启动后 **无需** 安装 npm/pip 依赖或启动 dev server。

### 验证演示文稿（推荐 hello-world）

用 Python 标准库验证结构与幻灯片数量：

```bash
python3 << 'EOF'
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

pptx = Path("乙酰基六肽-8-苹果风发布会.pptx")
with zipfile.ZipFile(pptx) as z:
    slides = [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
    assert len(slides) == 14, f"expected 14 slides, got {len(slides)}"
    root = ET.fromstring(z.read("ppt/slides/slide1.xml"))
    texts = [t.text for t in root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t") if t.text]
    assert any("WrinFix-H8" in t for t in texts), "title slide missing product name"
print("PPTX OK:", len(slides), "slides")
EOF
```

ZIP 完整性检查：

```bash
unzip -t "乙酰基六肽-8-苹果风发布会.pptx"
```

### Lint / Test / Build

本仓库 **没有** 传统 lint、单元测试或 build 流程。环境是否就绪以 **PPTX 文件存在且上述验证通过** 为准。

### Git

- 默认分支：`main`
- 修改 `.pptx` 后请用 Git LFS 或二进制 diff 友好方式提交（当前为普通 Git 二进制文件）。
