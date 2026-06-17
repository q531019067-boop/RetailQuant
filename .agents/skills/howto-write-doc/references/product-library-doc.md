# 产品库文档规范

产品库文档（`tools/AITools/docs/`）的读者是策划和测试，他们看不到 C++ 源码。

## 核心原则

**所有 C++ 变量必须追溯到配置源头，同时保留公式说明用法。**

追溯配置不是简单替换代码，而是补充配置来源 + 保留公式。两者缺一不可：
- 配置来源：让策划知道去哪里改
- 公式：让策划一眼看出参数怎么起作用

## 三种配置来源

### 1. tab 表

配置项在 `.tab` 文件中，格式为 `文件路径 + 列名 + 值格式`。

示例：
```
配置文件: client/settings/NpcTemplate/<副本目录>/sNpcTemplate.tab
列名: NpcSeasonDamageScale
值格式: 千分比，1024 = 100%，0 或空 = 不缩放
```

**tab 表查找方法**：
1. 在 `client/settings/` 下搜索列名
2. 用 `head -1 file.tab | tr '\t' '\n' | grep -n "列名"` 定位列号
3. 值格式需要查看 C++ 加载代码或文档确认

### 2. Lua 脚本

配置项在 `.lua` 脚本中，格式为 `文件路径 + 函数名 + 配置写法`。

示例：
```
配置文件: client/scripts/skill/纯阳/天道剑势_万剑归宗.lua
配置方式: 在 GetSkillLevelData 函数中设置
写法: skill.nAngleRange = 256  (256 = 360°全向)
```

**脚本查找方法**：
1. 通过 `SkillRealization.tab` 的 ScriptFile 列找到脚本路径
2. 在脚本中搜索变量名

### 3. ini 配置文件

配置项在 `.ini` 文件中，格式为 `文件路径 + 段名 + 键名`。

示例：
```
配置文件: server/gs_settings.ini
配置项: [GameSetting] nMaxLevel = 100
```

**ini 查找方法**：
1. 在 `server/` 或 `client/settings/` 下搜索 `.ini` 文件
2. ini 文件是 GBK 编码，用文本编辑器打开
3. 格式为 `[Section]` 段 + `Key=Value` 键值对
4. 常见 ini 文件：`gs_settings.ini`（游戏设置）、`gateway.ini`（网关）、`zoneserver.ini`（区服）

## C++ 变量 → 配置的追溯方法

1. 找到 C++ 变量的赋值来源（如 `m_pTemplate->nXxx`）
2. 追溯到模板结构体的加载代码（如 `KSkillManager.cpp` 或 `KNpcTemplate.cpp`）
3. 确认是从 tab 表加载还是从脚本设置
4. 如果是 tab 表：找到列名
5. 如果是脚本：找到 `REGISTER_LUA_INTEGER` 注册的 Lua 属性名

## 文档中的写法

```
好的（策划能看懂）：
NPC 赛季伤害缩放系数，配置在 sNpcTemplate.tab 的 NpcSeasonDamageScale 列。
值为千分比，1024 = 100%，0 或空表示不缩放。

坏的（策划看不懂）：
pBullet->nNpcSeasonDamageScale = pNpc->m_pTemplate->nNpcSeasonDamageScale;
```
