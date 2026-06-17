如何写Skills
1. 核心概述
Skills 是一套可插拔的、按需加载的 AI 增强指令包。通过将特定领域的知识（如游戏数值表结构、脚本关联逻辑）封装为 Skill，可以使 AI 助手在处理任务时自动获得这些专业能力，而不会在平时占用宝贵的上下文空间。

1. 部署规约
2.1 存储路径
所有项目级技能必须严格存放在以下位置：
${workspaceFolder}/tools/AITools/SKILLS/

2.2 文件夹命名
每个技能需建立独立子文件夹，名称要求：

仅限小写字母、数字和连字符 (-)。

严禁使用空格、中文或特殊字符。

示例：npc-data-linker、ui-resource-manager。

2.3 编码协议 (重要)
技能文档编码：所有 SKILL.md、辅助脚本源码、Markdown 示例文件必须使用 UTF-8 编码保存。

业务处理编码：除非特别强调，技能在读写项目文件（如 .tab、.lua）时，必须默认使用 GBK 编码。

3. 技能包标准结构
${workspaceFolder}/tools/tools/AITools/SKILLS/my-skill/
├── SKILL.md              # [必须] 技能元数据与核心指令 (UTF-8)
├── scripts/              # [建议] 存放 Windows 批处理或 Python 脚本 (UTF-8)
├── examples/             # [可选] 存放填表/改脚本的对比示例 (UTF-8)
└── references/           # [可选] 存放大型配置规范或一些辅助知识文档 (UTF-8)

4. 技能定义模板 (SKILL.md)
YAML
---
name: npc-editor-helper
description: 专门处理 NPC 模板表与逻辑脚本的关联。当用户提到“修改 NPC”、“同步技能”或涉及.tab 文件时激活。
allowed-tools: powershell, cmd, Edit, Read
---

## YAML格式规范详解

每个Skill的SKILL.md文件必须包含标准的YAML头部，用于定义技能的基本元数据。YAML头部使用三个连字符`---`开始和结束。

### 基本格式
```yaml
---
name: skill-name
description: Skill功能的详细描述
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

### 字段说明
| 字段 | 类型 | 是否必需 | 说明 |
|------|------|----------|------|
| `name` | string | 是 | Skill的唯一名称，仅限小写字母、数字和连字符(-) |
| `description` | string | 是 | Skill功能的详细描述，支持多行文本（使用`\|`） |
| `allowed-tools` | string | 是 | 允许使用的工具列表，多个工具用逗号分隔 |

### 多行描述写法
当描述内容较长或需要分行时，使用`|`符号：
```yaml
---
name: dungeon-cooldown-expert
description: |
  副本CD配置专家，用于：
  1. 回答副本CD配置方式和文件路径
  2. 检查配置文件的正确性和完整性
  3. 查询特定副本的CD时间
  4. 指导用户完成配置任务
allowed-tools: powershell, cmd, Edit, Read, Write, RunCommand
---
```

### 游戏开发相关YAML示例

#### 1. 数值填表类Skill
```yaml
---
name: npc-data-manager
description: 管理NPC数据，支持读取和修改NPC模板表，自动同步相关脚本文件
allowed-tools: powershell, cmd, Edit, Read, Write
---
```

#### 2. 技能与Buff联动类Skill
```yaml
---
name: skill-buff-linker
description: 处理技能与Buff表联动，新增技能时自动生成对应Buff记录
allowed-tools: powershell, cmd, Edit, Read, Write
---
```

#### 3. 配置检查类Skill
```yaml
---
name: config-validator
description: 检查配置文件语法和格式，确保.tab文件符合规范，无数据冲突
allowed-tools: powershell, cmd, Edit, Read
---
```

#### 4. UI插件关联类Skill
```yaml
---
name: ui-plugin-coordinator
description: 协调UI插件与数据表的关联，确保界面显示与底层数据一致
allowed-tools: powershell, cmd, Edit, Read, Write
---
```

### 编码注意事项
1. **文件编码**：SKILL.md文件必须使用UTF-8编码保存
2. **路径格式**：在YAML描述中可以使用Windows路径，但建议使用正斜杠`/`
3. **工具限制**：根据Skill功能合理设置`allowed-tools`，避免不必要的权限

---

# NPC 模板助手指南

## 适用路径
- 配置表：client/settings/NpcTempleate.tab
- 脚本：client/scripts/NpcManager.lua

## 处理准则
1. **表格格式**：.tab 文件为制表符 (\t) 分隔，字符串无引号。读写必须用 GBK。
2. **多目录联动**：修改 NpcTempleate.tab 后，必须检查 NpcManager.lua 中对应的 ID 定义。

## Windows 命令行操作示例 (PowerShell)
```powershell
# 以 GBK 编码读取 NPC 表并查找特定 ID
Get-Content "client/settings/NpcTempleate.tab" -Encoding Default | Select-String "1001"
执行步骤
接收用户的修改需求。

