# 路径规范

> **禁止写死绝对路径。** 禁止 `K:\Sword11\`、`/mnt/k/Sword11`、`C:\Users\xxx` 等硬编码。

## 引用仓库资源

从仓库根出发，用相对路径：

```
Source/Server/ZoneServer/ZoneServer.prj
Lib/Linux_x64/
Document/编译说明.md
```

## 引用仓库外资源

用 `../` 前缀：

```
../DevEnv/devtools/mktools/kfc/product/linux/
../Base/base2019.sln
../Sword3-products/trunk/server/bin64/
```

## 引用其他 skill

从仓库根出发，完整路径：

```
Source/Tools/AITools/SKILLS/build/scripts/windows/find_msbuild.py
Source/Tools/AITools/SKILLS/build/references/linux.md
```

## 脚本内路径计算

用 `os.path` 从脚本位置推算仓库根目录，不写死绝对路径：

```python
script_dir = os.path.dirname(os.path.abspath(__file__))
# scripts/xxx.py → 仓库根：4 个 ..
# scripts/linux/xxx.py → 仓库根：5 个 ..
repo_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..', '..'))
```

> 层数 = 脚本到仓库根的目录深度。写错层数会导致路径计算错误。

## Examples 中的路径

用变量 `$S` 指向脚本目录，不写死完整路径：

```bash
S=Source/Tools/AITools/SKILLS/howto-create-skill/scripts
python $S/hello.py 张三
python $S/linux/scan_projects.py Source/
```
