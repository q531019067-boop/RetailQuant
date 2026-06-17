# C++ 代码引用规范

## 引用格式

### 函数引用

```
文件路径 函数名
```

示例：
- `SO3Represent/Src/common/kmathtools.cpp` 函数 `YawRHToLH`
- `SO3World/Src/KSkill.cpp` 函数 `CastOnPointSector`
- `KG3DInterface.h` 接口 `IKG3DScene`

### 结构体/类成员引用

```
文件路径 类名::成员名
```

示例：
- `SO3World/Src/KSkill.h` `KSkill::m_nAngleRange`
- `SO3World/Src/KTarget.h` `KTargetData::m_Coordination.nDirection`

### 宏/常量引用

```
定义文件 宏名
```

示例：
- `Include/SO3GlobalDef.h` `METER_LENGTH`
- `Include/SO3World/Global.h` `DIRECTION_COUNT`

## 不要用的格式

```
坏：kmathtools.cpp:467          ← 行号会变
坏：KSkill.cpp 第 4485 行       ← 行号会变
坏：Source/Common/.../kmathtools.cpp  ← 路径太长，读者不需要完整路径
```

## 搜索验证

写文档前，用 grep/Agent 验证函数名确实存在：

```bash
grep -rn "函数名" Source/ 2>/dev/null | head -5
```

确认函数名拼写正确、在预期的文件中。