读取.tab 文件（GBK 模式），定位行与列。

应用修改并保存。

扫描脚本目录，同步更新 Lua 引用。


---

## 5. 游戏开发实战案例

### 案例 A：数值填表与脚本关联 (针对非程序员)
**场景**：修改 NPC 的出生坐标或速度。
*   **关联文件 1**：`${workspaceFolder}/client/settings/NpcTempleate.tab` (GBK)
*   **关联文件 2**：`${workspaceFolder}/client/scripts/NpcManager.lua` (GBK)

**Skill 逻辑描述**：
> “当你修改 `NpcTempleate.tab` 时，请注意：
> 1. 列与列之间必须使用 `\t` 分隔。
> 2. 找到第 N 列的 `Speed` 字段进行修改。
> 3. 修改完成后，前往 `client/scripts/` 目录下查找所有引用该 NPC ID 的 Lua 脚本，确保逻辑层没有硬编码该数值。”

### 案例 B：技能与 Buff 表联动 (多目录关联)
**场景**：新增一个技能，并为其自动生成 Buff。
*   **技能表**：`${workspaceFolder}/client/settings/skill/skills.tab`
*   **Buff 表**：`${workspaceFolder}/client/settings/skill/buff.tab`
*   **GM 插件*：`${workspaceFolder}/client/interface/GMToosl`
*   **UI*：`${workspaceFolder}/client/ui/BuffShow.lua`

**Skill 自动化指令示例 (Python 伪代码)**：
```python
# 脚本保存为 UTF-8，处理游戏数据用 GBK
def add_new_skill(skill_id, buff_id):
    # 1. 写入技能表 (GBK)
    with open('client/settings/skill/skills.tab', 'a', encoding='gbk') as f:
        f.write(f"{skill_id}\tNewSkill\t{buff_id}\n")
    
    # 2. 写入关联 Buff 表 (GBK)
    with open('client/settings/skill/buff.tab', 'a', encoding='gbk') as f:
        f.write(f"{buff_id}\tBuffEffect\n")
6. 如何指导 AI 创建新 Skill
在与 AI 对话时，你可以直接使用以下 Prompt 模板：

开发者指令：
“请帮我创建一个新的技能，以及一些buff：

技能名：[输入技能名]， 技能id， buffID， buff名字。

核心任务：[如：每当我修改技能表和Buff表，自动去检查 UI 插件是否有冲突]。


7. 注意事项
Windows 路径：在指令中尽量使用斜杠 / 或在双引号内使用双反斜杠 \\ 以避免转义错误。

GBK 陷阱：PowerShell 5.1 默认输出可能带 BOM，建议在 Skill 指令中明确要求 AI 助手在保存时使用 Set-Content -Encoding Default (对应系统 ANSI/GBK) 。

8. 使用 agent-skill-generator 快速创建新技能

在 `${workspaceFolder}/tools/tools/AITools/SKILLS/` 目录下已经有一个现成的技能 `agent-skill-generator`，它可以帮助你快速生成新的技能。

### agent-skill-generator 功能介绍
这是一个自动化的技能生成器，能够根据自然语言描述创建完整的技能目录结构，包括：
- 自动识别技能类型（转换器、工具、知识库、测试器等）
- 生成符合规范的目录结构
- 创建包含正确YAML头部的SKILL.md文件
- 根据需要生成Python脚本和示例文件

### 如何安装和使用

#### 安装方法
1. **打包agent-skill-generator**：
   ```powershell
   cd ${workspaceFolder}/tools/tools/AITools/SKILLS/
   Compress-Archive -Path .\agent-skill-generator\* -DestinationPath .\agent-skill-generator.zip
   ```

2. **在Trae IDE中安装**：
   - 按照第9节的安装指南上传 `agent-skill-generator.zip`
   - 启用该技能

#### 使用方法
安装后，你可以通过以下方式使用：
1. **生成新技能**：
   ```
   我需要一个处理NPC数据的Skill，能够读取和修改NPC模板文件，支持批量操作。
   ```

2. **参考学习**：
   - 查看`agent-skill-generator`的目录结构作为模板
   - 学习其SKILL.md文件的编写方式
   - 参考其中的YAML格式定义

### 优势与价值
1. **提高效率**：无需手动创建目录结构和文件
2. **规范统一**：确保所有技能遵循相同标准
3. **学习参考**：提供了一个完整的技能实现示例
4. **类型覆盖**：支持8种不同的技能类型生成

### 实际应用场景
当需要创建新技能时，可以：
1. 先安装并使用`agent-skill-generator`生成技能框架
2. 根据生成的结果进行定制化修改
3. 参考其中的文档和示例完善功能
4. 最后按照第9节指南打包安装

## 9. Skill安装指南

创建好Skill目录后，需要将其打包并安装到Trae IDE中才能使用。

**提示**：你可以参考 `${workspaceFolder}/tools/tools/AITools/SKILLS/agent-skill-generator/` 目录的结构和文件作为标准示例。这个技能本身也是一个完整的Skill实现，你可以安装它来学习如何创建和使用Skill。

### 安装前准备
1. **检查Skill结构**：确保Skill目录包含正确的文件结构
2. **验证YAML头部**：检查SKILL.md文件中的YAML格式是否正确
3. **测试功能**：运行脚本确保功能正常

### 打包步骤
1. **进入Skill目录**：
   ```powershell
   cd ${workspaceFolder}/tools/tools/AITools/SKILLS/
   ```

2. **压缩Skill目录**：
   - 选中要安装的Skill目录（如`npc-data-manager`）
   - 右键选择"添加到压缩文件"
   - 格式选择`ZIP`
   - 确保只压缩目录本身，不包含父目录路径

   或者使用命令行：
   ```powershell
   Compress-Archive -Path .\npc-data-manager\* -DestinationPath .\npc-data-manager.zip
   ```

### Trae IDE安装步骤
1. **打开Trae IDE设置**：
   - 点击左下角的"设置"图标（齿轮图标）
   - 或使用快捷键 `Ctrl+,`

2. **进入技能管理**：
   - 左侧导航选择"规则和技能"
   - 点击"技能"选项卡

3. **创建新技能**：
   - 点击"创建"按钮
   - 在弹出的对话框中填写技能信息（可选，Trae会自动从SKILL.md读取）

4. **上传ZIP文件**：
   - 点击"上传"按钮
   - 选择之前创建的ZIP压缩包（如`npc-data-manager.zip`）
   - 等待上传完成

5. **完成安装**：
   - Trae会自动解析ZIP文件中的SKILL.md
   - 技能会出现在已安装技能列表中
   - 启用技能开关以激活

### 验证安装
1. **检查技能列表**：
   - 在Trae的聊天窗口中输入`/skills`查看已安装技能
   - 或查看设置中的技能管理界面

2. **测试技能功能**：
   - 在聊天中尝试使用新安装的技能
   - 例如：输入"修改NPC 1001的速度为5.0"

### 常见问题
#### Q: 上传ZIP文件失败怎么办？
A: 检查以下问题：
   - ZIP文件是否包含完整的Skill目录结构
   - SKILL.md文件是否在根目录下
   - ZIP文件大小是否过大（建议小于10MB）

#### Q: 技能安装后无法识别怎么办？
A: 检查以下问题：
   - SKILL.md中的YAML格式是否正确
   - `name`字段是否符合命名规范
   - 技能是否已启用

#### Q: 如何更新已安装的技能？
A: 有两种方法：
   1. **重新上传**：删除旧技能，上传新版本的ZIP文件
   2. **直接编辑**：在Trae的设置中编辑已安装的技能（高级用户）

### 批量安装技巧
如果需要安装多个技能，可以：
1. 将多个Skill目录打包成单个ZIP文件
2. 在Trae中一次性上传多个ZIP文件
3. 使用脚本批量生成和打包：
   ```powershell
   # 批量生成技能并打包
   Get-ChildItem -Directory | ForEach-Object {
     $skillName = $_.Name
     Compress-Archive -Path "$_\*" -DestinationPath "$skillName.zip"
   }
   ```

### 最佳实践
1. **版本控制**：在Skill目录中包含版本信息，如`version.txt`
2. **文档完整**：确保SKILL.md包含清晰的使用说明和示例
3. **依赖管理**：如果需要外部依赖，在SKILL.md中注明安装方法
4. **测试验证**：安装前先在本机测试技能功能
